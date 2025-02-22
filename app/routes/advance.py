from flask import Blueprint, request, jsonify
from datetime import datetime
from app import db
from app.models import Advance, Employee
from app.utils import token_required

advances_bp = Blueprint('advances', __name__)

# Create Advance
@advances_bp.route('/api/advances', methods=['POST'])
@token_required
def create_advance(user_id):
    data = request.get_json()

    required_fields = ['employee_id', 'amount', 'document_number']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return jsonify({'message': f'Missing fields: {", ".join(missing_fields)}'}), 400

    employee = Employee.query.get(data['employee_id'])
    if not employee:
        return jsonify({'message': 'Employee not found'}), 404

    advance = Advance(
        employee_id=data['employee_id'],
        amount=data['amount'],
        document_number=data['document_number'],
        notes=data.get('notes')
    )
    db.session.add(advance)
    db.session.commit()

    return jsonify({
        'id': advance.id,
        'date': str(advance.date),
        'amount': str(advance.amount),
        'document_number': advance.document_number,
        'notes': advance.notes,
        'employee': { 
            'id': employee.id,
            'full_name': employee.full_name
        }
    }), 201


# Get All Advances with Employee Details
@advances_bp.route('/api/advances', methods=['GET'])
@token_required
def get_all_advances(user_id):

    advances = Advance.query.join(Employee).all()

    return jsonify([{
        'id': adv.id,
        'employee': {
            'id': adv.employee.id,
            'name': adv.employee.full_name,
        },
        'amount': str(adv.amount),
        'document_number': adv.document_number,
        'notes': adv.notes,
        'date': str(adv.date)
    } for adv in advances]), 200

# Get Advance by ID
@advances_bp.route('/api/advances/<int:id>', methods=['GET'])
@token_required
def get_advance(user_id, id):
    advance = Advance.query.get(id)
    if not advance:
        return jsonify({'message': 'Advance not found'}), 404

    return jsonify({
        'id': advance.id,
        'employee_id': advance.employee_id,
        'amount': str(advance.amount),
        'document_number': advance.document_number,
        'notes': advance.notes,
        'date': str(advance.date)
    }), 200


# Update Advance
@advances_bp.route('/api/advances/<int:id>', methods=['PUT'])
@token_required
def update_advance(user_id, id):
    advance = Advance.query.get(id)
    if not advance:
        return jsonify({'message': 'Advance not found'}), 404

    data = request.get_json()
    for key, value in data.items():
        if hasattr(advance, key) and key != 'employee':  # تخطي التعديل على كائن الموظف
            setattr(advance, key, value)

    db.session.commit()

    # جلب معلومات الموظف المرتبطة بالسلفة
    employee = Employee.query.get(advance.employee_id)
    if not employee:
        return jsonify({'message': 'Employee not found'}), 404

    # إعادة السلفة مع تفاصيل الموظف بنفس النمط المستخدم في الفرونت
    return jsonify({
        'id': advance.id,
        'date': str(advance.date),
        'amount': str(advance.amount),
        'document_number': advance.document_number,
        'notes': advance.notes,
        'employee': {
            'id': employee.id,
            'name': employee.full_name  # التوافق مع اسم الحقل "name" بدلاً من "full_name"
        }
    }), 200

# Delete Advance
@advances_bp.route('/api/advances/<int:id>', methods=['DELETE'])
@token_required
def delete_advance(user_id, id):
    advance = Advance.query.get(id)
    if not advance:
        return jsonify({'message': 'Advance not found'}), 404

    db.session.delete(advance)
    db.session.commit()

    return jsonify({'message': 'Advance deleted'}), 200


# Get Advances by Employee ID
@advances_bp.route('/api/advances/employee/<int:employee_id>', methods=['GET'])
@token_required
def get_advances_by_employee(user_id, employee_id):
    advances = Advance.query.filter_by(employee_id=employee_id).all()
    if not advances:
        return jsonify({'message': 'No advances found for this employee'})

    return jsonify([{
        'id': adv.id,
        'employee_id': adv.employee_id,
        'amount': str(adv.amount),
        'document_number': adv.document_number,
        'notes': adv.notes,
        'date': str(adv.date)
    } for adv in advances]), 200


# Get Advances by Date Range
@advances_bp.route('/api/advances/range', methods=['GET'])
@token_required
def get_advances_by_date_range(user_id):
    start_date = request.args.get('startDate')
    end_date = request.args.get('endDate')

    if not start_date or not end_date:
        return jsonify({'message': 'Both startDate and endDate are required'}), 400

    try:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'message': 'Invalid date format. Please use YYYY-MM-DD'}), 400

    advances = Advance.query.filter(Advance.date.between(start_date, end_date)).all()
    if not advances:
        return jsonify({'message': 'No advances found for the given date range'})

    return jsonify([{
        'id': adv.id,
        'employee_id': adv.employee_id,
        'amount': str(adv.amount),
        'document_number': adv.document_number,
        'notes': adv.notes,
        'date': str(adv.date)
    } for adv in advances]), 200


@advances_bp.route('/api/advances/employee/<int:employee_id>/current-month', methods=['GET'])
@token_required
def get_current_month_advances_total(user_id, employee_id):
    # الحصول على التاريخ الحالي
    today = datetime.today()

    # تحديد بداية الشهر ونهاية الشهر
    start_of_month = today.replace(day=1)
    end_of_month = today.replace(day=1, month=today.month+1) if today.month != 12 else today.replace(day=1, month=1, year=today.year+1)

    # استعلام للحصول على مجموع السلف للموظف خلال الشهر الحالي
    total_advances = db.session.query(db.func.sum(Advance.amount)).filter(
        Advance.employee_id == employee_id,
        Advance.date >= start_of_month,
        Advance.date < end_of_month
    ).scalar()  # استخدام .scalar() للحصول على النتيجة كقيمة واحدة

    # في حالة عدم وجود سلف، إرجاع 0
    total_advances = total_advances if total_advances else 0

    return jsonify({
        'employee_id': employee_id,
        'total_advances_for_current_month': str(total_advances)
    }), 200
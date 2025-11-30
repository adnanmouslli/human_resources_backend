from flask import Blueprint, request, jsonify
from datetime import datetime
from app import db
from app.models import Advance, Employee
from app.models.user import User
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


# Bulk Upload Advances from Excel
@advances_bp.route('/api/advances/bulk-upload', methods=['POST'])
@token_required
def bulk_upload_advances(user):
    """
    رفع مجموعة من السلف دفعة واحدة من ملف Excel
    """
    data = request.get_json()
    
    if 'advances' not in data or not isinstance(data['advances'], list):
        return jsonify({'message': 'Invalid data format. Expected "advances" array'}), 400
    
    advances_data = data['advances']
    
    if len(advances_data) == 0:
        return jsonify({'message': 'No advances data provided'}), 400
    
    # الحصول على المستخدم
    user_obj = User.query.get(user.id)
    if not user_obj:
        return jsonify({'message': 'User not found'}), 404
    
    # جلب الموظفين المسموح له برؤيتهم
    accessible_employees = user_obj.get_accessible_employees()
    accessible_employee_ids = {emp.id for emp in accessible_employees}
    
    successful_advances = []
    failed_advances = []
    
    for index, advance_data in enumerate(advances_data, start=2):  # نبدأ من 2 لأن 1 هو العنوان
        try:
            # التحقق من الحقول المطلوبة
            employee_id = advance_data.get('employee_id')
            amount = advance_data.get('amount')
            document_number = advance_data.get('document_number')
            
            if not employee_id or not amount or not document_number:
                failed_advances.append({
                    'row': index,
                    'employee_id': employee_id or 'N/A',
                    'employee_name': 'N/A',
                    'error': 'بيانات ناقصة: يجب توفير كود الموظف، القيمة، ورقم المستند'
                })
                continue
            
            # التحقق من أن الموظف موجود
            employee = Employee.query.get(employee_id)
            if not employee:
                failed_advances.append({
                    'row': index,
                    'employee_id': employee_id,
                    'employee_name': 'غير موجود',
                    'error': f'الموظف بالكود {employee_id} غير موجود'
                })
                continue
            
            # التحقق من صلاحية الوصول للموظف
            if employee_id not in accessible_employee_ids:
                failed_advances.append({
                    'row': index,
                    'employee_id': employee_id,
                    'employee_name': employee.full_name,
                    'error': 'ليس لديك صلاحية للوصول إلى هذا الموظف'
                })
                continue
            
            # التحقق من صحة المبلغ
            try:
                amount = float(amount)
                if amount <= 0:
                    raise ValueError("Amount must be positive")
            except (ValueError, TypeError):
                failed_advances.append({
                    'row': index,
                    'employee_id': employee_id,
                    'employee_name': employee.full_name,
                    'error': 'قيمة السلفة غير صحيحة'
                })
                continue
            
            # إنشاء السلفة
            advance = Advance(
                employee_id=employee_id,
                amount=amount,
                document_number=str(document_number),
                notes=advance_data.get('notes', '')
            )
            
            db.session.add(advance)
            successful_advances.append({
                'employee_id': employee_id,
                'employee_name': employee.full_name,
                'amount': amount,
                'document_number': document_number
            })
            
        except Exception as e:
            failed_advances.append({
                'row': index,
                'employee_id': advance_data.get('employee_id', 'N/A'),
                'employee_name': 'N/A',
                'error': f'خطأ غير متوقع: {str(e)}'
            })
    
    # حفظ جميع السلف الناجحة
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'فشل حفظ البيانات: {str(e)}',
            'successful_count': 0,
            'failed_count': len(advances_data)
        }), 500
    
    return jsonify({
        'success': True,
        'message': f'تم رفع {len(successful_advances)} سلفة بنجاح من أصل {len(advances_data)}',
        'successful_count': len(successful_advances),
        'failed_count': len(failed_advances),
        'errors': failed_advances if failed_advances else None
    }), 200


# Get All Advances with Employee Details
@advances_bp.route('/api/advances', methods=['GET'])
@token_required
def get_all_advances(user):
    # الحصول على المستخدم
    user = User.query.get(user.id)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    # جلب الموظفين المسموح له برؤيتهم
    accessible_employees = user.get_accessible_employees()
    accessible_employee_ids = [emp.id for emp in accessible_employees]

    # جلب السلف فقط للموظفين المسموحين
    advances = Advance.query.filter(Advance.employee_id.in_(accessible_employee_ids)).join(Employee).all()

    # تجهيز النتائج
    result = []
    for adv in advances:
        result.append({
            'id': adv.id,
            'employee': {
                'id': adv.employee.id,
                'name': adv.employee.full_name,
            },
            'amount': str(adv.amount),
            'document_number': adv.document_number,
            'notes': adv.notes,
            'date': adv.date.isoformat() if adv.date else None
        })

    return jsonify(result), 200


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
            'name': employee.full_name
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
    ).scalar()

    # في حالة عدم وجود سلف، إرجاع 0
    total_advances = total_advances if total_advances else 0

    return jsonify({
        'employee_id': employee_id,
        'total_advances_for_current_month': str(total_advances)
    }), 200
from flask import Blueprint, request, jsonify
from datetime import datetime, date
from app import db
from app.models.holiday import Holiday
from app.models.user import User
from app.utils import token_required

holiday_bp = Blueprint('holiday', __name__)

@holiday_bp.route('/api/holidays', methods=['POST'])
@token_required
def create_holiday(current_user):  # تغيير اسم المعامل
    """إنشاء عطلة جديدة"""
    try:
        # الحصول على المستخدم مباشرة من المعامل
        if not current_user or not current_user.has_permission('create', 'holidays'):
            return jsonify({'message': 'Unauthorized'}), 403
        
        data = request.get_json()
        
        # التحقق من البيانات المطلوبة
        required_fields = ['name', 'date']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return jsonify({'message': f'Missing fields: {", ".join(missing_fields)}'}), 400
        
        # تحويل التاريخ
        try:
            holiday_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'message': 'Invalid date format. Use YYYY-MM-DD'}), 400
        
        # التحقق من عدم وجود عطلة في نفس التاريخ للفرع/القسم نفسه
        existing_holiday = Holiday.is_holiday(
            holiday_date, 
            data.get('branch_id'),
            data.get('department_id')
        )
        
        if existing_holiday:
            return jsonify({
                'message': f'Holiday already exists on {holiday_date}: {existing_holiday.name}'
            }), 400
        
        # إنشاء العطلة الجديدة
        holiday = Holiday(
            name=data['name'],
            date=holiday_date,
            description=data.get('description'),
            holiday_type=data.get('holiday_type', 'national'),
            is_paid=data.get('is_paid', True),
            branch_id=data.get('branch_id'),
            department_id=data.get('department_id'),
            created_by=current_user.id  # استخدام current_user.id
        )
        
        db.session.add(holiday)
        db.session.commit()
        
        return jsonify({
            'message': 'Holiday created successfully',
            'holiday': holiday.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Error creating holiday: {str(e)}'}), 500

@holiday_bp.route('/api/holidays', methods=['GET'])
@token_required
def get_holidays(current_user):  # تغيير اسم المعامل
    """الحصول على قائمة العطل"""
    try:
        if not current_user:
            return jsonify({'message': 'User not found'}), 404
        
        # الحصول على معاملات الفلترة
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        branch_id = request.args.get('branch_id', type=int)
        department_id = request.args.get('department_id', type=int)
        holiday_type = request.args.get('holiday_type')
        
        # بناء الاستعلام
        query = Holiday.query.filter(Holiday.is_active == True)
        
        # تطبيق الفلاتر
        if start_date and end_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                query = query.filter(Holiday.date.between(start_date, end_date))
            except ValueError:
                return jsonify({'message': 'Invalid date format. Use YYYY-MM-DD'}), 400
        
        if branch_id:
            query = query.filter(
                db.or_(
                    Holiday.branch_id == branch_id,
                    Holiday.branch_id.is_(None)
                )
            )
        
        if department_id:
            query = query.filter(
                db.or_(
                    Holiday.department_id == department_id,
                    Holiday.department_id.is_(None)
                )
            )
        
        if holiday_type:
            query = query.filter(Holiday.holiday_type == holiday_type)
        
        # تطبيق الصلاحيات حسب نوع المستخدم
        if current_user.is_branch_head() or current_user.is_branch_deputy():
            query = query.filter(
                db.or_(
                    Holiday.branch_id == current_user.branch_id,
                    Holiday.branch_id.is_(None)
                )
            )
        elif current_user.is_department_head() or current_user.is_department_deputy():
            query = query.filter(
                db.or_(
                    Holiday.department_id == current_user.department_id,
                    Holiday.department_id.is_(None)
                )
            )
        
        holidays = query.order_by(Holiday.date).all()
        
        return jsonify([holiday.to_dict() for holiday in holidays]), 200
        
    except Exception as e:
        return jsonify({'message': f'Error fetching holidays: {str(e)}'}), 500

@holiday_bp.route('/api/holidays/<int:holiday_id>', methods=['PUT'])
@token_required
def update_holiday(current_user, holiday_id):  # تغيير اسم المعامل
    """تحديث عطلة موجودة"""
    try:
        if not current_user or not current_user.has_permission('update', 'holidays'):
            return jsonify({'message': 'Unauthorized'}), 403
        
        holiday = Holiday.query.get(holiday_id)
        if not holiday:
            return jsonify({'message': 'Holiday not found'}), 404
        
        data = request.get_json()
        
        # تحديث البيانات
        if 'name' in data:
            holiday.name = data['name']
        
        if 'date' in data:
            try:
                holiday.date = datetime.strptime(data['date'], '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'message': 'Invalid date format. Use YYYY-MM-DD'}), 400
        
        if 'description' in data:
            holiday.description = data['description']
        
        if 'holiday_type' in data:
            holiday.holiday_type = data['holiday_type']
        
        if 'is_paid' in data:
            holiday.is_paid = data['is_paid']
        
        if 'branch_id' in data:
            holiday.branch_id = data['branch_id']
        
        if 'department_id' in data:
            holiday.department_id = data['department_id']
        
        if 'is_active' in data:
            holiday.is_active = data['is_active']
        
        db.session.commit()
        
        return jsonify({
            'message': 'Holiday updated successfully',
            'holiday': holiday.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Error updating holiday: {str(e)}'}), 500

@holiday_bp.route('/api/holidays/<int:holiday_id>', methods=['DELETE'])
@token_required
def delete_holiday(current_user, holiday_id):  # تغيير اسم المعامل
    """حذف عطلة (إلغاء تفعيل)"""
    try:
        if not current_user or not current_user.has_permission('delete', 'holidays'):
            return jsonify({'message': 'Unauthorized'}), 403
        
        holiday = Holiday.query.get(holiday_id)
        if not holiday:
            return jsonify({'message': 'Holiday not found'}), 404
        
        # بدلاً من الحذف الفعلي، نقوم بإلغاء التفعيل
        holiday.is_active = False
        db.session.commit()
        
        return jsonify({'message': 'Holiday deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Error deleting holiday: {str(e)}'}), 500

@holiday_bp.route('/api/holidays/check', methods=['GET'])
@token_required
def check_holiday(current_user):  # تغيير اسم المعامل
    """التحقق من كون تاريخ معين يوم عطلة"""
    try:
        date_str = request.args.get('date')
        branch_id = request.args.get('branch_id', type=int)
        department_id = request.args.get('department_id', type=int)
        
        if not date_str:
            return jsonify({'message': 'Date parameter is required'}), 400
        
        try:
            check_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'message': 'Invalid date format. Use YYYY-MM-DD'}), 400
        
        holiday = Holiday.is_holiday(check_date, branch_id, department_id)
        
        if holiday:
            return jsonify({
                'is_holiday': True,
                'holiday': holiday.to_dict()
            }), 200
        else:
            return jsonify({
                'is_holiday': False,
                'holiday': None
            }), 200
            
    except Exception as e:
        return jsonify({'message': f'Error checking holiday: {str(e)}'}), 500

@holiday_bp.route('/api/holidays/bulk', methods=['POST'])
@token_required
def create_bulk_holidays(current_user):  # تغيير اسم المعامل
    """إنشاء عطل متعددة دفعة واحدة"""
    try:
        if not current_user or not current_user.has_permission('create', 'holidays'):
            return jsonify({'message': 'Unauthorized'}), 403
        
        data = request.get_json()
        holidays_data = data.get('holidays', [])
        
        if not holidays_data:
            return jsonify({'message': 'No holidays data provided'}), 400
        
        created_holidays = []
        errors = []
        
        for i, holiday_data in enumerate(holidays_data):
            try:
                # التحقق من البيانات المطلوبة
                if 'name' not in holiday_data or 'date' not in holiday_data:
                    errors.append(f"Holiday {i+1}: Missing required fields (name, date)")
                    continue
                
                # تحويل التاريخ
                holiday_date = datetime.strptime(holiday_data['date'], '%Y-%m-%d').date()
                
                # التحقق من عدم وجود عطلة مسبقاً
                existing_holiday = Holiday.is_holiday(
                    holiday_date,
                    holiday_data.get('branch_id'),
                    holiday_data.get('department_id')
                )
                
                if existing_holiday:
                    errors.append(f"Holiday {i+1}: Already exists on {holiday_date}")
                    continue
                
                # إنشاء العطلة
                holiday = Holiday(
                    name=holiday_data['name'],
                    date=holiday_date,
                    description=holiday_data.get('description'),
                    holiday_type=holiday_data.get('holiday_type', 'national'),
                    is_paid=holiday_data.get('is_paid', True),
                    branch_id=holiday_data.get('branch_id'),
                    department_id=holiday_data.get('department_id'),
                    created_by=current_user.id  # استخدام current_user.id
                )
                
                db.session.add(holiday)
                created_holidays.append(holiday_data)
                
            except ValueError as e:
                errors.append(f"Holiday {i+1}: Invalid date format")
            except Exception as e:
                errors.append(f"Holiday {i+1}: {str(e)}")
        
        if created_holidays:
            db.session.commit()
        
        return jsonify({
            'message': f'Created {len(created_holidays)} holidays',
            'created_count': len(created_holidays),
            'errors_count': len(errors),
            'errors': errors
        }), 201 if created_holidays else 400
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Error creating bulk holidays: {str(e)}'}), 500
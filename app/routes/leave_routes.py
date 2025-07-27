from flask import Blueprint, request, jsonify
from sqlalchemy import null
from app import db
from app.utils import token_required
from app.models.leave import Leave
from app.models.user import User
from app.models.employee import Employee
from datetime import datetime, date, timedelta

leave_bp = Blueprint('leave', __name__)

# =========================== إنشاء إجازة جديدة ===========================

@leave_bp.route('/api/leaves', methods=['POST'])
@token_required
def create_leave(user):
    try:
        data = request.get_json()
        
        # التحقق من البيانات المطلوبة
        required_fields = ['employee_id', 'leave_type', 'start_date', 'reason']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'message': f'الحقل {field} مطلوب'}), 400
        
        # التحقق من صحة نوع الإجازة
        valid_types = ['hourly_leave', 'daily_leave']
        if data['leave_type'] not in valid_types:
            return jsonify({'message': 'نوع الإجازة غير صالح'}), 400
        
        # التحقق من وجود الموظف
        employee = Employee.query.get(data['employee_id'])
        if not employee:
            return jsonify({'message': 'الموظف غير موجود'}), 404
        
        # التحقق من صلاحية المستخدم
        current_user = User.query.get(user.id)
        if not current_user:
            return jsonify({'message': 'المستخدم غير موجود'}), 404
        
        # فقط السوبر أدمن يمكنه إنشاء إجازات مباشرة
        if not current_user.is_super_admin():
            return jsonify({'message': 'ليس لديك صلاحية لإنشاء إجازات مباشرة'}), 403
        
        # إنشاء الإجازة
        leave_data = {
            'employee_id': data['employee_id'],
            'leave_type': data['leave_type'],
            'start_date': datetime.strptime(data['start_date'], '%Y-%m-%d').date(),
            'reason': data['reason'],
            'notes': data.get('notes'),
            'status': data.get('status', 'active'),
            'transaction_id': null
        }
        
        # إضافة البيانات حسب نوع الإجازة
        if data['leave_type'] == 'daily_leave':
            if not data.get('days'):
                return jsonify({'message': 'عدد الأيام مطلوب للإجازة اليومية'}), 400
            
            days = int(data['days'])
            leave_data['days'] = days
            
            # حساب تاريخ النهاية
            start_date = leave_data['start_date']
            end_date = start_date + timedelta(days=days-1) if days > 1 else start_date
            leave_data['end_date'] = end_date
            
        elif data['leave_type'] == 'hourly_leave':
            required_hourly_fields = ['hours']
            for field in required_hourly_fields:
                if not data.get(field):
                    return jsonify({'message': f'الحقل {field} مطلوب للإجازة الساعية'}), 400
            
            leave_data['hours'] = int(data['hours'])
            
            # إضافة الأوقات إذا تم تقديمها
            if data.get('start_time'):
                try:
                    leave_data['start_time'] = datetime.strptime(data['start_time'], '%H:%M:%S').time()
                except ValueError:
                    try:
                        leave_data['start_time'] = datetime.strptime(data['start_time'], '%H:%M').time()
                    except ValueError:
                        return jsonify({'message': 'تنسيق وقت البداية غير صحيح'}), 400
            
            if data.get('end_time'):
                try:
                    leave_data['end_time'] = datetime.strptime(data['end_time'], '%H:%M:%S').time()
                except ValueError:
                    try:
                        leave_data['end_time'] = datetime.strptime(data['end_time'], '%H:%M').time()
                    except ValueError:
                        return jsonify({'message': 'تنسيق وقت النهاية غير صحيح'}), 400
        
        # إنشاء الإجازة
        leave = Leave(**leave_data)
        db.session.add(leave)
        db.session.commit()
        
        return jsonify({
            'message': 'تم إنشاء الإجازة بنجاح',
            'leave': leave.get_leave_details()
        }), 201
    
    except Exception as e:
        db.session.rollback()
        print(f"Error creating leave: {str(e)}")
        return jsonify({'message': f'حدث خطأ أثناء إنشاء الإجازة: {str(e)}'}), 500


# =========================== تحديث إجازة ===========================

@leave_bp.route('/api/leaves/<int:leave_id>', methods=['PUT'])
@token_required
def update_leave(user, leave_id):
    try:
        leave = Leave.query.get(leave_id)
        if not leave:
            return jsonify({'message': 'الإجازة غير موجودة'}), 404

        current_user = User.query.get(user.id)
        
        # فقط السوبر أدمن يمكنه تحديث الإجازات
        if not current_user.is_super_admin():
            return jsonify({'message': 'ليس لديك صلاحية لتحديث الإجازات'}), 403
        
        # لا يمكن تحديث الإجازات المرتبطة بمعاملات مقبولة
        if leave.transaction_id and leave.transaction and leave.transaction.status == 'approved':
            return jsonify({'message': 'لا يمكن تحديث إجازة مرتبطة بمعاملة مقبولة'}), 400
        
        data = request.get_json()
        
        # تحديث الحقول المسموحة
        if 'reason' in data:
            leave.reason = data['reason']
        if 'notes' in data:
            leave.notes = data['notes']
        if 'status' in data and data['status'] in ['active', 'cancelled', 'expired']:
            leave.status = data['status']
        
        # تحديث البيانات الخاصة بنوع الإجازة
        if leave.leave_type == 'daily_leave':
            if 'days' in data:
                days = int(data['days'])
                leave.days = days
                # إعادة حساب تاريخ النهاية
                end_date = leave.start_date + timedelta(days=days-1) if days > 1 else leave.start_date
                leave.end_date = end_date
        elif leave.leave_type == 'hourly_leave':
            if 'hours' in data:
                leave.hours = int(data['hours'])
            if 'start_time' in data:
                try:
                    leave.start_time = datetime.strptime(data['start_time'], '%H:%M:%S').time()
                except ValueError:
                    leave.start_time = datetime.strptime(data['start_time'], '%H:%M').time()
            if 'end_time' in data:
                try:
                    leave.end_time = datetime.strptime(data['end_time'], '%H:%M:%S').time()
                except ValueError:
                    leave.end_time = datetime.strptime(data['end_time'], '%H:%M').time()
        
        leave.updated_at = datetime.now()
        db.session.commit()
        
        return jsonify({
            'message': 'تم تحديث الإجازة بنجاح',
            'leave': leave.get_leave_details()
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'حدث خطأ أثناء تحديث الإجازة: {str(e)}'}), 500

# =========================== الحصول على جميع الإجازات ===========================

@leave_bp.route('/api/leaves', methods=['GET'])
@token_required
def get_all_leaves(user):
    try:
        current_user = User.query.get(user.id)
        if not current_user:
            return jsonify({'message': 'المستخدم غير موجود'}), 404

        # فلترة الإجازات حسب صلاحيات المستخدم
        query = Leave.query
        
        if not current_user.is_super_admin():
            accessible_employee_ids = [emp.id for emp in current_user.get_accessible_employees()]
            if accessible_employee_ids:
                query = query.filter(Leave.employee_id.in_(accessible_employee_ids))
            else:
                query = query.filter(Leave.employee_id == current_user.employee_id)

        # فلترة حسب النوع إذا تم تحديده
        leave_type = request.args.get('type')
        if leave_type:
            query = query.filter(Leave.leave_type == leave_type)

        # فلترة حسب الحالة إذا تم تحديدها
        status = request.args.get('status')
        if status:
            query = query.filter(Leave.status == status)

        # فلترة حسب الموظف إذا تم تحديده
        employee_id = request.args.get('employee_id')
        if employee_id:
            query = query.filter(Leave.employee_id == employee_id)

        # فلترة حسب فترة زمنية
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        if start_date and end_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                query = query.filter(
                    Leave.start_date <= end_date,
                    db.or_(
                        Leave.end_date >= start_date,
                        Leave.end_date.is_(None)
                    )
                )
            except ValueError:
                return jsonify({'message': 'تنسيق التاريخ غير صحيح. استخدم YYYY-MM-DD'}), 400

        # ترتيب النتائج
        query = query.order_by(Leave.created_at.desc())

        # التصفح (pagination)
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        leaves = query.paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )

        result = []
        for leave in leaves.items:
            result.append(leave.get_leave_details())

        return jsonify({
            'leaves': result,
            'pagination': {
                'page': leaves.page,
                'pages': leaves.pages,
                'per_page': leaves.per_page,
                'total': leaves.total,
                'has_next': leaves.has_next,
                'has_prev': leaves.has_prev
            }
        }), 200

    except Exception as e:
        return jsonify({'message': f'حدث خطأ أثناء جلب الإجازات: {str(e)}'}), 500
        

# =========================== الحصول على إجازة محددة ===========================

@leave_bp.route('/api/leaves/<int:leave_id>', methods=['GET'])
@token_required
def get_leave(user, leave_id):
    try:
        leave = Leave.query.get(leave_id)
        if not leave:
            return jsonify({'message': 'الإجازة غير موجودة'}), 404

        current_user = User.query.get(user.id)
        
        # التحقق من صلاحية الوصول
        if not current_user.is_super_admin():
            accessible_employee_ids = [emp.id for emp in current_user.get_accessible_employees()]
            if leave.employee_id not in accessible_employee_ids and leave.employee_id != current_user.employee_id:
                return jsonify({'message': 'ليس لديك صلاحية للوصول إلى هذه الإجازة'}), 403

        return jsonify(leave.get_leave_details()), 200

    except Exception as e:
        return jsonify({'message': f'حدث خطأ أثناء جلب الإجازة: {str(e)}'}), 500

# =========================== الحصول على إجازات موظف محدد ===========================

@leave_bp.route('/api/employees/<int:employee_id>/leaves', methods=['GET'])
@token_required
def get_employee_leaves(user, employee_id):
    try:
        current_user = User.query.get(user.id)
        if not current_user:
            return jsonify({'message': 'المستخدم غير موجود'}), 404

        # التحقق من صلاحية الوصول للموظف
        if not current_user.is_super_admin():
            accessible_employee_ids = [emp.id for emp in current_user.get_accessible_employees()]
            if employee_id not in accessible_employee_ids and employee_id != current_user.employee_id:
                return jsonify({'message': 'ليس لديك صلاحية للوصول إلى إجازات هذا الموظف'}), 403

        employee = Employee.query.get(employee_id)
        if not employee:
            return jsonify({'message': 'الموظف غير موجود'}), 404

        # فلترة حسب فترة زمنية إذا تم تحديدها
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if start_date and end_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                leaves = Leave.get_employee_leaves_for_period(employee_id, start_date, end_date)
            except ValueError:
                return jsonify({'message': 'تنسيق التاريخ غير صحيح. استخدم YYYY-MM-DD'}), 400
        else:
            leaves = Leave.query.filter_by(employee_id=employee_id).order_by(Leave.created_at.desc()).all()

        result = []
        for leave in leaves:
            result.append(leave.get_leave_details())

        return jsonify({
            'employee': {
                'id': employee.id,
                'full_name': employee.full_name,
                'fingerprint_id': employee.fingerprint_id
            },
            'leaves': result,
            'total_count': len(result)
        }), 200

    except Exception as e:
        return jsonify({'message': f'حدث خطأ أثناء جلب إجازات الموظف: {str(e)}'}), 500

# =========================== حذف إجازة ===========================

@leave_bp.route('/api/leaves/<int:leave_id>', methods=['DELETE'])
@token_required
def delete_leave(user, leave_id):
    try:
        leave = Leave.query.get(leave_id)
        if not leave:
            return jsonify({'message': 'الإجازة غير موجودة'}), 404

        current_user = User.query.get(user.id)
        
        # فقط السوبر أدمن يمكنه حذف الإجازات
        if not current_user.is_super_admin():
            return jsonify({'message': 'ليس لديك صلاحية لحذف الإجازات'}), 403

        # التحقق من إمكانية الحذف (لا يمكن حذف الإجازات المرتبطة بمعاملات مقبولة)
        if leave.transaction and leave.transaction.status == 'approved':
            return jsonify({'message': 'لا يمكن حذف إجازة مرتبطة بمعاملة مقبولة'}), 400

        db.session.delete(leave)
        db.session.commit()

        return jsonify({'message': 'تم حذف الإجازة بنجاح'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'حدث خطأ أثناء حذف الإجازة: {str(e)}'}), 500

# =========================== تحديث حالة إجازة ===========================

@leave_bp.route('/api/leaves/<int:leave_id>/status', methods=['PUT'])
@token_required
def update_leave_status(user, leave_id):
    try:
        leave = Leave.query.get(leave_id)
        if not leave:
            return jsonify({'message': 'الإجازة غير موجودة'}), 404

        current_user = User.query.get(user.id)
        
        # فقط السوبر أدمن يمكنه تحديث حالة الإجازات
        if not current_user.is_super_admin():
            return jsonify({'message': 'ليس لديك صلاحية لتحديث حالة الإجازات'}), 403

        data = request.get_json()
        new_status = data.get('status')
        
        if new_status not in ['active', 'cancelled', 'expired']:
            return jsonify({'message': 'حالة الإجازة غير صالحة'}), 400

        leave.status = new_status
        leave.updated_at = datetime.now()
        
        db.session.commit()

        return jsonify({
            'message': f'تم تحديث حالة الإجازة إلى {new_status}',
            'leave': leave.get_leave_details()
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'حدث خطأ أثناء تحديث حالة الإجازة: {str(e)}'}), 500

# =========================== إحصائيات الإجازات ===========================

@leave_bp.route('/api/leaves/statistics', methods=['GET'])
@token_required
def get_leave_statistics(user):
    try:
        current_user = User.query.get(user.id)
        if not current_user:
            return jsonify({'message': 'المستخدم غير موجود'}), 404

        # فلترة الإجازات حسب صلاحيات المستخدم
        query = Leave.query
        
        if not current_user.is_super_admin():
            accessible_employee_ids = [emp.id for emp in current_user.get_accessible_employees()]
            if accessible_employee_ids:
                query = query.filter(Leave.employee_id.in_(accessible_employee_ids))
            else:
                query = query.filter(Leave.employee_id == current_user.employee_id)

        # فلترة حسب فترة زمنية إذا تم تحديدها
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if start_date and end_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                query = query.filter(
                    Leave.start_date <= end_date,
                    db.or_(
                        Leave.end_date >= start_date,
                        Leave.end_date.is_(None)
                    )
                )
            except ValueError:
                return jsonify({'message': 'تنسيق التاريخ غير صحيح. استخدم YYYY-MM-DD'}), 400

        # إحصائيات عامة
        total_leaves = query.count()
        active_leaves = query.filter(Leave.status == 'active').count()
        cancelled_leaves = query.filter(Leave.status == 'cancelled').count()
        expired_leaves = query.filter(Leave.status == 'expired').count()

        # إحصائيات حسب النوع
        hourly_leaves = query.filter(Leave.leave_type == 'hourly_leave').count()
        daily_leaves = query.filter(Leave.leave_type == 'daily_leave').count()

        # إحصائيات تفصيلية
        hourly_leaves_active = query.filter(
            Leave.leave_type == 'hourly_leave',
            Leave.status == 'active'
        ).count()
        
        daily_leaves_active = query.filter(
            Leave.leave_type == 'daily_leave',
            Leave.status == 'active'
        ).count()

        # حساب إجمالي الساعات والأيام
        hourly_leaves_list = query.filter(
            Leave.leave_type == 'hourly_leave',
            Leave.status == 'active'
        ).all()
        
        daily_leaves_list = query.filter(
            Leave.leave_type == 'daily_leave',
            Leave.status == 'active'
        ).all()

        total_hours = sum(leave.hours or 0 for leave in hourly_leaves_list)
        total_days = sum(leave.days or 0 for leave in daily_leaves_list)

        return jsonify({
            'overview': {
                'total': total_leaves,
                'active': active_leaves,
                'cancelled': cancelled_leaves,
                'expired': expired_leaves
            },
            'by_type': {
                'hourly_leave': {
                    'total': hourly_leaves,
                    'active': hourly_leaves_active,
                    'total_hours': total_hours
                },
                'daily_leave': {
                    'total': daily_leaves,
                    'active': daily_leaves_active,
                    'total_days': total_days
                }
            },
            'period': {
                'start_date': start_date.strftime('%Y-%m-%d') if start_date else None,
                'end_date': end_date.strftime('%Y-%m-%d') if end_date else None
            }
        }), 200

    except Exception as e:
        return jsonify({'message': f'حدث خطأ أثناء جلب إحصائيات الإجازات: {str(e)}'}), 500
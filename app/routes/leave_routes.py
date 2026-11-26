from flask import Blueprint, request, jsonify
from app import db
from app.utils import token_required
from app.models.leave import Leave
from app.models.user import User
from app.models.employee import Employee
from app.services.employee_notifications import notify_leave_added
from datetime import datetime, date, timedelta
import traceback

leave_bp = Blueprint('leave', __name__)

_ADMIN_LIKE = {
    'super_admin',
    'branch_head',
    'branch_deputy',
    'department_head',
    'department_deputy',
}


def _can_manage_leave(user, leave):
    """سوبر أدمن أو رئيس/نائب ضمن نطاق الموظف."""
    if not user:
        return False
    if user.is_super_admin():
        return True
    if user.user_type not in _ADMIN_LIKE:
        return False
    accessible_ids = [e.id for e in user.get_accessible_employees()]
    return leave.employee_id in accessible_ids


def _sync_transaction_details_from_leave(leave):
    """مزامنة تفاصيل المعاملة المرتبطة بعد تعديل نطاق الإجازة."""
    if not leave.transaction_id or not leave.transaction:
        return
    details = leave.transaction.get_details() or {}
    if leave.leave_type == 'daily_leave':
        details['start_date'] = leave.start_date.isoformat() if leave.start_date else None
        details['end_date'] = leave.end_date.isoformat() if leave.end_date else None
        details['days'] = leave.days
    elif leave.leave_type == 'hourly_leave':
        details['leave_date'] = leave.start_date.isoformat() if leave.start_date else None
        details['hours'] = leave.hours
        if leave.start_time:
            details['start_time'] = leave.start_time.strftime('%H:%M:%S')
        if leave.end_time:
            details['end_time'] = leave.end_time.strftime('%H:%M:%S')
    leave.transaction.set_details(details)


# =========================== إنشاء إجازة جديدة ===========================

def _parse_leave_date(value, field_name='start_date'):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return datetime.strptime(value[:10], '%Y-%m-%d').date()
    raise ValueError(f'تنسيق {field_name} غير صحيح')


def _normalize_daily_ranges(data):
    """
    يحوّل الطلب إلى قائمة نطاقات يومية.
    يدعم:
    - date_ranges: [{start_date, end_date}] أو [{start_date, days}]
    - أو الحقول القديمة start_date + days / end_date (نطاق واحد)
    """
    ranges = data.get('date_ranges') or data.get('ranges')
    normalized = []

    if ranges:
        if not isinstance(ranges, list) or not ranges:
            raise ValueError('date_ranges يجب أن تكون قائمة غير فارغة')
        for idx, item in enumerate(ranges, start=1):
            if not isinstance(item, dict):
                raise ValueError(f'النطاق رقم {idx} غير صالح')
            if not item.get('start_date'):
                raise ValueError(f'start_date مطلوب في النطاق رقم {idx}')
            start = _parse_leave_date(item['start_date'], 'start_date')
            if item.get('end_date'):
                end = _parse_leave_date(item['end_date'], 'end_date')
            elif item.get('days'):
                days = int(item['days'])
                if days < 1:
                    raise ValueError(f'days غير صالح في النطاق رقم {idx}')
                end = start + timedelta(days=days - 1)
            else:
                raise ValueError(f'end_date أو days مطلوب في النطاق رقم {idx}')
            if end < start:
                raise ValueError(f'تاريخ النهاية قبل البداية في النطاق رقم {idx}')
            days = (end - start).days + 1
            normalized.append({'start_date': start, 'end_date': end, 'days': days})
        return normalized

    if not data.get('start_date'):
        raise ValueError('start_date مطلوب')
    start = _parse_leave_date(data['start_date'], 'start_date')
    if data.get('end_date'):
        end = _parse_leave_date(data['end_date'], 'end_date')
        if end < start:
            raise ValueError('تاريخ النهاية قبل تاريخ البداية')
        days = (end - start).days + 1
    elif data.get('days'):
        days = int(data['days'])
        if days < 1:
            raise ValueError('عدد الأيام مطلوب للإجازة اليومية')
        end = start + timedelta(days=days - 1) if days > 1 else start
    else:
        raise ValueError('عدد الأيام أو تاريخ النهاية مطلوب للإجازة اليومية')
    return [{'start_date': start, 'end_date': end, 'days': days}]


@leave_bp.route('/api/leaves', methods=['POST'])
@token_required
def create_leave(user):
    try:
        data = request.get_json()
        
        # التحقق من البيانات المطلوبة المشتركة
        for field in ('employee_id', 'leave_type', 'reason'):
            if not data.get(field):
                return jsonify({'message': f'الحقل {field} مطلوب'}), 400
        reason = str(data.get('reason') or '').strip()
        if not reason:
            return jsonify({'message': 'سبب الإجازة مطلوب'}), 400
        data['reason'] = reason

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

        # ——— إجازة يومية: دعم نطاق واحد أو عدة نطاقات متفرقة بنفس الطلب ———
        if data['leave_type'] == 'daily_leave':
            try:
                ranges = _normalize_daily_ranges(data)
            except ValueError as ve:
                return jsonify({'message': str(ve)}), 400

            created = []
            for rng in ranges:
                leave = Leave(
                    employee_id=data['employee_id'],
                    leave_type='daily_leave',
                    start_date=rng['start_date'],
                    end_date=rng['end_date'],
                    days=rng['days'],
                    reason=data['reason'],
                    notes=data.get('notes') or None,
                    status=data.get('status') or 'active',
                    transaction_id=None,
                )
                db.session.add(leave)
                created.append(leave)

            db.session.commit()

            for leave in created:
                try:
                    notify_leave_added(leave, sender_id=current_user.id)
                except Exception as notify_err:
                    print(f"notify_leave_added failed: {notify_err}")

            leaves_payload = [leave.get_leave_details() for leave in created]
            if len(leaves_payload) == 1:
                return jsonify({
                    'message': 'تم إنشاء الإجازة بنجاح',
                    'leave': leaves_payload[0],
                    'leaves': leaves_payload,
                    'created_count': 1,
                }), 201

            return jsonify({
                'message': f'تم إنشاء {len(leaves_payload)} إجازات يومية بنجاح',
                'leaves': leaves_payload,
                'created_count': len(leaves_payload),
                # للتوافق مع عملاء يتوقعون leave مفرداً
                'leave': leaves_payload[0],
            }), 201

        # ——— إجازة ساعية (سلوك قديم دون تغيير) ———
        if not data.get('start_date'):
            return jsonify({'message': 'الحقل start_date مطلوب'}), 400

        leave_data = {
            'employee_id': data['employee_id'],
            'leave_type': data['leave_type'],
            'start_date': _parse_leave_date(data['start_date'], 'start_date'),
            'reason': data['reason'],
            'notes': data.get('notes') or None,
            'status': data.get('status') or 'active',
            'transaction_id': None,
        }

        if not data.get('hours'):
            return jsonify({'message': 'الحقل hours مطلوب للإجازة الساعية'}), 400

        leave_data['hours'] = int(data['hours'])

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

        leave = Leave(**leave_data)
        db.session.add(leave)
        db.session.commit()

        try:
            notify_leave_added(leave, sender_id=current_user.id)
        except Exception as notify_err:
            print(f"notify_leave_added failed: {notify_err}")

        return jsonify({
            'message': 'تم إنشاء الإجازة بنجاح',
            'leave': leave.get_leave_details()
        }), 201
    
    except Exception as e:
        db.session.rollback()
        print(f"Error creating leave: {str(e)}")
        traceback.print_exc()
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
        if not _can_manage_leave(current_user, leave):
            return jsonify({'message': 'ليس لديك صلاحية لتحديث هذه الإجازة'}), 403

        data = request.get_json() or {}

        # تحديث الحقول المسموحة (بما فيها المرتبطة بمعاملة معتمدة — لتعديل النطاق أو الإلغاء)
        if 'reason' in data:
            reason = str(data.get('reason') or '').strip()
            if not reason:
                return jsonify({'message': 'سبب الإجازة مطلوب'}), 400
            leave.reason = reason
        if 'notes' in data:
            leave.notes = data['notes']
        if 'status' in data and data['status'] in ['active', 'cancelled', 'expired']:
            leave.status = data['status']

        # تحديث البيانات الخاصة بنوع الإجازة
        if leave.leave_type == 'daily_leave':
            if 'start_date' in data and data['start_date']:
                leave.start_date = _parse_leave_date(data['start_date'], 'start_date')
            if 'end_date' in data and data['end_date']:
                end_date = _parse_leave_date(data['end_date'], 'end_date')
                if end_date < leave.start_date:
                    return jsonify({'message': 'تاريخ النهاية قبل تاريخ البداية'}), 400
                leave.end_date = end_date
                leave.days = (end_date - leave.start_date).days + 1
            elif 'days' in data:
                days = int(data['days'])
                if days < 1:
                    return jsonify({'message': 'عدد الأيام يجب أن يكون 1 على الأقل'}), 400
                leave.days = days
                end_date = leave.start_date + timedelta(days=days - 1) if days > 1 else leave.start_date
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
        _sync_transaction_details_from_leave(leave)
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
        if not _can_manage_leave(current_user, leave):
            return jsonify({'message': 'ليس لديك صلاحية لحذف هذه الإجازة'}), 403

        # يُسمح بالحذف حتى لو مرتبطة بمعاملة معتمدة لإزالة تأثيرها من التقارير.
        # سجل المعاملة يبقى للمراجعة التاريخية.
        db.session.delete(leave)
        db.session.commit()

        return jsonify({
            'message': 'تم حذف الإجازة بنجاح وإزالة تأثيرها من التقارير'
        }), 200

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
        if not _can_manage_leave(current_user, leave):
            return jsonify({'message': 'ليس لديك صلاحية لتحديث حالة هذه الإجازة'}), 403

        data = request.get_json() or {}
        new_status = data.get('status')

        if new_status not in ['active', 'cancelled', 'expired']:
            return jsonify({'message': 'حالة الإجازة غير صالحة'}), 400

        leave.status = new_status
        leave.updated_at = datetime.now()

        db.session.commit()

        effect_note = (
            ' — لن تظهر في تقارير الحضور كإجازة'
            if new_status == 'cancelled'
            else ''
        )
        return jsonify({
            'message': f'تم تحديث حالة الإجازة إلى {new_status}{effect_note}',
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
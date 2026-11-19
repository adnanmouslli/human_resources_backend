"""
تقييم صلاحية دخول الموظف للتطبيق.

السياسة الجديدة (حسب إعداد المستخدم):
- إذا app_access_require_checkin = False → مسموح دائماً (موظفو العمل عن بعد / بصمة من التطبيق).
- إذا = True → مسموح فقط بوجود جلسة حضور مفتوحة (بصمة دخول بدون خروج).
  قبل الدخول أو بعد الخروج → التطبيق مقفول.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Optional

from app.models.attendance import Attendance
from app.models.employee import Employee


def _format_dt(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat(timespec='seconds') if dt else None


def _format_time(t) -> Optional[str]:
    if t is None:
        return None
    try:
        return t.strftime('%H:%M')
    except Exception:
        return str(t)


def _base_payload(now: datetime, **extra) -> dict[str, Any]:
    payload = {
        'allowed': True,
        'enforced': False,
        'require_checkin': False,
        'work_system': None,
        'shift_id': None,
        'shift_name': None,
        'is_working_day': None,
        'has_check_in': False,
        'has_check_out': False,
        'check_in_time': None,
        'check_out_time': None,
        'window_start': None,
        'window_end': None,
        'window_start_time': None,
        'window_end_time': None,
        'checked_at': _format_dt(now),
        'message': 'الوصول مسموح',
        'reason': 'ok',
    }
    payload.update(extra)
    return payload


def _find_open_attendance(employee_id: int, today: date) -> Optional[Attendance]:
    """جلسة مفتوحة: دخول بدون خروج (اليوم أو أمس للورديات الليلية)."""
    yesterday = today - timedelta(days=1)
    return (
        Attendance.query.filter(
            Attendance.empId == employee_id,
            Attendance.createdAt.in_([today, yesterday]),
            Attendance.checkInTime.isnot(None),
            Attendance.checkOutTime.is_(None),
        )
        .order_by(Attendance.createdAt.desc(), Attendance.id.desc())
        .first()
    )


def _today_attendance_summary(employee_id: int, today: date) -> dict[str, Any]:
    records = (
        Attendance.query.filter(
            Attendance.empId == employee_id,
            Attendance.createdAt == today,
        )
        .order_by(Attendance.id.asc())
        .all()
    )
    check_ins = [r.checkInTime for r in records if r.checkInTime]
    check_outs = [r.checkOutTime for r in records if r.checkOutTime]
    return {
        'has_check_in': len(check_ins) > 0,
        'has_check_out': len(check_outs) > 0,
        'check_in_time': _format_time(check_ins[0]) if check_ins else None,
        'check_out_time': _format_time(check_outs[-1]) if check_outs else None,
    }


def evaluate_attendance_app_access(employee: Employee, user=None, at: Optional[datetime] = None) -> dict[str, Any]:
    """تقييم الوصول حسب بصمة الدخول/الخروج وإعداد المستخدم."""
    now = at or datetime.now()
    today = now.date()

    require = bool(getattr(user, 'app_access_require_checkin', False)) if user is not None else False
    work_system = (getattr(employee, 'work_system', None) or '').strip().lower() or None

    base = _base_payload(
        now,
        require_checkin=require,
        work_system=work_system,
        shift_id=getattr(employee, 'shift_id', None),
        enforced=require,
    )

    if not require:
        base['message'] = 'قيد بصمة الدخول غير مفعّل لهذا الحساب'
        base['reason'] = 'setting_disabled'
        return base

    summary = _today_attendance_summary(employee.id, today)
    base.update(summary)

    open_att = _find_open_attendance(employee.id, today)
    if open_att is not None:
        base.update({
            'allowed': True,
            'has_check_in': True,
            'has_check_out': False,
            'check_in_time': _format_time(open_att.checkInTime),
            'check_out_time': None,
            'message': 'تم تسجيل بصمة الدخول — يمكنك استخدام التطبيق',
            'reason': 'checked_in',
        })
        return base

    # لا توجد جلسة مفتوحة
    if summary['has_check_out'] or summary['has_check_in']:
        base.update({
            'allowed': False,
            'message': 'تم تسجيل بصمة الخروج — لا يمكنك استخدام التطبيق الآن.',
            'reason': 'checked_out',
        })
        return base

    # ربما خرج أمس في وردية ليلية وانتهت الجلسة
    yesterday = today - timedelta(days=1)
    y_open_closed = (
        Attendance.query.filter(
            Attendance.empId == employee.id,
            Attendance.createdAt == yesterday,
            Attendance.checkInTime.isnot(None),
            Attendance.checkOutTime.isnot(None),
        ).count()
        > 0
    )
    # لا جلسة مفتوحة ولا دخول اليوم
    base.update({
        'allowed': False,
        'message': 'يجب تسجيل بصمة الدخول أولاً لاستخدام التطبيق.',
        'reason': 'no_checkin',
    })
    if y_open_closed and not summary['has_check_in']:
        # لا يغيّر الرسالة — ما زال يحتاج دخول جديد لليوم
        pass
    return base


# توافق مع الاسم القديم في المسارات
def evaluate_shift_access(employee: Employee, at: Optional[datetime] = None, user=None) -> dict[str, Any]:
    return evaluate_attendance_app_access(employee, user=user, at=at)


def evaluate_user_app_access(user, at: Optional[datetime] = None) -> dict[str, Any]:
    """تقييم وصول مستخدم التطبيق."""
    now = at or datetime.now()
    if user is None:
        return _base_payload(
            now,
            allowed=False,
            message='المستخدم غير موجود',
            reason='no_user',
        )

    user_type = (getattr(user, 'user_type', None) or '').strip().lower()
    manager_types = {
        'branch_head', 'branch_deputy',
        'department_head', 'department_deputy',
        'super_admin', 'dev',
    }
    if user_type in manager_types or (hasattr(user, 'is_super_admin') and user.is_super_admin()):
        return _base_payload(
            now,
            message='حساب إداري — قيد الوصول غير مفعّل',
            reason='manager_exempt',
        )

    employee = getattr(user, 'employee', None)
    if employee is None and getattr(user, 'employee_id', None):
        employee = Employee.query.get(user.employee_id)

    if employee is None:
        return _base_payload(
            now,
            message='لا يوجد موظف مرتبط — الوصول مسموح',
            reason='no_employee',
        )

    return evaluate_attendance_app_access(employee, user=user, at=now)

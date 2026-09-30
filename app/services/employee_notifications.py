# app/services/employee_notifications.py
# إشعارات الموظف نفسه: عند إضافة سلفة/مكافأة/جزاء/إجازة له، أو اعتماد غياب أو تقييم شهري.
# تُحفظ في جدول الإشعارات وتصل للجوال فوراً عبر NotificationService.

import logging
from typing import Optional

from app.models.employee import Employee
from app.models.notification import NotificationType, NotificationPriority
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


def _fmt_amount(value) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f'{v:.0f}' if v == int(v) else f'{v:.2f}'


def notify_employee(
    employee_id: int,
    title: str,
    message: str,
    notification_type: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    sender_id: Optional[int] = None,
    priority: str = NotificationPriority.MEDIUM.value,
    extra_data: Optional[dict] = None,
):
    """إرسال إشعار لحساب المستخدم المرتبط بالموظف (إن وجد). لا يرمي استثناءات."""
    try:
        employee = Employee.query.get(employee_id)
        account = getattr(employee, 'user_account', None) if employee else None
        if not account or not account.is_active:
            return None
        # لا داعي لإشعار الشخص بإجراء قام به بنفسه
        if sender_id is not None and account.id == sender_id:
            return None
        return NotificationService.send_notification(
            recipient_id=account.id,
            title=title,
            message=' '.join(message.split()),
            notification_type=notification_type,
            priority=priority,
            sender_id=sender_id,
            entity_type=entity_type,
            entity_id=entity_id,
            extra_data=extra_data,
        )
    except Exception as e:
        logger.error('فشل إشعار الموظف %s: %s', employee_id, e)
        return None


# ─────────────────────────── السلف / المكافآت / الجزاءات ───────────────────────────

def notify_advance_added(advance, sender_id=None):
    notify_employee(
        advance.employee_id,
        'تمت إضافة سلفة لك',
        f'تم تسجيل سلفة لك بقيمة {_fmt_amount(advance.amount)} ج.م.',
        NotificationType.ADVANCE.value,
        entity_type='advance', entity_id=advance.id, sender_id=sender_id,
    )


def notify_reward_added(reward, sender_id=None):
    notify_employee(
        reward.employee_id,
        'مكافأة جديدة 🎉',
        f'تمت إضافة مكافأة لك بقيمة {_fmt_amount(reward.amount)} ج.م.',
        NotificationType.REWARD.value,
        entity_type='reward', entity_id=reward.id, sender_id=sender_id,
    )


def notify_penalty_added(penalty, sender_id=None):
    notes = f' الملاحظات: {penalty.notes}' if getattr(penalty, 'notes', None) else ''
    notify_employee(
        penalty.employee_id,
        'تم تسجيل جزاء',
        f'تم تسجيل جزاء عليك بقيمة {_fmt_amount(penalty.amount)} ج.م.{notes}',
        NotificationType.PENALTY.value,
        entity_type='penalty', entity_id=penalty.id, sender_id=sender_id,
        priority=NotificationPriority.HIGH.value,
    )


# ─────────────────────────── الإجازات ───────────────────────────

def notify_leave_added(leave, sender_id=None):
    if leave.leave_type == 'daily_leave':
        body = f'تم تسجيل إجازة يومية لك لمدة {leave.days} يوم من {leave.start_date}'
        if leave.end_date and leave.end_date != leave.start_date:
            body += f' إلى {leave.end_date}'
    else:
        body = f'تم تسجيل إجازة ساعية لك لمدة {leave.hours} ساعة بتاريخ {leave.start_date}'
    notify_employee(
        leave.employee_id,
        'تم تسجيل إجازة لك',
        body + '.',
        NotificationType.LEAVE.value,
        entity_type='leave', entity_id=leave.id, sender_id=sender_id,
    )


# ─────────────────────────── الغياب ───────────────────────────

def notify_absence_approved(absence_transaction, deduction_total: float, sender_id=None):
    body = f'تم اعتماد غيابك بتاريخ {absence_transaction.absence_date}'
    if deduction_total and deduction_total > 0:
        body += f' مع خصم {_fmt_amount(deduction_total)}'
    notify_employee(
        absence_transaction.employee_id,
        'اعتماد غياب',
        body + '.',
        NotificationType.ABSENCE.value,
        entity_type='absence', entity_id=absence_transaction.id, sender_id=sender_id,
        priority=NotificationPriority.HIGH.value,
    )


# ─────────────────────────── تقييم الأداء (KPI) ───────────────────────────

_GRADE_LABELS = {
    'excellent': 'ممتاز', 'good': 'جيد', 'average': 'متوسط',
    'poor': 'ضعيف', 'not_evaluated': 'لم يقيّم',
}


def notify_kpi_month_finalized(summary, sender_id=None):
    """عند اعتماد التقييم الشهري (فقط إذا كان عرض النتائج للموظف مفعلاً)."""
    from app.models.kpi import KpiSettings
    if not KpiSettings.get().allow_self_view:
        return
    grade = _GRADE_LABELS.get(summary.performance_grade, '')
    notify_employee(
        summary.employee_id,
        'تم اعتماد تقييمك الشهري',
        f'تقييمك لشهر {summary.month}/{summary.year}: '
        f'{_fmt_amount(summary.monthly_percentage or 0)}% ({grade}).',
        NotificationType.KPI.value,
        entity_type='kpi_summary', entity_id=summary.id, sender_id=sender_id,
        extra_data={'year': summary.year, 'month': summary.month},
    )

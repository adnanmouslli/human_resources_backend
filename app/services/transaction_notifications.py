# app/services/transaction_notifications.py
# إشعارات نظام المعاملات (سلفة، مكافأة، جزاء، إجازات)
# تُحفظ في جدول الإشعارات وتُرسل كإشعار فوري للجوال عبر NotificationService

import logging

from app.models.notification import NotificationType, NotificationPriority
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

_TYPE_LABELS = {
    'advance': 'سلفة',
    'reward': 'مكافأة',
    'penalty': 'جزاء',
    'hourly_leave': 'إجازة ساعية',
    'daily_leave': 'إجازة يومية',
}

# ربط نوع المعاملة بنوع الإشعار (لاحترام إعدادات المستخدم)
_NOTIFICATION_TYPES = {
    'advance': NotificationType.ADVANCE.value,
    'reward': NotificationType.REWARD.value,
    'penalty': NotificationType.PENALTY.value,
    'hourly_leave': NotificationType.LEAVE.value,
    'daily_leave': NotificationType.LEAVE.value,
}


def _summary(transaction) -> str:
    """وصف مختصر لتفاصيل المعاملة."""
    d = transaction.get_details() or {}
    t = transaction.transaction_type
    if t in ('advance', 'reward', 'penalty') and d.get('amount') is not None:
        amount = float(d['amount'])
        amount_str = f'{amount:.0f}' if amount == int(amount) else f'{amount:.2f}'
        return f'بقيمة {amount_str} ج.م'
    if t == 'hourly_leave':
        return f'لمدة {d.get("hours")} ساعة بتاريخ {d.get("leave_date")}'
    if t == 'daily_leave':
        return f'لمدة {d.get("days")} يوم من {d.get("start_date")}'
    return ''


def _extra(transaction):
    return {
        'transaction_id': transaction.id,
        'transaction_number': transaction.transaction_number,
        'transaction_type': transaction.transaction_type,
        'employee_id': transaction.employee_id,
    }


def notify_transaction_created(transaction, employee, requester, approvers):
    """
    إشعار كل من يجب أن يوافق على المعاملة (رؤساء ونواب الفرع/القسم والمدير العام)
    ما عدا منشئ الطلب نفسه.
    """
    try:
        label = _TYPE_LABELS.get(transaction.transaction_type, 'معاملة')
        summary = _summary(transaction)

        is_self_request = requester.employee_id == employee.id
        if is_self_request:
            title = f'طلب {label} جديد'
            message = f'قام الموظف {employee.full_name} بطلب {label} {summary}، بانتظار موافقتك.'
        else:
            requester_name = requester.employee.full_name if requester.employee else requester.username
            title = f'معاملة {label} جديدة'
            message = f'أنشأ {requester_name} معاملة {label} للموظف {employee.full_name} {summary}، بانتظار موافقتك.'

        recipient_ids = {a.id for a in approvers if a.id != requester.id}
        NotificationService.send_notification_to_multiple(
            recipient_ids=list(recipient_ids),
            title=title,
            message=' '.join(message.split()),
            notification_type=_NOTIFICATION_TYPES.get(transaction.transaction_type, NotificationType.TRANSACTION.value),
            priority=NotificationPriority.HIGH.value,
            sender_id=requester.id,
            entity_type='transaction',
            entity_id=transaction.id,
            extra_data=_extra(transaction),
        )
    except Exception as e:
        logger.error('فشل إرسال إشعار إنشاء المعاملة %s: %s', transaction.id, e)


def notify_transaction_decided(transaction, actor, approved: bool, reason=None):
    """
    إشعار منشئ الطلب والموظف صاحب المعاملة عند اكتمال الموافقة أو الرفض.
    """
    try:
        label = _TYPE_LABELS.get(transaction.transaction_type, 'معاملة')
        employee = transaction.employee

        if approved:
            title = f'تمت الموافقة على {label}'
            message = f'تمت الموافقة على طلب {label} رقم {transaction.transaction_number} {_summary(transaction)}.'
            priority = NotificationPriority.MEDIUM.value
        else:
            title = f'تم رفض {label}'
            message = f'تم رفض طلب {label} رقم {transaction.transaction_number}.'
            if reason:
                message += f' السبب: {reason}'
            priority = NotificationPriority.HIGH.value

        recipient_ids = {transaction.requested_by}
        if employee is not None and getattr(employee, 'user_account', None):
            recipient_ids.add(employee.user_account.id)
        recipient_ids.discard(actor.id)
        recipient_ids.discard(None)

        NotificationService.send_notification_to_multiple(
            recipient_ids=list(recipient_ids),
            title=title,
            message=' '.join(message.split()),
            notification_type=_NOTIFICATION_TYPES.get(transaction.transaction_type, NotificationType.TRANSACTION.value),
            priority=priority,
            sender_id=actor.id,
            entity_type='transaction',
            entity_id=transaction.id,
            extra_data=_extra(transaction),
        )
    except Exception as e:
        logger.error('فشل إرسال إشعار قرار المعاملة %s: %s', transaction.id, e)

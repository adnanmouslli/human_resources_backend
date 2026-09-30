# app/services/transaction_notifications.py
# إشعارات نظام المعاملات (سلفة، مكافأة، جزاء، إجازات)
# تُحفظ في جدول الإشعارات وتُرسل كإشعار فوري للجوال عبر NotificationService

import logging

from app import db

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
        db.session.rollback()
        logger.error('فشل إرسال إشعار إنشاء المعاملة %s: %s', transaction.id, e)


_ADDED_FOR_EMPLOYEE = {
    'advance': 'تمت إضافة سلفة لك',
    'reward': 'مكافأة جديدة',
    'penalty': 'تم تسجيل جزاء',
    'hourly_leave': 'تم تسجيل إجازة لك',
    'daily_leave': 'تم تسجيل إجازة لك',
}


def notify_transaction_decided(transaction, actor, approved: bool, reason=None):
    """
    عند اكتمال الموافقة أو الرفض:
    - طلب قدّمه الموظف لنفسه: يُشعَر الموظف بالقبول أو الرفض (مع السبب).
    - معاملة أنشأها مدير للموظف: يُشعَر الموظف عند الاعتماد فقط (تمت إضافة ... لك)،
      ويُشعَر المدير منشئ المعاملة بالنتيجة في الحالتين.
    """
    try:
        label = _TYPE_LABELS.get(transaction.transaction_type, 'معاملة')
        n_type = _NOTIFICATION_TYPES.get(transaction.transaction_type, NotificationType.TRANSACTION.value)
        summary = _summary(transaction)
        number = transaction.transaction_number

        employee = transaction.employee
        employee_user = getattr(employee, 'user_account', None) if employee else None
        employee_user_id = employee_user.id if employee_user else None
        is_self_request = employee_user_id is not None and employee_user_id == transaction.requested_by

        messages = {}  # recipient_id -> (title, message, priority)

        if approved:
            if is_self_request:
                messages[employee_user_id] = (
                    f'تمت الموافقة على طلب {label}',
                    f'تمت الموافقة على طلبك ({label}) رقم {number} {summary}.',
                    NotificationPriority.MEDIUM.value,
                )
            else:
                if employee_user_id:
                    messages[employee_user_id] = (
                        _ADDED_FOR_EMPLOYEE.get(transaction.transaction_type, f'{label} جديدة'),
                        f'تم اعتماد {label} لك {summary}.',
                        NotificationPriority.HIGH.value if transaction.transaction_type == 'penalty'
                        else NotificationPriority.MEDIUM.value,
                    )
                messages[transaction.requested_by] = (
                    f'تم اعتماد معاملة {label}',
                    f'تم اعتماد معاملة {label} رقم {number} للموظف {employee.full_name if employee else ""}.',
                    NotificationPriority.MEDIUM.value,
                )
        else:
            reason_txt = f' السبب: {reason}' if reason else ''
            if is_self_request:
                messages[employee_user_id] = (
                    f'تم رفض طلب {label}',
                    f'تم رفض طلبك ({label}) رقم {number}.{reason_txt}',
                    NotificationPriority.HIGH.value,
                )
            else:
                messages[transaction.requested_by] = (
                    f'تم رفض معاملة {label}',
                    f'تم رفض معاملة {label} رقم {number} للموظف {employee.full_name if employee else ""}.{reason_txt}',
                    NotificationPriority.MEDIUM.value,
                )

        for recipient_id, (title, message, priority) in messages.items():
            if not recipient_id or recipient_id == actor.id:
                continue
            NotificationService.send_notification(
                recipient_id=recipient_id,
                title=title,
                message=' '.join(message.split()),
                notification_type=n_type,
                priority=priority,
                sender_id=actor.id,
                entity_type='transaction',
                entity_id=transaction.id,
                extra_data=_extra(transaction),
            )
    except Exception as e:
        db.session.rollback()
        logger.error('فشل إرسال إشعار قرار المعاملة %s: %s', transaction.id, e)

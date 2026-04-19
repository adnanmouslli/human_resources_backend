# app/recruitment/notifications.py
# مساعد الإشعارات الداخلية لقسم التوظيف

from app import db
from app.models.notification import Notification, NotificationType, NotificationPriority
from app.models.user import User


def send_internal_notification(user_ids, title, body, notif_type='recruitment', related_id=None):
    """
    إرسال إشعار داخلي لقائمة من المستخدمين.

    user_ids  : list[int] - معرفات المستخدمين
    title     : str       - عنوان الإشعار
    body      : str       - نص الإشعار
    notif_type: str       - نوع الإشعار (يُستخدم الـ GENERAL إذا لم يُعرَّف)
    related_id: int|None  - معرف الكيان المرتبط
    """
    if not user_ids:
        return []

    # تحديد نوع الإشعار
    notification_type_val = NotificationType.GENERAL.value

    created = []
    for uid in set(user_ids):
        user = User.query.get(uid)
        if not user or not user.is_active:
            continue
        notif = Notification(
            recipient_id=uid,
            sender_id=None,
            title=title,
            message=body,
            notification_type=notification_type_val,
            priority=NotificationPriority.HIGH.value,
            entity_type='recruitment',
            entity_id=related_id,
        )
        db.session.add(notif)
        created.append(notif)

    return created


def get_super_admin_ids():
    """إرجاع معرفات كل super_admin نشطين"""
    admins = User.query.filter_by(user_type='super_admin', is_active=True).all()
    return [u.id for u in admins]


def get_branch_manager_ids(branch_id):
    """إرجاع معرفات مدراء الفرع (branch_head) المرتبطين بالفرع المعطى"""
    if not branch_id:
        return []
    from app.models.user import UserBranchHead
    records = UserBranchHead.query.filter_by(branch_id=branch_id, role_type='head').all()
    return [r.user_id for r in records]

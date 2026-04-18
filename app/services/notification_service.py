# app/services/notification_service.py
# خدمة الإشعارات - نظام إرسال وإدارة الإشعارات المتكامل

from datetime import datetime
from typing import List, Optional, Dict, Any
from app import db
from app.models.notification import Notification, NotificationSetting, NotificationType, NotificationPriority
from app.models.user import User, UserDepartmentHead, UserBranchHead
from app.models.department import Department
from app.models.branch import Branch
from app.models.employee import Employee

class NotificationService:
    """
    خدمة الإشعارات المركزية
    توفر واجهة موحدة لإرسال وإدارة الإشعارات
    """
    
    @staticmethod
    def send_notification(
        recipient_id: int,
        title: str,
        message: str,
        notification_type: str = NotificationType.GENERAL.value,
        priority: str = NotificationPriority.MEDIUM.value,
        sender_id: Optional[int] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Notification]:
        """
        إرسال إشعار لمستخدم محدد
        
        Args:
            recipient_id: معرف المستلم
            title: عنوان الإشعار
            message: نص الإشعار
            notification_type: نوع الإشعار
            priority: أولوية الإشعار
            sender_id: معرف المرسل (اختياري)
            entity_type: نوع الكيان المرتبط (اختياري)
            entity_id: معرف الكيان المرتبط (اختياري)
            extra_data: بيانات إضافية بتنسيق JSON (اختياري)
        
        Returns:
            كائن الإشعار المنشأ أو None إذا كان المستخدم قد عطل هذا النوع من الإشعارات
        """
        # التحقق من وجود المستخدم
        recipient = User.query.get(recipient_id)
        if not recipient:
            return None
        
        # التحقق من إعدادات الإشعارات
        settings = NotificationService.get_or_create_settings(recipient_id)
        if not settings.is_type_enabled(notification_type):
            return None
        
        # إنشاء الإشعار
        notification = Notification(
            recipient_id=recipient_id,
            sender_id=sender_id,
            title=title,
            message=message,
            notification_type=notification_type,
            priority=priority,
            entity_type=entity_type,
            entity_id=entity_id,
            extra_data=extra_data
        )
        
        db.session.add(notification)
        db.session.commit()
        
        return notification
    
    @staticmethod
    def send_notification_to_multiple(
        recipient_ids: List[int],
        title: str,
        message: str,
        notification_type: str = NotificationType.GENERAL.value,
        priority: str = NotificationPriority.MEDIUM.value,
        sender_id: Optional[int] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> List[Notification]:
        """
        إرسال إشعار لعدة مستخدمين
        
        Returns:
            قائمة بالإشعارات المنشأة
        """
        notifications = []
        
        for recipient_id in recipient_ids:
            notification = NotificationService.send_notification(
                recipient_id=recipient_id,
                title=title,
                message=message,
                notification_type=notification_type,
                priority=priority,
                sender_id=sender_id,
                entity_type=entity_type,
                entity_id=entity_id,
                extra_data=extra_data
            )
            if notification:
                notifications.append(notification)
        
        return notifications
    
    @staticmethod
    def notify_department_heads(
        department_id: int,
        title: str,
        message: str,
        notification_type: str = NotificationType.GENERAL.value,
        priority: str = NotificationPriority.MEDIUM.value,
        sender_id: Optional[int] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        extra_data: Optional[Dict[str, Any]] = None,
        include_deputies: bool = True
    ) -> List[Notification]:
        """
        إرسال إشعار لرؤساء قسم معين (والنواب إذا تم تحديده)
        
        Args:
            department_id: معرف القسم
            title: عنوان الإشعار
            message: نص الإشعار
            notification_type: نوع الإشعار
            priority: أولوية الإشعار
            sender_id: معرف المرسل
            entity_type: نوع الكيان المرتبط
            entity_id: معرف الكيان المرتبط
            extra_data: بيانات إضافية
            include_deputies: هل يشمل النواب؟
        
        Returns:
            قائمة بالإشعارات المرسلة
        """
        notifications = []
        
        # الحصول على رؤساء القسم
        heads = UserDepartmentHead.query.filter_by(
            department_id=department_id,
            role_type='head'
        ).all()
        
        head_ids = [h.user_id for h in heads]
        
        # الحصول على النواب إذا كان مطلوباً
        deputy_ids = []
        if include_deputies:
            deputies = UserDepartmentHead.query.filter_by(
                department_id=department_id,
                role_type='deputy'
            ).all()
            deputy_ids = [d.user_id for d in deputies]
        
        # دمج القائمتين
        all_recipient_ids = list(set(head_ids + deputy_ids))
        
        for recipient_id in all_recipient_ids:
            notification = NotificationService.send_notification(
                recipient_id=recipient_id,
                title=title,
                message=message,
                notification_type=notification_type,
                priority=priority,
                sender_id=sender_id,
                entity_type=entity_type,
                entity_id=entity_id,
                extra_data=extra_data
            )
            if notification:
                notifications.append(notification)
        
        return notifications
    
    @staticmethod
    def notify_branch_heads(
        branch_id: int,
        title: str,
        message: str,
        notification_type: str = NotificationType.GENERAL.value,
        priority: str = NotificationPriority.MEDIUM.value,
        sender_id: Optional[int] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        extra_data: Optional[Dict[str, Any]] = None,
        include_deputies: bool = True
    ) -> List[Notification]:
        """
        إرسال إشعار لرؤساء فرع معين (والنواب إذا تم تحديده)
        
        Args:
            branch_id: معرف الفرع
            title: عنوان الإشعار
            message: نص الإشعار
            notification_type: نوع الإشعار
            priority: أولوية الإشعار
            sender_id: معرف المرسل
            entity_type: نوع الكيان المرتبط
            entity_id: معرف الكيان المرتبط
            extra_data: بيانات إضافية
            include_deputies: هل يشمل النواب؟
        
        Returns:
            قائمة بالإشعارات المرسلة
        """
        notifications = []
        
        # الحصول على رؤساء الفرع
        heads = UserBranchHead.query.filter_by(
            branch_id=branch_id,
            role_type='head'
        ).all()
        
        head_ids = [h.user_id for h in heads]
        
        # الحصول على النواب إذا كان مطلوباً
        deputy_ids = []
        if include_deputies:
            deputies = UserBranchHead.query.filter_by(
                branch_id=branch_id,
                role_type='deputy'
            ).all()
            deputy_ids = [d.user_id for d in deputies]
        
        # دمج القائمتين
        all_recipient_ids = list(set(head_ids + deputy_ids))
        
        for recipient_id in all_recipient_ids:
            notification = NotificationService.send_notification(
                recipient_id=recipient_id,
                title=title,
                message=message,
                notification_type=notification_type,
                priority=priority,
                sender_id=sender_id,
                entity_type=entity_type,
                entity_id=entity_id,
                extra_data=extra_data
            )
            if notification:
                notifications.append(notification)
        
        return notifications
    
    @staticmethod
    def notify_employee_managers(
        employee_id: int,
        title: str,
        message: str,
        notification_type: str = NotificationType.GENERAL.value,
        priority: str = NotificationPriority.MEDIUM.value,
        sender_id: Optional[int] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        extra_data: Optional[Dict[str, Any]] = None,
        include_deputies: bool = True
    ) -> List[Notification]:
        """
        إرسال إشعار لمديري موظف معين (رئيس القسم والفرع)
        
        Args:
            employee_id: معرف الموظف
            title: عنوان الإشعار
            message: نص الإشعار
            notification_type: نوع الإشعار
            priority: أولوية الإشعار
            sender_id: معرف المرسل
            entity_type: نوع الكيان المرتبط
            entity_id: معرف الكيان المرتبط
            extra_data: بيانات إضافية
            include_deputies: هل يشمل النواب؟
        
        Returns:
            قائمة بالإشعارات المرسلة
        """
        notifications = []
        
        # الحصول على معلومات الموظف
        employee = Employee.query.get(employee_id)
        if not employee:
            return notifications
        
        # إرسال إشعار لرؤساء القسم
        if employee.department_id:
            dept_notifications = NotificationService.notify_department_heads(
                department_id=employee.department_id,
                title=title,
                message=message,
                notification_type=notification_type,
                priority=priority,
                sender_id=sender_id,
                entity_type=entity_type,
                entity_id=entity_id,
                extra_data=extra_data,
                include_deputies=include_deputies
            )
            notifications.extend(dept_notifications)
        
        # إرسال إشعار لرؤساء الفرع
        if employee.branch_id:
            branch_notifications = NotificationService.notify_branch_heads(
                branch_id=employee.branch_id,
                title=title,
                message=message,
                notification_type=notification_type,
                priority=priority,
                sender_id=sender_id,
                entity_type=entity_type,
                entity_id=entity_id,
                extra_data=extra_data,
                include_deputies=include_deputies
            )
            notifications.extend(branch_notifications)
        
        return notifications
    
    @staticmethod
    def notify_all_admins(
        title: str,
        message: str,
        notification_type: str = NotificationType.GENERAL.value,
        priority: str = NotificationPriority.MEDIUM.value,
        sender_id: Optional[int] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> List[Notification]:
        """
        إرسال إشعار لجميع المسؤولين (super_admin, branch_heads, department_heads)
        
        Returns:
            قائمة بالإشعارات المرسلة
        """
        notifications = []
        
        # الحصول على جميع المستخدمين المسؤولين
        admin_types = ['super_admin', 'branch_head', 'department_head', 'branch_deputy', 'department_deputy']
        admins = User.query.filter(User.user_type.in_(admin_types)).all()
        
        for admin in admins:
            notification = NotificationService.send_notification(
                recipient_id=admin.id,
                title=title,
                message=message,
                notification_type=notification_type,
                priority=priority,
                sender_id=sender_id,
                entity_type=entity_type,
                entity_id=entity_id,
                extra_data=extra_data
            )
            if notification:
                notifications.append(notification)
        
        return notifications
    
    @staticmethod
    def get_user_notifications(
        user_id: int,
        is_read: Optional[bool] = None,
        notification_type: Optional[str] = None,
        priority: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Notification]:
        """
        الحصول على إشعارات مستخدم معين
        
        Args:
            user_id: معرف المستخدم
            is_read: فلترة حسب حالة القراءة (True/False/None للكل)
            notification_type: فلترة حسب نوع الإشعار
            priority: فلترة حسب الأولوية
            limit: عدد النتائج
            offset: بداية النتائج
        
        Returns:
            قائمة بالإشعارات
        """
        query = Notification.query.filter_by(recipient_id=user_id)
        
        if is_read is not None:
            query = query.filter_by(is_read=is_read)
        
        if notification_type:
            query = query.filter_by(notification_type=notification_type)
        
        if priority:
            query = query.filter_by(priority=priority)
        
        return query.order_by(Notification.created_at.desc()).offset(offset).limit(limit).all()
    
    @staticmethod
    def get_unread_count(user_id: int) -> int:
        """الحصول على عدد الإشعارات غير المقروءة لمستخدم"""
        return Notification.query.filter_by(
            recipient_id=user_id,
            is_read=False
        ).count()
    
    @staticmethod
    def mark_as_read(notification_id: int, user_id: int) -> bool:
        """
        تعليم إشعار كمقروء
        
        Args:
            notification_id: معرف الإشعار
            user_id: معرف المستخدم (للتحقق من الصلاحية)
        
        Returns:
            True إذا تم التحديث بنجاح، False خلاف ذلك
        """
        notification = Notification.query.filter_by(
            id=notification_id,
            recipient_id=user_id
        ).first()
        
        if notification:
            notification.mark_as_read()
            db.session.commit()
            return True
        
        return False
    
    @staticmethod
    def mark_as_unread(notification_id: int, user_id: int) -> bool:
        """تعليم إشعار كغير مقروء"""
        notification = Notification.query.filter_by(
            id=notification_id,
            recipient_id=user_id
        ).first()
        
        if notification:
            notification.mark_as_unread()
            db.session.commit()
            return True
        
        return False
    
    @staticmethod
    def mark_all_as_read(user_id: int, notification_type: Optional[str] = None) -> int:
        """
        تعليم جميع إشعارات المستخدم كمقروءة
        
        Args:
            user_id: معرف المستخدم
            notification_type: نوع الإشعار (اختياري للتعليم حسب النوع)
        
        Returns:
            عدد الإشعارات المحدثة
        """
        query = Notification.query.filter_by(
            recipient_id=user_id,
            is_read=False
        )
        
        if notification_type:
            query = query.filter_by(notification_type=notification_type)
        
        notifications = query.all()
        
        for notification in notifications:
            notification.mark_as_read()
        
        db.session.commit()
        
        return len(notifications)
    
    @staticmethod
    def delete_notification(notification_id: int, user_id: int) -> bool:
        """حذف إشعار"""
        notification = Notification.query.filter_by(
            id=notification_id,
            recipient_id=user_id
        ).first()
        
        if notification:
            db.session.delete(notification)
            db.session.commit()
            return True
        
        return False
    
    @staticmethod
    def delete_old_notifications(days: int = 30) -> int:
        """
        حذف الإشعارات القديمة (المقروءة فقط)
        
        Args:
            days: عدد الأيام (الإشعارات الأقدم من هذا العدد ستحذف)
        
        Returns:
            عدد الإشعارات المحذوفة
        """
        from datetime import timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        old_notifications = Notification.query.filter(
            Notification.is_read == True,
            Notification.created_at < cutoff_date
        ).all()
        
        count = len(old_notifications)
        
        for notification in old_notifications:
            db.session.delete(notification)
        
        db.session.commit()
        
        return count
    
    @staticmethod
    def get_or_create_settings(user_id: int) -> NotificationSetting:
        """الحصول على إعدادات الإشعارات أو إنشاؤها إذا لم تكن موجودة"""
        settings = NotificationSetting.query.filter_by(user_id=user_id).first()
        
        if not settings:
            settings = NotificationSetting(user_id=user_id)
            db.session.add(settings)
            db.session.commit()
        
        return settings
    
    @staticmethod
    def update_settings(user_id: int, settings_data: Dict[str, Any]) -> NotificationSetting:
        """تحديث إعدادات الإشعارات"""
        settings = NotificationService.get_or_create_settings(user_id)
        
        for key, value in settings_data.items():
            if hasattr(settings, key):
                setattr(settings, key, value)
        
        db.session.commit()
        return settings


# دوال مساعدة للإرسال السريع

def notify_employee_action(
    employee_id: int,
    action_title: str,
    action_message: str,
    notification_type: str = NotificationType.GENERAL.value,
    priority: str = NotificationPriority.MEDIUM.value,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    extra_data: Optional[Dict[str, Any]] = None
) -> List[Notification]:
    """
    إشعار سريع: إعلام مديري الموظف بحدث معين
    
    مثال الاستخدام:
        notify_employee_action(
            employee_id=1,
            action_title="طلب إجازة جديد",
            action_message="قام الموظف أحمد بطلب إجازة جديدة",
            notification_type=NotificationType.LEAVE.value,
            entity_type="leave",
            entity_id=123
        )
    """
    return NotificationService.notify_employee_managers(
        employee_id=employee_id,
        title=action_title,
        message=action_message,
        notification_type=notification_type,
        priority=priority,
        entity_type=entity_type,
        entity_id=entity_id,
        extra_data=extra_data
    )


def notify_department_action(
    department_id: int,
    action_title: str,
    action_message: str,
    notification_type: str = NotificationType.GENERAL.value,
    priority: str = NotificationPriority.MEDIUM.value,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    extra_data: Optional[Dict[str, Any]] = None,
    include_deputies: bool = True
) -> List[Notification]:
    """
    إشعار سريع: إعلام رؤساء قسم بحدث معين
    """
    return NotificationService.notify_department_heads(
        department_id=department_id,
        title=action_title,
        message=action_message,
        notification_type=notification_type,
        priority=priority,
        entity_type=entity_type,
        entity_id=entity_id,
        extra_data=extra_data,
        include_deputies=include_deputies
    )


def notify_branch_action(
    branch_id: int,
    action_title: str,
    action_message: str,
    notification_type: str = NotificationType.GENERAL.value,
    priority: str = NotificationPriority.MEDIUM.value,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    extra_data: Optional[Dict[str, Any]] = None,
    include_deputies: bool = True
) -> List[Notification]:
    """
    إشعار سريع: إعلام رؤساء فرع بحدث معين
    """
    return NotificationService.notify_branch_heads(
        branch_id=branch_id,
        title=action_title,
        message=action_message,
        notification_type=notification_type,
        priority=priority,
        entity_type=entity_type,
        entity_id=entity_id,
        extra_data=extra_data,
        include_deputies=include_deputies
    )

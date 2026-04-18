# app/models/notification.py
# نموذج الإشعارات - نظام إشعارات متكامل ومرن

from app import db
from datetime import datetime
from enum import Enum

class NotificationType(Enum):
    """أنواع الإشعارات"""
    GENERAL = "general"                    # إشعار عام
    ATTENDANCE = "attendance"            # إشعار حضور/غياب
    LEAVE = "leave"                      # إشعار إجازة
    ADVANCE = "advance"                  # إشعار سلفة
    REWARD = "reward"                    # إشعار مكافأة
    PENALTY = "penalty"                  # إشعار جزاء
    TRANSACTION = "transaction"          # إشعار معاملة
    ABSENCE = "absence"                  # إشعار غياب
    PRODUCTION = "production"            # إشعار إنتاج
    SYSTEM = "system"                    # إشعار نظام
    KPI = "kpi"                          # إشعار KPI

class NotificationPriority(Enum):
    """أولويات الإشعارات"""
    LOW = "low"          # منخفضة
    MEDIUM = "medium"    # متوسطة
    HIGH = "high"        # عالية
    URGENT = "urgent"    # عاجلة

class Notification(db.Model):
    """
    نموذج الإشعارات: يمثل الإشعارات المرسلة للمستخدمين
    """
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # معلومات المستلم
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='NO ACTION'), nullable=False)
    
    # معلومات المرسل (يمكن أن يكون null للإشعارات النظامية)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    
    # محتوى الإشعار
    title = db.Column(db.String(200), nullable=False)           # عنوان الإشعار
    message = db.Column(db.Text, nullable=False)                # نص الإشعار
    
    # نوع الإشعار وأولويته
    notification_type = db.Column(db.String(50), default=NotificationType.GENERAL.value)
    priority = db.Column(db.String(20), default=NotificationPriority.MEDIUM.value)
    
    # حالة القراءة
    is_read = db.Column(db.Boolean, default=False)              # هل تم قراءته؟
    read_at = db.Column(db.DateTime, nullable=True)             # وقت القراءة
    
    # معلومات إضافية (للربط بالكيانات الأخرى)
    entity_type = db.Column(db.String(50), nullable=True)       # نوع الكيان المرتبط
    entity_id = db.Column(db.Integer, nullable=True)            # معرف الكيان المرتبط
    
    # بيانات إضافية بتنسيق JSON (لتخزين أي معلومات إضافية)
    extra_data = db.Column(db.JSON, nullable=True)
    
    # تواريخ النظام
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # العلاقات
    recipient = db.relationship(
        'User', 
        foreign_keys=[recipient_id],
        back_populates='notifications',
        lazy='joined'
    )
    
    sender = db.relationship(
        'User', 
        foreign_keys=[sender_id],
        back_populates='sent_notifications',
        lazy='joined'
    )
    
    def __repr__(self):
        return f"<Notification {self.id}: {self.title[:30]}... to User {self.recipient_id}>"
    
    def mark_as_read(self):
        """تعليم الإشعار كمقروء"""
        if not self.is_read:
            self.is_read = True
            self.read_at = datetime.now()
            return True
        return False
    
    def mark_as_unread(self):
        """تعليم الإشعار كغير مقروء"""
        if self.is_read:
            self.is_read = False
            self.read_at = None
            return True
        return False
    
    def to_dict(self, include_sender=False):
        """تحويل الإشعار إلى قاموس"""
        data = {
            'id': self.id,
            'title': self.title,
            'message': self.message,
            'notification_type': self.notification_type,
            'priority': self.priority,
            'is_read': self.is_read,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'extra_data': self.extra_data,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'recipient': {
                'id': self.recipient.id,
                'username': self.recipient.username
            } if self.recipient else None
        }
        
        if include_sender and self.sender:
            data['sender'] = {
                'id': self.sender.id,
                'username': self.sender.username,
                'user_type': self.sender.user_type
            }
        
        return data


class NotificationSetting(db.Model):
    """
    نموذج إعدادات الإشعارات: لتخصيص إعدادات الإشعارات لكل مستخدم
    """
    __tablename__ = 'notification_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True)
    
    # إعدادات الإشعارات لكل نوع
    enable_all = db.Column(db.Boolean, default=True)                    # تفعيل جميع الإشعارات
    enable_attendance = db.Column(db.Boolean, default=True)             # إشعارات الحضور
    enable_leave = db.Column(db.Boolean, default=True)                  # إشعارات الإجازات
    enable_advance = db.Column(db.Boolean, default=True)                # إشعارات السلف
    enable_reward = db.Column(db.Boolean, default=True)                 # إشعارات المكافآت
    enable_penalty = db.Column(db.Boolean, default=True)                # إشعارات الجزاءات
    enable_transaction = db.Column(db.Boolean, default=True)            # إشعارات المعاملات
    enable_absence = db.Column(db.Boolean, default=True)                # إشعارات الغياب
    enable_production = db.Column(db.Boolean, default=True)             # إشعارات الإنتاج
    enable_system = db.Column(db.Boolean, default=True)                 # إشعارات النظام
    enable_kpi = db.Column(db.Boolean, default=True)                    # إشعارات KPI
    
    # إعدادات الإشعارات حسب الدور
    notify_as_department_head = db.Column(db.Boolean, default=True)     # إشعارات كرئيس قسم
    notify_as_department_deputy = db.Column(db.Boolean, default=True)   # إشعارات كنائب رئيس قسم
    notify_as_branch_head = db.Column(db.Boolean, default=True)       # إشعارات كرئيس فرع
    notify_as_branch_deputy = db.Column(db.Boolean, default=True)       # إشعارات كنائب رئيس فرع
    
    # تواريخ النظام
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # العلاقة
    user = db.relationship('User', back_populates='notification_settings', uselist=False)
    
    def __repr__(self):
        return f"<NotificationSetting for User {self.user_id}>"
    
    def is_type_enabled(self, notification_type):
        """التحقق مما إذا كان نوع الإشعار مفعلاً"""
        if not self.enable_all:
            return False
            
        type_mapping = {
            NotificationType.ATTENDANCE.value: self.enable_attendance,
            NotificationType.LEAVE.value: self.enable_leave,
            NotificationType.ADVANCE.value: self.enable_advance,
            NotificationType.REWARD.value: self.enable_reward,
            NotificationType.PENALTY.value: self.enable_penalty,
            NotificationType.TRANSACTION.value: self.enable_transaction,
            NotificationType.ABSENCE.value: self.enable_absence,
            NotificationType.PRODUCTION.value: self.enable_production,
            NotificationType.SYSTEM.value: self.enable_system,
            NotificationType.KPI.value: self.enable_kpi,
        }
        
        return type_mapping.get(notification_type, True)
    
    def to_dict(self):
        """تحويل الإعدادات إلى قاموس"""
        return {
            'user_id': self.user_id,
            'enable_all': self.enable_all,
            'enable_attendance': self.enable_attendance,
            'enable_leave': self.enable_leave,
            'enable_advance': self.enable_advance,
            'enable_reward': self.enable_reward,
            'enable_penalty': self.enable_penalty,
            'enable_transaction': self.enable_transaction,
            'enable_absence': self.enable_absence,
            'enable_production': self.enable_production,
            'enable_system': self.enable_system,
            'enable_kpi': self.enable_kpi,
            'notify_as_department_head': self.notify_as_department_head,
            'notify_as_department_deputy': self.notify_as_department_deputy,
            'notify_as_branch_head': self.notify_as_branch_head,
            'notify_as_branch_deputy': self.notify_as_branch_deputy,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

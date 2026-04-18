# app/routes/notification.py
# مسارات الإشعارات - API للتعامل مع الإشعارات

from flask import Blueprint, request, jsonify
from functools import wraps
from app.services.notification_service import NotificationService
from app.models.notification import NotificationType, NotificationPriority
from app.utils import token_required

notification_bp = Blueprint('notification', __name__)


def super_admin_required(f):
    """ديكوراتور للتحقق من أن المستخدم super_admin"""
    @wraps(f)
    def decorated(user, *args, **kwargs):
        if not user.is_super_admin():
            return jsonify({'message': 'يتطلب صلاحية مدير النظام'}), 403
        return f(user, *args, **kwargs)
    return decorated


# ==================== إشعارات المستخدم ====================

@notification_bp.route('/api/notifications', methods=['GET'])
@token_required
def get_notifications(user):
    """
    الحصول على إشعارات المستخدم الحالي
    
    Query Parameters:
        - is_read: فلترة حسب حالة القراءة (true/false)
        - type: نوع الإشعار
        - priority: أولوية الإشعار
        - limit: عدد النتائج (افتراضي: 50)
        - offset: بداية النتائج (افتراضي: 0)
    """
    user_id = user.id
    
    # معاملات الفلترة
    is_read = request.args.get('is_read')
    if is_read is not None:
        is_read = is_read.lower() == 'true'
    
    notification_type = request.args.get('type')
    priority = request.args.get('priority')
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)
    
    notifications = NotificationService.get_user_notifications(
        user_id=user_id,
        is_read=is_read,
        notification_type=notification_type,
        priority=priority,
        limit=limit,
        offset=offset
    )
    
    return jsonify({
        'notifications': [n.to_dict() for n in notifications],
        'total': len(notifications),
        'limit': limit,
        'offset': offset
    }), 200


@notification_bp.route('/api/notifications/unread-count', methods=['GET'])
@token_required
def get_unread_count(user):
    """الحصول على عدد الإشعارات غير المقروءة"""
    user_id = user.id
    count = NotificationService.get_unread_count(user_id)
    
    return jsonify({
        'unread_count': count
    }), 200


@notification_bp.route('/api/notifications/<int:notification_id>/read', methods=['PUT'])
@token_required
def mark_as_read(user, notification_id):
    """تعليم إشعار كمقروء"""
    user_id = user.id
    
    success = NotificationService.mark_as_read(notification_id, user_id)
    
    if success:
        return jsonify({
            'message': 'تم تعليم الإشعار كمقروء',
            'notification_id': notification_id
        }), 200
    
    return jsonify({
        'message': 'الإشعار غير موجود أو لا تمتلك صلاحية الوصول إليه'
    }), 404


@notification_bp.route('/api/notifications/<int:notification_id>/unread', methods=['PUT'])
@token_required
def mark_as_unread(user, notification_id):
    """تعليم إشعار كغير مقروء"""
    user_id = user.id
    
    success = NotificationService.mark_as_unread(notification_id, user_id)
    
    if success:
        return jsonify({
            'message': 'تم تعليم الإشعار كغير مقروء',
            'notification_id': notification_id
        }), 200
    
    return jsonify({
        'message': 'الإشعار غير موجود أو لا تمتلك صلاحية الوصول إليه'
    }), 404


@notification_bp.route('/api/notifications/mark-all-read', methods=['PUT'])
@token_required
def mark_all_as_read(user):
    """تعليم جميع الإشعارات كمقروءة"""
    user_id = user.id
    notification_type = request.args.get('type')
    
    count = NotificationService.mark_all_as_read(user_id, notification_type)
    
    return jsonify({
        'message': f'تم تعليم {count} إشعار كمقروء',
        'marked_count': count
    }), 200


@notification_bp.route('/api/notifications/<int:notification_id>', methods=['DELETE'])
@token_required
def delete_notification(user, notification_id):
    """حذف إشعار"""
    user_id = user.id
    
    success = NotificationService.delete_notification(notification_id, user_id)
    
    if success:
        return jsonify({
            'message': 'تم حذف الإشعار بنجاح',
            'notification_id': notification_id
        }), 200
    
    return jsonify({
        'message': 'الإشعار غير موجود أو لا تمتلك صلاحية حذفه'
    }), 404


# ==================== إعدادات الإشعارات ====================

@notification_bp.route('/api/notifications/settings', methods=['GET'])
@token_required
def get_settings(user):
    """الحصول على إعدادات الإشعارات"""
    user_id = user.id
    
    settings = NotificationService.get_or_create_settings(user_id)
    
    return jsonify({
        'settings': settings.to_dict()
    }), 200


@notification_bp.route('/api/notifications/settings', methods=['PUT'])
@token_required
def update_settings(user):
    """تحديث إعدادات الإشعارات"""
    user_id = user.id
    data = request.get_json()
    
    if not data:
        return jsonify({'message': 'لم يتم إرسال بيانات'}), 400
    
    # الحقول المسموح بتحديثها
    allowed_fields = [
        'enable_all', 'enable_attendance', 'enable_leave', 'enable_advance',
        'enable_reward', 'enable_penalty', 'enable_transaction', 'enable_absence',
        'enable_production', 'enable_system', 'enable_kpi',
        'notify_as_department_head', 'notify_as_department_deputy',
        'notify_as_branch_head', 'notify_as_branch_deputy'
    ]
    
    # تصفية البيانات
    update_data = {k: v for k, v in data.items() if k in allowed_fields}
    
    if not update_data:
        return jsonify({'message': 'لا توجد حقول صالحة للتحديث'}), 400
    
    settings = NotificationService.update_settings(user_id, update_data)
    
    return jsonify({
        'message': 'تم تحديث الإعدادات بنجاح',
        'settings': settings.to_dict()
    }), 200


# ==================== إرسال إشعارات (للمسؤولين) ====================

@notification_bp.route('/api/notifications/send', methods=['POST'])
@token_required
def send_notification(user):
    """
    إرسال إشعار لمستخدم محدد (للمسؤولين)
    
    Body:
        - recipient_id: معرف المستلم (مطلوب)
        - title: عنوان الإشعار (مطلوب)
        - message: نص الإشعار (مطلوب)
        - type: نوع الإشعار (افتراضي: general)
        - priority: أولوية الإشعار (افتراضي: medium)
        - entity_type: نوع الكيان المرتبط (اختياري)
        - entity_id: معرف الكيان المرتبط (اختياري)
    """
    # التحقق من الصلاحيات
    if not (user.is_super_admin() or 
            user.is_branch_head() or 
            user.is_department_head()):
        return jsonify({'message': 'ليس لديك صلاحية إرسال الإشعارات'}), 403
    
    data = request.get_json()
    
    # التحقق من الحقول المطلوبة
    required_fields = ['recipient_id', 'title', 'message']
    for field in required_fields:
        if field not in data:
            return jsonify({'message': f'الحقل {field} مطلوب'}), 400
    
    # إرسال الإشعار
    notification = NotificationService.send_notification(
        recipient_id=data['recipient_id'],
        title=data['title'],
        message=data['message'],
        notification_type=data.get('type', NotificationType.GENERAL.value),
        priority=data.get('priority', NotificationPriority.MEDIUM.value),
        sender_id=user.id,
        entity_type=data.get('entity_type'),
        entity_id=data.get('entity_id'),
        extra_data=data.get('extra_data')
    )
    
    if notification:
        return jsonify({
            'message': 'تم إرسال الإشعار بنجاح',
            'notification': notification.to_dict()
        }), 201
    
    return jsonify({
        'message': 'فشل في إرسال الإشعار. قد يكون المستخدم قد عطل هذا النوع من الإشعارات.'
    }), 400


@notification_bp.route('/api/notifications/send-to-department', methods=['POST'])
@token_required
def send_to_department(user):
    """
    إرسال إشعار لرؤساء قسم (وللنواب)
    
    Body:
        - department_id: معرف القسم (مطلوب)
        - title: عنوان الإشعار (مطلوب)
        - message: نص الإشعار (مطلوب)
        - include_deputies: هل يشمل النواب؟ (افتراضي: true)
    """
    # التحقق من الصلاحيات
    if not (user.is_super_admin() or 
            user.is_branch_head() or 
            user.is_department_head()):
        return jsonify({'message': 'ليس لديك صلاحية إرسال الإشعارات'}), 403
    
    data = request.get_json()
    
    required_fields = ['department_id', 'title', 'message']
    for field in required_fields:
        if field not in data:
            return jsonify({'message': f'الحقل {field} مطلوب'}), 400
    
    notifications = NotificationService.notify_department_heads(
        department_id=data['department_id'],
        title=data['title'],
        message=data['message'],
        notification_type=data.get('type', NotificationType.GENERAL.value),
        priority=data.get('priority', NotificationPriority.MEDIUM.value),
        sender_id=user.id,
        entity_type=data.get('entity_type'),
        entity_id=data.get('entity_id'),
        extra_data=data.get('extra_data'),
        include_deputies=data.get('include_deputies', True)
    )
    
    return jsonify({
        'message': f'تم إرسال الإشعار إلى {len(notifications)} مستخدم',
        'sent_count': len(notifications)
    }), 201


@notification_bp.route('/api/notifications/send-to-branch', methods=['POST'])
@token_required
def send_to_branch(user):
    """
    إرسال إشعار لرؤساء فرع (وللنواب)
    
    Body:
        - branch_id: معرف الفرع (مطلوب)
        - title: عنوان الإشعار (مطلوب)
        - message: نص الإشعار (مطلوب)
        - include_deputies: هل يشمل النواب؟ (افتراضي: true)
    """
    # التحقق من الصلاحيات
    if not user.is_super_admin():
        return jsonify({'message': 'ليس لديك صلاحية إرسال الإشعارات'}), 403
    
    data = request.get_json()
    
    required_fields = ['branch_id', 'title', 'message']
    for field in required_fields:
        if field not in data:
            return jsonify({'message': f'الحقل {field} مطلوب'}), 400
    
    notifications = NotificationService.notify_branch_heads(
        branch_id=data['branch_id'],
        title=data['title'],
        message=data['message'],
        notification_type=data.get('type', NotificationType.GENERAL.value),
        priority=data.get('priority', NotificationPriority.MEDIUM.value),
        sender_id=user.id,
        entity_type=data.get('entity_type'),
        entity_id=data.get('entity_id'),
        extra_data=data.get('extra_data'),
        include_deputies=data.get('include_deputies', True)
    )
    
    return jsonify({
        'message': f'تم إرسال الإشعار إلى {len(notifications)} مستخدم',
        'sent_count': len(notifications)
    }), 201


@notification_bp.route('/api/notifications/send-to-admins', methods=['POST'])
@token_required
@super_admin_required
def send_to_admins(user):
    """
    إرسال إشعار لجميع المسؤولين (super_admin فقط)
    
    Body:
        - title: عنوان الإشعار (مطلوب)
        - message: نص الإشعار (مطلوب)
    """
    data = request.get_json()
    
    required_fields = ['title', 'message']
    for field in required_fields:
        if field not in data:
            return jsonify({'message': f'الحقل {field} مطلوب'}), 400
    
    notifications = NotificationService.notify_all_admins(
        title=data['title'],
        message=data['message'],
        notification_type=data.get('type', NotificationType.GENERAL.value),
        priority=data.get('priority', NotificationPriority.MEDIUM.value),
        sender_id=user.id,
        entity_type=data.get('entity_type'),
        entity_id=data.get('entity_id'),
        extra_data=data.get('extra_data')
    )
    
    return jsonify({
        'message': f'تم إرسال الإشعار إلى {len(notifications)} مسؤول',
        'sent_count': len(notifications)
    }), 201


# ==================== أنواع وأولويات الإشعارات ====================

@notification_bp.route('/api/notifications/types', methods=['GET'])
@token_required
def get_notification_types(user):
    """الحصول على قائمة أنواع الإشعارات المتاحة"""
    types = [
        {'value': t.value, 'label': t.name} 
        for t in NotificationType
    ]
    
    return jsonify({'types': types}), 200


@notification_bp.route('/api/notifications/priorities', methods=['GET'])
@token_required
def get_notification_priorities(user):
    """الحصول على قائمة أولويات الإشعارات المتاحة"""
    priorities = [
        {'value': p.value, 'label': p.name} 
        for p in NotificationPriority
    ]
    
    return jsonify({'priorities': priorities}), 200


# ==================== صيانة الإشعارات (لـ super_admin) ====================

@notification_bp.route('/api/notifications/cleanup', methods=['DELETE'])
@token_required
@super_admin_required
def cleanup_old_notifications(user):
    """
    حذف الإشعارات القديمة المقروءة
    
    Query Parameters:
        - days: عدد الأيام (الإشعارات الأقدم من هذا العدد ستحذف)
    """
    days = request.args.get('days', 30, type=int)
    
    deleted_count = NotificationService.delete_old_notifications(days)
    
    return jsonify({
        'message': f'تم حذف {deleted_count} إشعار قديم',
        'deleted_count': deleted_count,
        'older_than_days': days
    }), 200

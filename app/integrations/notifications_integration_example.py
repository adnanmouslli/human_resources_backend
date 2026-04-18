# app/integrations/notifications_integration_example.py
# أمثلة تكامل نظام الإشعارات مع الموديلات المختلفة
# يمكن نسخ هذه الأمثلة وإضافتها إلى المسارات المناسبة

from app.services.notification_service import (
    notify_employee_action,
    notify_department_action,
    notify_branch_action,
    NotificationService,
    NotificationType,
    NotificationPriority
)

# ==========================================
# 1. التكامل مع نظام الإجازات
# ==========================================

def example_leave_notification(leave_request, employee):
    """
    مثال: إرسال إشعار عند طلب إجازة جديدة
    
    أضف هذا الكود في routes/leave_routes.py بعد إنشاء طلب الإجازة
    """
    notify_employee_action(
        employee_id=employee.id,
        action_title="طلب إجازة جديد",
        action_message=f"قام {employee.full_name} بطلب إجازة {leave_request.leave_type} "
                      f"من {leave_request.start_date} إلى {leave_request.end_date}",
        notification_type=NotificationType.LEAVE.value,
        priority=NotificationPriority.MEDIUM.value,
        entity_type="leave",
        entity_id=leave_request.id,
        extra_data={
            "leave_type": leave_request.leave_type,
            "start_date": str(leave_request.start_date),
            "end_date": str(leave_request.end_date),
            "days_count": leave_request.days_count
        }
    )


def example_leave_approved_notification(leave_request, employee, approved_by):
    """إشعار عند موافقة الإجازة"""
    NotificationService.send_notification(
        recipient_id=employee.user_account.id if employee.user_account else None,
        title="تمت موافقة إجازتك",
        message=f"تمت موافقة طلب إجازتك من {approved_by.username}",
        notification_type=NotificationType.LEAVE.value,
        sender_id=approved_by.id,
        entity_type="leave",
        entity_id=leave_request.id
    )


# ==========================================
# 2. التكامل مع نظام الحضور
# ==========================================

def example_attendance_notification(attendance, employee):
    """
    مثال: إشعار عند تسجيل حضور متأخر
    
    أضف هذا في routes/attendance.py عند إضافة سجل حضور
    """
    if attendance.is_late:
        notify_employee_action(
            employee_id=employee.id,
            action_title="تأخر موظف",
            action_message=f"تأخر {employee.full_name} {attendance.delay_minutes} دقيقة اليوم",
            notification_type=NotificationType.ATTENDANCE.value,
            priority=NotificationPriority.MEDIUM.value,
            entity_type="attendance",
            entity_id=attendance.id,
            extra_data={
                "delay_minutes": attendance.delay_minutes,
                "check_in_time": str(attendance.checkInTime),
                "date": str(attendance.createdAt)
            }
        )


def example_absence_notification(employee, date):
    """إشعار عند غياب موظف"""
    notify_employee_action(
        employee_id=employee.id,
        action_title="غياب موظف",
        action_message=f"{employee.full_name} غائب اليوم {date}",
        notification_type=NotificationType.ABSENCE.value,
        priority=NotificationPriority.HIGH.value,
        entity_type="attendance",
        extra_data={
            "date": str(date),
            "department": employee.department.name if employee.department else None
        }
    )


# ==========================================
# 3. التكامل مع نظام السلف
# ==========================================

def example_advance_request_notification(advance, employee):
    """
    مثال: إشعار عند طلب سلفة
    
    أضف هذا في routes/advance.py عند إنشاء طلب سلفة
    """
    notify_employee_action(
        employee_id=employee.id,
        action_title="طلب سلفة جديد",
        action_message=f"قام {employee.full_name} بطلب سلفة بقيمة {advance.amount}",
        notification_type=NotificationType.ADVANCE.value,
        priority=NotificationPriority.HIGH.value,  # أولوية عالية لأنها تتعلق بالمال
        entity_type="advance",
        entity_id=advance.id,
        extra_data={
            "amount": float(advance.amount),
            "reason": advance.reason,
            "request_date": str(advance.request_date)
        }
    )


def example_advance_approved_notification(advance, employee, approved_by):
    """إشعار عند موافقة السلفة"""
    if employee.user_account:
        NotificationService.send_notification(
            recipient_id=employee.user_account.id,
            title="تمت موافقة سلفتك",
            message=f"تمت موافقة طلب السلفة بقيمة {advance.amount} من {approved_by.username}",
            notification_type=NotificationType.ADVANCE.value,
            priority=NotificationPriority.HIGH.value,
            sender_id=approved_by.id,
            entity_type="advance",
            entity_id=advance.id
        )


# ==========================================
# 4. التكامل مع نظام المكافآت والجزاءات
# ==========================================

def example_reward_notification(reward, employee, added_by):
    """
    مثال: إشعار عند إضافة مكافأة
    
    أضف هذا في routes/reward.py عند إضافة مكافأة
    """
    notify_employee_action(
        employee_id=employee.id,
        action_title="مكافأة جديدة",
        action_message=f"تم إضافة مكافأة للموظف {employee.full_name} بقيمة {reward.amount}",
        notification_type=NotificationType.REWARD.value,
        sender_id=added_by.id if added_by else None,
        entity_type="reward",
        entity_id=reward.id,
        extra_data={
            "amount": float(reward.amount),
            "reason": reward.reason,
            "date": str(reward.date)
        }
    )
    
    # إرسال إشعار للموظف نفسه إذا كان لديه حساب
    if employee.user_account:
        NotificationService.send_notification(
            recipient_id=employee.user_account.id,
            title="تهانينا! مكافأة جديدة",
            message=f"تم إضافة مكافأة لك بقيمة {reward.amount} بسبب: {reward.reason}",
            notification_type=NotificationType.REWARD.value,
            sender_id=added_by.id if added_by else None,
            entity_type="reward",
            entity_id=reward.id
        )


def example_penalty_notification(penalty, employee, added_by):
    """
    مثال: إشعار عند إضافة جزاء
    
    أضف هذا في routes/penalty.py عند إضافة جزاء
    """
    notify_employee_action(
        employee_id=employee.id,
        action_title="جزاء جديد",
        action_message=f"تم إضافة جزاء للموظف {employee.full_name}",
        notification_type=NotificationType.PENALTY.value,
        priority=NotificationPriority.HIGH.value,
        sender_id=added_by.id if added_by else None,
        entity_type="penalty",
        entity_id=penalty.id,
        extra_data={
            "penalty_type": penalty.penalty_type,
            "reason": penalty.reason,
            "date": str(penalty.date)
        }
    )


# ==========================================
# 5. التكامل مع نظام المعاملات
# ==========================================

def example_transaction_notification(transaction, employee, action_type):
    """
    مثال: إشعار عند إجراء معاملة
    
    أضف هذا في routes/transaction_routes.py
    """
    messages = {
        "created": f"تم إنشاء معاملة جديدة للموظف {employee.full_name}",
        "updated": f"تم تحديث معاملة للموظف {employee.full_name}",
        "approved": f"تمت الموافقة على معاملة للموظف {employee.full_name}",
        "rejected": f"تم رفض معاملة للموظف {employee.full_name}"
    }
    
    notify_employee_action(
        employee_id=employee.id,
        action_title=f"معاملة {action_type}",
        action_message=messages.get(action_type, "تم إجراء معاملة"),
        notification_type=NotificationType.TRANSACTION.value,
        entity_type="transaction",
        entity_id=transaction.id,
        extra_data={
            "action": action_type,
            "transaction_type": transaction.transaction_type,
            "amount": float(transaction.amount) if hasattr(transaction, 'amount') else None
        }
    )


# ==========================================
# 6. التكامل مع نظام الإنتاج
# ==========================================

def example_production_notification(production_record, employee, monitoring_data=None):
    """
    مثال: إشعار عند تحقيق إنجاز إنتاج
    
    أضف هذا في routes/ProductionMonitoring.py
    """
    if monitoring_data and monitoring_data.get('is_excellent'):
        notify_employee_action(
            employee_id=employee.id,
            action_title="إنجاز إنتاج متميز",
            action_message=f"حقق {employee.full_name} إنتاجية متميزة اليوم!",
            notification_type=NotificationType.PRODUCTION.value,
            priority=NotificationPriority.MEDIUM.value,
            entity_type="production",
            entity_id=production_record.id,
            extra_data={
                "production_count": monitoring_data.get('count'),
                "efficiency": monitoring_data.get('efficiency'),
                "date": str(production_record.date)
            }
        )


# ==========================================
# 7. إشعارات على مستوى القسم/الفرع
# ==========================================

def example_department_notification(department_id, event_title, event_message, event_type="general"):
    """
    إشعار لجميع رؤساء قسم معين
    """
    notify_department_action(
        department_id=department_id,
        action_title=event_title,
        action_message=event_message,
        notification_type=getattr(NotificationType, event_type.upper(), NotificationType.GENERAL).value,
        include_deputies=True  # إرسال للنواب أيضاً
    )


def example_branch_notification(branch_id, event_title, event_message, event_type="general"):
    """
    إشعار لجميع رؤساء فرع معين
    """
    notify_branch_action(
        branch_id=branch_id,
        action_title=event_title,
        action_message=event_message,
        notification_type=getattr(NotificationType, event_type.upper(), NotificationType.GENERAL).value,
        include_deputies=True
    )


# ==========================================
# 8. إشعارات النظام
# ==========================================

def example_system_notification(title, message, priority=NotificationPriority.LOW.value):
    """
    إشعار نظامي لجميع المسؤولين
    """
    NotificationService.notify_all_admins(
        title=title,
        message=message,
        notification_type=NotificationType.SYSTEM.value,
        priority=priority
    )


def example_backup_completed_notification(backup_info):
    """إشعار اكتمال النسخ الاحتياطي"""
    NotificationService.notify_all_admins(
        title="اكتمال النسخ الاحتياطي",
        message=f"تم إنشاء نسخة احتياطية بنجاح. الحجم: {backup_info.get('size', 'غير معروف')}",
        notification_type=NotificationType.SYSTEM.value,
        priority=NotificationPriority.LOW.value,
        extra_data=backup_info
    )


# ==========================================
# 9. التكامل مع نظام KPI
# ==========================================

def example_kpi_evaluation_notification(evaluation, employee, evaluated_by):
    """
    إشعار عند إجراء تقييم KPI
    """
    notify_employee_action(
        employee_id=employee.id,
        action_title="تقييم أداء جديد",
        action_message=f"تم تقييم أداء {employee.full_name} لليوم {evaluation.date}",
        notification_type=NotificationType.KPI.value,
        sender_id=evaluated_by.id if evaluated_by else None,
        entity_type="kpi_evaluation",
        entity_id=evaluation.id,
        extra_data={
            "date": str(evaluation.date),
            "total_score": evaluation.total_score,
            "evaluator": evaluated_by.username if evaluated_by else None
        }
    )


def example_kpi_low_score_notification(evaluation, employee, threshold=60):
    """إشعار خاص عندما يكون التقييم منخفضاً"""
    if evaluation.total_score < threshold:
        notify_employee_action(
            employee_id=employee.id,
            action_title="تنبيه: تقييم أداء منخفض",
            action_message=f"حصل {employee.full_name} على تقييم منخفض ({evaluation.total_score}%) "
                          f"في يوم {evaluation.date}. يُنصح بمتابعة الأداء.",
            notification_type=NotificationType.KPI.value,
            priority=NotificationPriority.HIGH.value,
            entity_type="kpi_evaluation",
            entity_id=evaluation.id
        )


# ==========================================
# 10. دالة مساعدة للاستخدام السريع
# ==========================================

def notify_on_employee_action(
    employee_id: int,
    action: str,
    details: dict = None,
    priority: str = NotificationPriority.MEDIUM.value
):
    """
    دالة موحدة للإشعار عند أي إجراء يقوم به موظف
    
    Args:
        employee_id: معرف الموظف
        action: نوع الإجراء (مثلاً: 'leave_request', 'advance_request', etc.)
        details: تفاصيل إضافية
        priority: أولوية الإشعار
    """
    from app.models.employee import Employee
    
    employee = Employee.query.get(employee_id)
    if not employee:
        return
    
    # أنواع الإجراءات ورسائلها
    action_messages = {
        'leave_request': ('طلب إجازة', f"قام {employee.full_name} بطلب إجازة"),
        'leave_approved': ('إجازة معتمدة', f"تمت الموافقة على إجازة {employee.full_name}"),
        'advance_request': ('طلب سلفة', f"قام {employee.full_name} بطلب سلفة"),
        'advance_approved': ('سلفة معتمدة', f"تمت الموافقة على سلفة {employee.full_name}"),
        'attendance_late': ('تأخر', f"تأخر {employee.full_name} عن العمل"),
        'attendance_absent': ('غياب', f"غاب {employee.full_name} عن العمل"),
        'reward_added': ('مكافأة', f"تم إضافة مكافأة لـ {employee.full_name}"),
        'penalty_added': ('جزاء', f"تم إضافة جزاء لـ {employee.full_name}"),
        'transaction_created': ('معاملة جديدة', f"تم إنشاء معاملة لـ {employee.full_name}"),
        'kpi_evaluated': ('تقييم KPI', f"تم تقييم أداء {employee.full_name}"),
        'profile_updated': ('تحديث بيانات', f"قام {employee.full_name} بتحديث بياناته"),
    }
    
    title, message = action_messages.get(
        action, 
        ('إجراء جديد', f"قام {employee.full_name} بإجراء جديد")
    )
    
    # تحديد نوع الإشعار بناءً على الإجراء
    notification_type = NotificationType.GENERAL.value
    if 'leave' in action:
        notification_type = NotificationType.LEAVE.value
    elif 'advance' in action:
        notification_type = NotificationType.ADVANCE.value
    elif 'attendance' in action or 'absent' in action:
        notification_type = NotificationType.ATTENDANCE.value
    elif 'reward' in action:
        notification_type = NotificationType.REWARD.value
    elif 'penalty' in action:
        notification_type = NotificationType.PENALTY.value
    elif 'transaction' in action:
        notification_type = NotificationType.TRANSACTION.value
    elif 'kpi' in action:
        notification_type = NotificationType.KPI.value
    
    notify_employee_action(
        employee_id=employee_id,
        action_title=title,
        action_message=message,
        notification_type=notification_type,
        priority=priority,
        extra_data=details
    )


# ==========================================
# مثال استخدام شاملة
# ==========================================
"""
# في routes/leave_routes.py:

from app.integrations.notifications_integration_example import (
    example_leave_notification,
    example_leave_approved_notification
)

@leave_bp.route('/api/leaves', methods=['POST'])
@token_required
def create_leave(current_user):
    # ... كود إنشاء الإجازة ...
    
    # إرسال إشعار تلقائي لمديري القسم والفرع
    example_leave_notification(new_leave, employee)
    
    return jsonify({'message': 'تم إنشاء طلب الإجازة', 'leave': new_leave.to_dict()}), 201


@leave_bp.route('/api/leaves/<int:leave_id>/approve', methods=['PUT'])
@token_required
def approve_leave(current_user, leave_id):
    # ... كود الموافقة ...
    
    # إرسال إشعار للموظف بالموافقة
    example_leave_approved_notification(leave, employee, current_user)
    
    return jsonify({'message': 'تمت الموافقة على الإجازة'}), 200
"""

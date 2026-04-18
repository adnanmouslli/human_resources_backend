# app/services/__init__.py

from .notification_service import (
    NotificationService,
    notify_employee_action,
    notify_department_action,
    notify_branch_action
)

__all__ = [
    'NotificationService',
    'notify_employee_action',
    'notify_department_action',
    'notify_branch_action'
]

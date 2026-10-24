# app/services/user_account_service.py
# إنشاء حساب مستخدم تلقائياً للموظف عند تعيينه في فرع/قسم
# (مصدر واحد تستخدمه كل المسارات: التعيين، التوظيف، التعيين الجماعي، الإضافة، الاستيراد)

from werkzeug.security import generate_password_hash

from app import db
from app.models.user import User

DEFAULT_EMPLOYEE_PASSWORD = '123456'
USERNAME_MAX_LENGTH = 50  # يطابق طول عمود users.username


def generate_unique_username(full_name):
    """
    توليد اسم مستخدم فريد من اسم الموظف (أحرف صغيرة مع إبقاء الفراغ كما هو)
    بحيث لا يتجاوز طول عمود users.username.
    """
    base = ' '.join((full_name or '').lower().split())[:USERNAME_MAX_LENGTH].strip() or 'employee'
    username = base
    counter = 1
    while User.query.filter_by(username=username).first():
        suffix = f" {counter}"
        username = f"{base[:USERNAME_MAX_LENGTH - len(suffix)].rstrip()}{suffix}"
        counter += 1
    return username


def ensure_employee_user_account(employee, password=None, user_type='employee'):
    """
    إنشاء حساب مستخدم للموظف إذا لم يكن لديه حساب وكان معيّناً في فرع أو قسم
    (الموظف غير المفعّل لا يُنشأ له حساب).

    يعيد الحساب الجديد، أو None إذا لم يُنشأ شيء (لديه حساب أو غير معيّن).
    لا يقوم بـ commit — المستدعي مسؤول عن ذلك.
    """
    if not employee or not employee.id or employee.is_active is False:
        return None
    if not (employee.branch_id or employee.department_id):
        return None
    if employee.user_account or User.query.filter_by(employee_id=employee.id).first():
        return None

    new_user = User(
        username=generate_unique_username(employee.full_name),
        password=generate_password_hash(password or DEFAULT_EMPLOYEE_PASSWORD),
        user_type=user_type,
        is_active=True,
        department_id=employee.department_id,
        branch_id=employee.branch_id,
    )
    # الربط عبر العلاقة حتى يرى employee.user_account الحساب الجديد في نفس الجلسة
    employee.user_account = new_user
    db.session.add(new_user)
    db.session.flush()
    return new_user

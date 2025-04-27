# employee.py

from app import db
from sqlalchemy import event, CheckConstraint

from app.models.department import Department

class Employee(db.Model):
    __tablename__ = 'employees'

    id = db.Column(db.Integer, primary_key=True)
    fingerprint_id = db.Column(db.String(50), nullable=False)  # رقم الموظف على جهاز البصمة
    full_name = db.Column(db.String(255), nullable=False)  # الاسم الرباعي
    employee_type = db.Column(db.String(50), nullable=True)  # 'permanent' or 'temporary'

    # New fields for department and branch connections
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)  # ربط مع الفرع
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)  # ربط مع القسم
    is_department_head = db.Column(db.Boolean, default=False)  # مؤشر إذا كان الموظف رئيس قسم

    position = db.Column(db.Integer, db.ForeignKey('job_titles.id'), nullable=True)  # ربط مع جدول المسمى الوظيفي
    salary = db.Column(db.Numeric(10, 2), default=0)  # المرتب
    advancePercentage = db.Column(db.Numeric(5, 2), nullable=True)  # حقل نسبة السلفة
    certificates = db.Column(db.Text, nullable=True)  # الشهادات الحاصل عليها
    date_of_birth = db.Column(db.Date, nullable=True)  # تاريخ الولادة
    place_of_birth = db.Column(db.String(255), nullable=True)  # مكان الولادة
    id_card_number = db.Column(db.String(50), nullable=True)  # رقم البطاقة
    national_id = db.Column(db.String(50), nullable=True)  # الرقم الوطني
    residence = db.Column(db.String(255), nullable=True)  # مكان الإقامة
    mobile_1 = db.Column(db.String(15), nullable=True)  # رقم الموبايل 1
    mobile_2 = db.Column(db.String(15), nullable=True)  # رقم الموبايل 2
    mobile_3 = db.Column(db.String(15), nullable=True)  # رقم الموبايل 3
    worker_agreement = db.Column(db.Text, nullable=True)  # اتفاق العامل
    notes = db.Column(db.Text, nullable=True)  # ملاحظات

    work_system = db.Column(db.String(100), nullable=True)  # نظام العمل
    shift_id = db.Column(db.Integer, db.ForeignKey('shift.id'), nullable=True)  # رقم الوردية (ربط مع جدول الورديات)
    profession_id = db.Column(db.Integer, db.ForeignKey('professions.id'), nullable=True)  # ربط بالمهن المؤقتة

    insurance_deduction = db.Column(db.Float, default=0)  # خصم التأمينات
    allowances = db.Column(db.Float, default=0)  # البدلات
    insurance_start_date = db.Column(db.Date, nullable=True)
    insurance_end_date = db.Column(db.Date, nullable=True)

    date_of_joining = db.Column(db.Date, nullable=True)  # موعد التعيين
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())  # تاريخ الإضافة
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())  # تاريخ التحديث

    def __repr__(self):
        return f"<Employee {self.full_name} - {self.position}>"
    
    # إضافة قيد للتحقق من عدم وجود أكثر من رئيس قسم لنفس القسم
    __table_args__ = (
        CheckConstraint(
            "NOT (is_department_head AND department_id IN "
            "(SELECT department_id FROM employees WHERE is_department_head = true AND id != EXCLUDED.id))",
            name="unique_department_head"
        ),
    )


# إضافة قيد على مستوى قاعدة البيانات (يعمل عند إجراء تغييرات على الموظفين)
@event.listens_for(Employee, 'before_insert')
@event.listens_for(Employee, 'before_update')
def check_department_head(mapper, connection, target):
    if target.is_department_head and target.department_id:
        # التحقق من وجود رئيس قسم آخر للقسم نفسه
        stmt = db.select(Employee).where(
            Employee.department_id == target.department_id,
            Employee.is_department_head == True,
            Employee.id != target.id
        )
        existing_head = db.session.execute(stmt).scalar_one_or_none()
        
        if existing_head:
            raise ValueError(f"هناك رئيس قسم آخر بالفعل لهذا القسم: {existing_head.full_name}")
        
        # تحديث حقل رئيس القسم في جدول الأقسام
        department = db.session.get(Department, target.department_id)
        if department:
            department.head_id = target.id

"""
شرح الجدول:
يمثل هذا الجدول بيانات الموظفين في النظام، حيث يحتوي على المعلومات الشخصية، المالية، والمهنية مثل المسمى الوظيفي، المهنة، المرتب، البدلات، التأمينات، وغيرها.
الربط مع الجداول الأخرى يتم من خلال الأعمدة مثل `position` (المسمى الوظيفي) و `shift_id` (الوردية) و `profession_id` (المهنة المؤقتة).
"""

from enum import Enum
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy import JSON
from app import db

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

class Employee(db.Model):
    __tablename__ = 'employees'

    id = db.Column(db.Integer, primary_key=True)
    fingerprint_id = db.Column(db.String(50), nullable=False)  # رقم الموظف على جهاز البصمة
    full_name = db.Column(db.String(255), nullable=False)  # الاسم الرباعي
    employee_type = db.Column(db.String(50), nullable=True)  # 'permanent' or 'temporary'

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

    insurance_deduction = db.Column(db.Float, default=0)# خصم التأمينات
    allowances = db.Column(db.Float, default=0)  # البدلات
    insurance_start_date = db.Column(db.Date, nullable=True)
    insurance_end_date = db.Column(db.Date, nullable=True)

    date_of_joining = db.Column(db.Date, nullable=True)  # موعد التعيين
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())  # تاريخ الإضافة
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())  # تاريخ التحديث


    job_title = db.relationship('JobTitle', backref='employees', lazy=True)
    profession = db.relationship('Profession', backref='employees', lazy=True)
    

    def __repr__(self):
        return f"<Employee {self.full_name} - {self.position}>"


from app import db
from datetime import date, time

class Shift(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # ID تلقائي
    name = db.Column(db.String(100), nullable=False)  # اسم الوردية
    start_time = db.Column(db.Time, nullable=False)  # وقت البداية
    end_time = db.Column(db.Time, nullable=False)  # وقت النهاية
    allowed_delay_minutes = db.Column(db.Integer, nullable=False, default=0)  # فترة التأخير المسموحة بالدقائق
    allowed_exit_minutes = db.Column(db.Integer, nullable=False, default=0)  # فترة الخروج المسموحة
    note = db.Column(db.Text, nullable=True)  # ملاحظة
    absence_minutes = db.Column(db.Integer, nullable=False, default=0)  # فترة الغياب بالدقائق
    extra_minutes = db.Column(db.Integer, nullable=False, default=0)  # فترة الإضافي بالدقائق

    def __repr__(self):
        return f"<Shift {self.name}>"
    
class JobTitle(db.Model):
    __tablename__ = 'job_titles'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # ID تلقائي
    title_name = db.Column(db.String(100), nullable=False)  # اسم المسمى الوظيفي
    allowed_break_time = db.Column(db.String(5), nullable=True)  # عدد ساعات الاستراحة (صيغة HH:MM)
    overtime_hour_value = db.Column(db.Numeric(10, 2), nullable=True)  # قيمة ساعة الإضافي
    delay_minute_value = db.Column(db.Numeric(10, 2), nullable=True)  # قيمة دقيقة التأخير
    production_system = db.Column(db.Boolean, nullable=False, default=False)  # نظام كمية الإنتاج
    shift_system = db.Column(db.Boolean, nullable=False, default=False)  # نظام الورديات
    month_system = db.Column(db.Boolean, nullable=False, default=False)  # نظام الشهري
        
    production_piece_value = db.Column(db.Numeric(10, 2), nullable=True)  # سعر قطعة الإنتاج

    def __repr__(self):
        return f"<JobTitle {self.title_name}>"
    
class Attendance(db.Model):
    __tablename__ = 'attendances'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # ID تلقائي
    empId = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)  # ForeignKey من جدول Employee
    createdAt = db.Column(db.Date, default=date.today)  # تاريخ التسجيل فقط
    checkInTime = db.Column(db.Time, nullable=True)  # وقت الحضور فقط (صيغة الوقت)
    checkOutTime = db.Column(db.Time, nullable=True)  # وقت الانصراف فقط (صيغة الوقت)
    
    # الأعمدة الجديدة
    checkInReason = db.Column(db.String(255), nullable=True)  # سبب الدخول (اختياري)
    checkOutReason = db.Column(db.String(255), nullable=True)  # سبب الخروج (اختياري)
    productionQuantity = db.Column(db.Float, nullable=True)  # كمية الإنتاج للعمال بنظام الإنتاجية (اختياري)
    
    # علاقات بين الجداول (لمزيد من التفاعل مع جدول Employee)
    employee = db.relationship('Employee', backref='attendances', lazy=True)

    def __repr__(self):
        return f"<Attendance {self.id}, Employee {self.empId}>"
class Advance(db.Model):
    __tablename__ = 'advances'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    date = db.Column(db.Date, nullable=False, default=db.func.current_date())
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    document_number = db.Column(db.String(50), nullable=False)
    notes = db.Column(db.Text, nullable=True)

    # Relationship
    employee = db.relationship('Employee', backref='advances', lazy=True)

    def __repr__(self):
        return f"<Advance {self.id}, Employee {self.employee_id}>"


class ProductionPiece(db.Model):
    __tablename__ = 'production_pieces'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    piece_number = db.Column(db.String(50), unique=True, nullable=False)  # رقم القطعة
    is_active = db.Column(db.Boolean, default=True)  # حالة تفعيل القطعة

    piece_name = db.Column(db.String(255), nullable=False)  # اسم القطعة
    price_levels = db.Column(JSON, nullable=False)  # تخزين أسعار المستويات كـ JSON
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    def __repr__(self):
        return f"<ProductionPiece {self.piece_name}>"
    

class ProductionMonitoring(db.Model):
    __tablename__ = 'production_monitoring'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    piece_id = db.Column(db.Integer, db.ForeignKey('production_pieces.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, default=db.func.current_date())
    quantity = db.Column(db.Integer, nullable=False)  # عدد القطع
    quality_grade = db.Column(db.String(1), nullable=False)  # مستوى الجودة (A, B, C, D, E)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
    notes = db.Column(db.Text, nullable=True)  # ملاحظات إضافية

    # العلاقات
    employee = db.relationship('Employee', backref='production_monitoring', lazy=True)
    piece = db.relationship('ProductionPiece', backref='production_monitoring', lazy=True)

    def __repr__(self):
        return f"<ProductionMonitoring Employee: {self.employee_id}, Piece: {self.piece_id}, Quantity: {self.quantity}, Grade: {self.quality_grade}>"
    

class Profession(db.Model):
    __tablename__ = 'professions'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # ID تلقائي
    name = db.Column(db.String(100), nullable=False)  # اسم المهنة
    hourly_rate = db.Column(db.Numeric(10, 2), nullable=False)  # سعر الساعة
    daily_rate = db.Column(db.Numeric(10, 2), nullable=False)  # سعر اليوم
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())  # تاريخ الإضافة
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())  # تاريخ التحديث

    def __repr__(self):
        return f"<Profession {self.name}, Hourly: {self.hourly_rate}, Daily: {self.daily_rate}>"


class AttendanceType(str, Enum):
    FULL_DAY = 'full_day'      # يوم كامل
    HALF_DAY = 'half_day'      # نصف يوم
    ONLINE_DAY = 'online_day'  # يوم أون لاين
    ABSENT = 'absent'          # غائب

class MonthlyAttendance(db.Model):
    __tablename__ = 'monthly_attendance'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    
    # نوع الدوام (يوم كامل، نصف يوم، أون لاين)
    attendance_type = db.Column(SQLAlchemyEnum(AttendanceType), nullable=False)
    
    # في حالة الغياب بعذر
    is_excused_absence = db.Column(db.Boolean, default=False)
    excuse_document = db.Column(db.String(255), nullable=True)  # مستند العذر إن وجد
    
    # أوقات الحضور والانصراف
    check_in = db.Column(db.Time, nullable=True)
    check_out = db.Column(db.Time, nullable=True)
    
    # ملاحظات
    notes = db.Column(db.Text, nullable=True)
    
    # التوقيت
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    # العلاقات
    employee = db.relationship('Employee', backref='monthly_attendance', lazy=True)

    __table_args__ = (
        # منع تكرار تسجيل نفس اليوم لنفس الموظف
        db.UniqueConstraint('employee_id', 'date', name='unique_employee_date'),
    )

    def __repr__(self):
        return f"<MonthlyAttendance: Employee {self.employee_id}, Date {self.date}, Type {self.attendance_type}>"
from app import db

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

"""
شرح الجدول:
يمثل جدول المسميات الوظيفية في النظام، حيث يحتوي على اسم المسمى الوظيفي، ونظام الورديات (إن وجد)، وساعات الاستراحة، وكذلك القيم المالية المرتبطة بالدوام الإضافي والتأخير.
الربط مع الموظفين يتم من خلال العمود `position` في جدول `Employee`.
"""

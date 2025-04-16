# shift.py

from app import db
from datetime import time

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

"""
شرح الجدول:
يمثل جدول الورديات الذي يحتوي على معلومات عن الورديات المختلفة في المؤسسة. يشمل وقت البداية والنهاية للوردية، مدة التأخير المسموح بها، إضافة إلى ملاحظات وأوقات الغياب والإضافي.
هذا الجدول يمكن ربطه بالموظفين في جدول `Employee` من خلال عمود `shift_id`.
"""

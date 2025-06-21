# shift.py

from app import db
from datetime import time
import json

class Shift(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # ID تلقائي
    name = db.Column(db.String(100), nullable=False)  # اسم الوردية
    
    # الحقول القديمة للتوافق مع النظام الحالي (اختيارية)
    start_time = db.Column(db.Time, nullable=True)  # وقت البداية العام
    end_time = db.Column(db.Time, nullable=True)  # وقت النهاية العام
    
    # الحقل الجديد لتخزين أوقات الأيام
    daily_schedule = db.Column(db.JSON, nullable=False)  # جدولة الأيام بصيغة JSON
    
    allowed_delay_minutes = db.Column(db.Integer, nullable=False, default=0)  # فترة التأخير المسموحة بالدقائق
    allowed_exit_minutes = db.Column(db.Integer, nullable=False, default=0)  # فترة الخروج المسموحة
    note = db.Column(db.Text, nullable=True)  # ملاحظة
    absence_minutes = db.Column(db.Integer, nullable=False, default=0)  # فترة الغياب بالدقائق
    extra_minutes = db.Column(db.Integer, nullable=False, default=0)  # فترة الإضافي بالدقائق

    def __repr__(self):
        return f"<Shift {self.name}>"
    
    def get_day_schedule(self, day_name):
        """
        الحصول على جدول يوم محدد
        day_name: اسم اليوم بالإنجليزية (monday, tuesday, etc.)
        """
        if not self.daily_schedule:
            return None
        return self.daily_schedule.get(day_name.lower())
    
    def is_working_day(self, day_name):
        """
        التحقق من كون اليوم يوم عمل
        """
        day_schedule = self.get_day_schedule(day_name)
        return day_schedule is not None and day_schedule.get('is_active', False)
    
    def get_day_times(self, day_name):
        """
        الحصول على أوقات الدخول والخروج ليوم محدد
        """
        day_schedule = self.get_day_schedule(day_name)
        if not day_schedule or not day_schedule.get('is_active', False):
            return None, None
        
        start_time_str = day_schedule.get('start_time')
        end_time_str = day_schedule.get('end_time')
        
        try:
            start_time = time.fromisoformat(start_time_str) if start_time_str else None
            end_time = time.fromisoformat(end_time_str) if end_time_str else None
            return start_time, end_time
        except:
            return None, None

"""
مثال على هيكل daily_schedule في JSON:
{
    "monday": {
        "is_active": true,
        "start_time": "08:00:00",
        "end_time": "18:00:00"
    },
    "tuesday": {
        "is_active": true,
        "start_time": "08:00:00",
        "end_time": "18:00:00"
    },
    "wednesday": {
        "is_active": true,
        "start_time": "10:00:00",
        "end_time": "16:00:00"
    },
    "thursday": {
        "is_active": true,
        "start_time": "10:00:00",
        "end_time": "16:00:00"
    },
    "friday": {
        "is_active": false
    },
    "saturday": {
        "is_active": false
    },
    "sunday": {
        "is_active": false
    }
}
"""
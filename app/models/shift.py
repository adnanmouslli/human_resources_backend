# shift.py

from app import db
from datetime import time, date, datetime, timedelta

# Python weekday(): Monday=0 ... Sunday=6
_WEEKDAY_NAME_TO_INDEX = {
    'monday': 0,
    'tuesday': 1,
    'wednesday': 2,
    'thursday': 3,
    'friday': 4,
    'saturday': 5,
    'sunday': 6,
}

_WEEKDAY_INDEX_TO_NAME = {v: k for k, v in _WEEKDAY_NAME_TO_INDEX.items()}


def _as_date(value):
    """تطبيع date/datetime/str إلى date."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value[:10])
    return value


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

    # التناوب الأسبوعي (اختياري — مغلق افتراضياً؛ لا يؤثر على الورديات الحالية)
    weekly_rotation_enabled = db.Column(db.Boolean, nullable=False, default=False)
    alternate_daily_schedule = db.Column(db.JSON, nullable=True)  # جدول الأسبوع المقابل
    rotation_week_start_day = db.Column(db.String(20), nullable=False, default='saturday')
    rotation_anchor_date = db.Column(db.Date, nullable=True)  # تاريخ يقع في أول أسبوع من النوع A

    def __repr__(self):
        return f"<Shift {self.name}>"
    
    def get_day_schedule(self, day_name, schedule=None):
        """
        الحصول على جدول يوم محدد من جدول معيّن (أو daily_schedule افتراضياً)
        day_name: اسم اليوم بالإنجليزية (monday, tuesday, etc.)
        """
        source = schedule if schedule is not None else self.daily_schedule
        if not source:
            return None
        return source.get(day_name.lower())
    
    def is_working_day(self, day_name, schedule=None):
        """
        التحقق من كون اليوم يوم عمل ضمن جدول معيّن (أو daily_schedule)
        للتوافق العكسي: بدون تمرير schedule يبقى السلوك القديم.
        """
        day_schedule = self.get_day_schedule(day_name, schedule=schedule)
        return day_schedule is not None and day_schedule.get('is_active', False)
    
    def get_day_times(self, day_name, schedule=None):
        """
        الحصول على أوقات الدخول والخروج ليوم محدد من جدول معيّن
        """
        day_schedule = self.get_day_schedule(day_name, schedule=schedule)
        if not day_schedule or not day_schedule.get('is_active', False):
            return None, None
        
        start_time_str = day_schedule.get('start_time')
        end_time_str = day_schedule.get('end_time')
        
        try:
            start_time = time.fromisoformat(start_time_str) if start_time_str else None
            end_time = time.fromisoformat(end_time_str) if end_time_str else None
            return start_time, end_time
        except Exception:
            return None, None

    @staticmethod
    def week_start_for_date(target_date, week_start_day='saturday'):
        """بداية أسبوع التناوب الذي يقع فيه التاريخ."""
        target_date = _as_date(target_date)
        week_start_day = (week_start_day or 'saturday').lower()
        start_idx = _WEEKDAY_NAME_TO_INDEX.get(week_start_day, 5)
        delta = (target_date.weekday() - start_idx) % 7
        return target_date - timedelta(days=delta)

    def get_effective_daily_schedule(self, target_date):
        """
        إرجاع الجدول الفعّال لتاريخ معيّن.
        بدون تناوب → daily_schedule دائماً.
        مع تناوب: أسابيع زوجية من الـ anchor → daily_schedule، فردية → alternate.
        """
        if not getattr(self, 'weekly_rotation_enabled', False):
            return self.daily_schedule

        if not self.alternate_daily_schedule or not self.rotation_anchor_date:
            return self.daily_schedule

        week_start_day = getattr(self, 'rotation_week_start_day', None) or 'saturday'
        target_week_start = self.week_start_for_date(target_date, week_start_day)
        anchor = _as_date(self.rotation_anchor_date)
        anchor_week_start = self.week_start_for_date(anchor, week_start_day)

        weeks_since_anchor = (target_week_start - anchor_week_start).days // 7
        if weeks_since_anchor % 2 == 0:
            return self.daily_schedule
        return self.alternate_daily_schedule

    def get_schedule_for_date(self, target_date):
        """
        الحصول على (is_working_day, start_time, end_time) لتاريخ محدد
        مع احترام التناوب الأسبوعي إن كان مفعّلاً.
        """
        target_date = _as_date(target_date)
        schedule = self.get_effective_daily_schedule(target_date)
        if not schedule:
            return False, None, None

        day_name = _WEEKDAY_INDEX_TO_NAME.get(target_date.weekday())
        day_schedule = schedule.get(day_name, {}) if day_name else {}

        if not day_schedule.get('is_active', False):
            return False, None, None

        try:
            start_time = time.fromisoformat(day_schedule.get('start_time', ''))
            end_time = time.fromisoformat(day_schedule.get('end_time', ''))
            return True, start_time, end_time
        except (ValueError, TypeError):
            return False, None, None

    def is_working_day_for_date(self, target_date):
        is_working, _, _ = self.get_schedule_for_date(target_date)
        return is_working


"""
مثال على هيكل daily_schedule في JSON:
{
    "monday": {
        "is_active": true,
        "start_time": "08:00:00",
        "end_time": "18:00:00"
    },
    ...
}

عند تفعيل التناوب الأسبوعي:
- daily_schedule = جدول الأسبوع A (من تاريخ rotation_anchor_date)
- alternate_daily_schedule = جدول الأسبوع B (الأسبوع التالي)
- rotation_week_start_day = 'saturday' افتراضياً
"""

# app/services/kpi_frequency_service.py
# خدمة تحديد تكرار التقييم لكل معيار

from datetime import date, timedelta
import calendar


class KpiFrequencyService:
    """
    تُحدد هذه الخدمة ما إذا كان معيار معين مستحقاً في يوم معين،
    بناءً على إعداد تكرار التقييم الخاص بكل معيار.

    أنواع التكرار المدعومة:
      daily        - كل يوم عمل
      every_n_days - كل N أيام (من تاريخ بداية الربط)
      weekly       - مرة أسبوعياً في يوم محدد
      biweekly     - كل أسبوعين (الأسابيع الفردية من الشهر)
      monthly      - مرة شهرياً في يوم محدد أو آخر يوم عمل
    """

    @staticmethod
    def is_due(criterion, employee_id: int, check_date: date, assignment_start_date: date = None) -> bool:
        """
        هل هذا المعيار مستحق التقييم في التاريخ المحدد؟

        Args:
            criterion:            كائن KpiCriterion
            employee_id:          معرّف الموظف (للمرجع)
            check_date:           التاريخ المطلوب فحصه
            assignment_start_date: تاريخ بداية ربط الموظف بالقالب
        Returns:
            True إذا كان المعيار مستحقاً، False إذا لم يكن
        """
        freq = criterion.frequency_type
        val  = criterion.frequency_value

        if freq == 'daily':
            # كل يوم عمل مستحق
            return True

        elif freq == 'every_n_days':
            # كل N أيام من تاريخ البداية
            if not val or val <= 0:
                return True
            if not assignment_start_date:
                return True
            delta = (check_date - assignment_start_date).days
            return delta % val == 0

        elif freq == 'weekly':
            # val = رقم اليوم: 0=أحد, 1=اثنين, ..., 6=سبت
            if val is None:
                return False
            # Python weekday: 0=Mon ... 6=Sun
            # نحوّل: 0=Sun → isoweekday: Sun=7, Mon=1...
            # أسهل: نستخدم isoweekday() ونحوّل val من 0-indexed-Sunday
            # val=0 (أحد) → isoweekday=7
            # val=1 (اثنين) → isoweekday=1
            # val=6 (سبت) → isoweekday=6
            iso_map = {0: 7, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6}
            return check_date.isoweekday() == iso_map.get(val, -1)

        elif freq == 'biweekly':
            # الأسابيع الفردية من الشهر (الأسبوع 1 و3)
            # نحسب رقم الأسبوع داخل الشهر
            week_of_month = KpiFrequencyService._week_of_month(check_date)
            return week_of_month % 2 == 1  # الأول والثالث

        elif freq == 'monthly':
            # val = رقم اليوم في الشهر، null = آخر يوم عمل في الشهر
            if val is None:
                # آخر يوم في الشهر
                last_day = calendar.monthrange(check_date.year, check_date.month)[1]
                return check_date.day == last_day
            else:
                return check_date.day == val

        return False

    @staticmethod
    def get_due_criteria(template_id: int, employee_id: int, check_date: date,
                         assignment_start_date: date = None) -> list:
        """
        جلب جميع المعايير المستحقة لموظف في يوم محدد.

        Returns:
            قائمة بكائنات KpiCriterion المستحقة
        """
        from app.models.kpi import KpiCriterion
        criteria = KpiCriterion.query.filter_by(template_id=template_id).all()
        due = []
        for c in criteria:
            if KpiFrequencyService.is_due(c, employee_id, check_date, assignment_start_date):
                due.append(c)
        return due

    @staticmethod
    def get_next_due_date(criterion, employee_id: int, from_date: date,
                          assignment_start_date: date = None) -> date:
        """
        إيجاد أقرب تاريخ مستحق لمعيار معين ابتداءً من from_date.
        يُستخدم لعرض "التقييم التالي: [تاريخ]" في الواجهة.
        """
        check = from_date
        for _ in range(400):  # حد أقصى 400 يوم للبحث
            check = check + timedelta(days=1)
            if KpiFrequencyService.is_due(criterion, employee_id, check, assignment_start_date):
                return check
        return None

    @staticmethod
    def _week_of_month(d: date) -> int:
        """حساب رقم الأسبوع داخل الشهر (1-5)."""
        first_day_of_month = d.replace(day=1)
        dom = d.day
        adjusted_dom = dom + first_day_of_month.weekday()
        return int(adjusted_dom / 7) + 1

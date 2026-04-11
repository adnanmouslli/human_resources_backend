# app/services/kpi_scoring_service.py
# خدمة حساب درجات KPI والملخص الشهري

from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from typing import Optional
from app import db
from app.models.kpi import (
    KpiDailyEvaluation, KpiCriterionScore, KpiMonthlySummary,
    KpiEmployeeAssignment, KpiSettings
)
from app.models.attendance import Attendance
from app.services.kpi_frequency_service import KpiFrequencyService


class KpiScoringService:
    """
    خدمة حساب نتائج KPI.

    القاعدة الأساسية (القانون الذهبي):
      monthly_percentage = Σ(total_score لأيام الحضور المقيّمة)
                           ÷ Σ(max_possible_score لنفس الأيام) × 100

      ← لا تُحتسب أيام الغياب أو الإجازة في أي حساب
      ← المقام = مجموع الدرجات القصوى للأيام التي تم تقييمها فعلاً
    """

    @staticmethod
    def get_attended_days(employee_id: int, year: int, month: int) -> list:
        """
        جلب أيام الحضور الفعلي (status='present') من جدول الحضور.
        هذه الأيام هي الوحيدة التي يُحتسب فيها التقييم.

        Returns:
            قائمة بكائنات Attendance للأيام الحضور
        """
        from sqlalchemy import extract
        attendances = Attendance.query.filter(
            Attendance.empId == employee_id,
            extract('year',  Attendance.createdAt) == year,
            extract('month', Attendance.createdAt) == month,
        ).all()

        # نُعيد فقط أيام الحضور الفعلي
        # الحضور: عندما يكون checkInTime موجوداً (أي حضر الموظف)
        # ملاحظة: جدول attendances لا يحتوي على حقل status للحضور/الغياب
        # بل يُعتبر الموظف حاضراً إذا كان له سجل حضور في ذلك اليوم مع checkInTime
        present_days = [a for a in attendances if a.checkInTime is not None]
        return present_days

    @staticmethod
    def get_attended_dates(employee_id: int, year: int, month: int) -> list:
        """
        جلب تواريخ أيام الحضور كقائمة من date objects.
        """
        attendances = KpiScoringService.get_attended_days(employee_id, year, month)
        return [a.createdAt for a in attendances]

    @staticmethod
    def get_active_assignment(employee_id: int, check_date: date = None) -> 'KpiEmployeeAssignment':
        """
        جلب الربط النشط بين الموظف وقالب KPI في تاريخ محدد.
        """
        if check_date is None:
            check_date = date.today()

        assignment = KpiEmployeeAssignment.query.filter(
            KpiEmployeeAssignment.employee_id == employee_id,
            KpiEmployeeAssignment.is_active == True,
            KpiEmployeeAssignment.start_date <= check_date,
            db.or_(
                KpiEmployeeAssignment.end_date == None,
                KpiEmployeeAssignment.end_date >= check_date,
            )
        ).first()
        return assignment

    @staticmethod
    def get_assignment_for_date(employee_id: int, check_date: date) -> Optional[KpiEmployeeAssignment]:
        """
        الربط الذي كان سارياً في تاريخ محدد (بما في ذلك بعد إلغاء الربط: is_active=False).
        يُستخدم لإعادة حساب ملخصات أشهر سابقة دون الاعتماد على الربط «النشط» الحالي فقط.
        """
        return KpiEmployeeAssignment.query.filter(
            KpiEmployeeAssignment.employee_id == employee_id,
            KpiEmployeeAssignment.start_date <= check_date,
            db.or_(
                KpiEmployeeAssignment.end_date == None,
                KpiEmployeeAssignment.end_date >= check_date,
            ),
        ).order_by(KpiEmployeeAssignment.start_date.desc()).first()

    @staticmethod
    def compute_daily_score(employee_id: int, eval_date: date) -> dict:
        """
        حساب أو جلب درجات موظف في يوم محدد.

        Returns:
            dict مع: total, max, percentage, evaluation (أو None)
        """
        evaluation = KpiDailyEvaluation.query.filter_by(
            employee_id=employee_id,
            evaluation_date=eval_date,
        ).first()

        if not evaluation:
            return {'total': 0, 'max': 0, 'percentage': 0, 'evaluation': None}

        total = float(evaluation.total_score or 0)
        max_s = float(evaluation.max_possible_score or 0)
        pct   = (total / max_s * 100) if max_s > 0 else 0
        return {
            'total': total,
            'max': max_s,
            'percentage': round(pct, 2),
            'evaluation': evaluation,
        }

    @staticmethod
    def compute_monthly_summary(employee_id: int, year: int, month: int) -> 'KpiMonthlySummary':
        """
        إعادة حساب الملخص الشهري لموظف.

        الخوارزمية:
          1. جلب أيام الحضور الفعلي من جدول الحضور
          2. لكل يوم حضور → جلب التقييم اليومي إن وُجد
          3. جمع الدرجات من الأيام التي لها تقييم فقط
          4. monthly_percentage = Σscores / Σmax_scores * 100
          5. حفظ الملخص (upsert) في kpi_monthly_summaries

        لا تُستخدم أيام الغياب أو الإجازة في أي حساب.
        """
        settings = KpiSettings.get()

        from datetime import date as date_cls
        import calendar as cal_mod
        last_day = cal_mod.monthrange(year, month)[1]
        month_end = date_cls(year, month, last_day)

        from sqlalchemy import extract
        evaluations = KpiDailyEvaluation.query.filter(
            KpiDailyEvaluation.employee_id == employee_id,
            extract('year',  KpiDailyEvaluation.evaluation_date) == year,
            extract('month', KpiDailyEvaluation.evaluation_date) == month,
            KpiDailyEvaluation.status != 'draft',
        ).all()

        # قالب الشهر: الربط الساري في نهاية الشهر (حتى المُلغى)، أو الأكثر شيوعاً في التقييمات
        assignment_cov = KpiScoringService.get_assignment_for_date(employee_id, month_end)
        if assignment_cov:
            template_id = assignment_cov.template_id
        elif evaluations:
            template_id = Counter(ev.template_id for ev in evaluations).most_common(1)[0][0]
        else:
            template_id = None

        if template_id is None:
            return None

        # أيام الحضور الفعلي في الشهر
        attended_dates = KpiScoringService.get_attended_dates(employee_id, year, month)
        total_attended = len(attended_dates)

        eval_map = {ev.evaluation_date: ev for ev in evaluations}

        # حساب الإجماليات
        # ← نحتسب فقط الأيام التي فيها: حضور + تقييم
        total_score      = 0.0
        max_possible     = 0.0
        evaluated_days   = 0

        for att_date in attended_dates:
            ev = eval_map.get(att_date)
            if ev:
                total_score  += float(ev.total_score or 0)
                max_possible += float(ev.max_possible_score or 0)
                evaluated_days += 1

        # النسبة الشهرية (القانون الذهبي)
        if max_possible > 0:
            monthly_pct = round(total_score / max_possible * 100, 2)
        else:
            monthly_pct = 0.0

        grade = settings.get_grade(monthly_pct) if evaluated_days > 0 else 'not_evaluated'

        # upsert الملخص الشهري
        summary = KpiMonthlySummary.query.filter_by(
            employee_id=employee_id,
            year=year,
            month=month,
        ).first()

        if not summary:
            summary = KpiMonthlySummary(
                employee_id=employee_id,
                year=year,
                month=month,
            )
            db.session.add(summary)

        summary.template_id          = template_id
        summary.total_attended_days  = total_attended
        summary.total_evaluable_days = total_attended  # كل أيام الحضور قابلة للتقييم
        summary.evaluated_days       = evaluated_days
        summary.total_score          = total_score
        summary.max_possible_score   = max_possible
        summary.monthly_percentage   = monthly_pct
        summary.performance_grade    = grade
        summary.computed_at          = datetime.now()

        db.session.commit()
        return summary

    @staticmethod
    def get_month_calendar(employee_id: int, year: int, month: int) -> list:
        """
        تقويم شهري يُظهر لكل يوم: حالة الحضور + حالة التقييم + النسبة اليومية.
        يُستخدم في شاشة التقييم اليومي.

        Returns:
            قائمة من dicts لكل يوم في الشهر
        """
        import calendar as cal_mod
        from datetime import date as date_cls

        first_day, num_days = cal_mod.monthrange(year, month)
        attended_dates = set(KpiScoringService.get_attended_dates(employee_id, year, month))

        # جلب جميع التقييمات في الشهر
        from sqlalchemy import extract
        evaluations = KpiDailyEvaluation.query.filter(
            KpiDailyEvaluation.employee_id == employee_id,
            extract('year',  KpiDailyEvaluation.evaluation_date) == year,
            extract('month', KpiDailyEvaluation.evaluation_date) == month,
        ).all()
        eval_map = {ev.evaluation_date: ev for ev in evaluations}

        result = []
        for day in range(1, num_days + 1):
            d = date_cls(year, month, day)
            is_attended = d in attended_dates
            ev = eval_map.get(d)

            if not is_attended:
                att_status = 'absent'
                eval_status = 'not_applicable'
            elif ev:
                att_status = 'present'
                eval_status = ev.status
            else:
                att_status = 'present'
                eval_status = 'missing'

            result.append({
                'date': d.isoformat(),
                'day': day,
                'weekday': d.isoweekday(),  # 1=Mon...7=Sun
                'attendance_status': att_status,
                'evaluation_status': eval_status,
                'daily_percentage': float(ev.daily_percentage) if ev else None,
                'evaluation_id': ev.id if ev else None,
            })

        return result

"""
اختبارات شاملة لخدمة حد السلف (advance_limit_service).
تعمل بدون قاعدة بيانات حقيقية عبر mock لطبقة SQLAlchemy.
"""
from __future__ import annotations

import unittest
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from tests._bootstrap_advance_limit import load_advance_limit_service

svc = load_advance_limit_service()

AdvanceLimitError = svc.AdvanceLimitError
VALID_MODES = svc.VALID_MODES
VALID_PERIODS = svc.VALID_PERIODS
_parse_date = svc._parse_date
_to_float = svc._to_float
build_limit_status = svc.build_limit_status
compute_base_salary = svc.compute_base_salary
compute_cap = svc.compute_cap
employee_limit_fields_payload = svc.employee_limit_fields_payload
get_limit_mode = svc.get_limit_mode
get_limit_period = svc.get_limit_period
get_period_window = svc.get_period_window
get_used_amount = svc.get_used_amount
normalize_limit_fields_from_data = svc.normalize_limit_fields_from_data
validate_advance_request = svc.validate_advance_request


def make_employee(**kwargs):
    defaults = dict(
        id=1,
        salary=5000,
        allowances=0,
        advancePercentage=20,
        advance_limit_mode='percentage',
        advance_fixed_limit=None,
        advance_limit_period='monthly',
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestHelpers(unittest.TestCase):
    def test_to_float_none_and_invalid(self):
        self.assertEqual(_to_float(None), 0.0)
        self.assertEqual(_to_float(''), 0.0)
        self.assertEqual(_to_float('abc', 7), 7)
        self.assertEqual(_to_float('12.5'), 12.5)

    def test_parse_date_formats(self):
        self.assertEqual(_parse_date('2026-11-19'), date(2026, 11, 19))
        self.assertEqual(_parse_date('19/11/2026'), date(2026, 11, 19))
        self.assertEqual(_parse_date('19-11-2026'), date(2026, 11, 19))
        self.assertEqual(_parse_date('2026/11/19'), date(2026, 11, 19))
        self.assertEqual(_parse_date('2026-11-19T15:30:00Z'), date(2026, 11, 19))
        self.assertEqual(_parse_date(datetime(2026, 5, 1, 12, 0)), date(2026, 5, 1))
        self.assertEqual(_parse_date(date(2026, 1, 2)), date(2026, 1, 2))

    def test_parse_date_none_returns_today(self):
        self.assertEqual(_parse_date(None), date.today())


class TestPeriodWindow(unittest.TestCase):
    def test_daily(self):
        start, end = get_period_window('daily', date(2026, 11, 19))
        self.assertEqual(start, date(2026, 11, 19))
        self.assertEqual(end, date(2026, 11, 20))

    def test_weekly_iso_monday_start(self):
        # 2026-11-19 = Thursday → week starts Monday 2026-11-16
        start, end = get_period_window('weekly', date(2026, 11, 19))
        self.assertEqual(start, date(2026, 11, 16))
        self.assertEqual(end, date(2026, 11, 23))

    def test_weekly_on_monday(self):
        start, end = get_period_window('weekly', date(2026, 11, 16))
        self.assertEqual(start, date(2026, 11, 16))
        self.assertEqual(end, date(2026, 11, 23))

    def test_monthly(self):
        start, end = get_period_window('monthly', date(2026, 11, 19))
        self.assertEqual(start, date(2026, 11, 1))
        self.assertEqual(end, date(2026, 12, 1))

    def test_monthly_december_rollover(self):
        start, end = get_period_window('monthly', date(2026, 12, 31))
        self.assertEqual(start, date(2026, 12, 1))
        self.assertEqual(end, date(2027, 1, 1))

    def test_unknown_period_defaults_monthly(self):
        start, end = get_period_window('weird', date(2026, 3, 15))
        self.assertEqual(start, date(2026, 3, 1))
        self.assertEqual(end, date(2026, 4, 1))


class TestCapCalculation(unittest.TestCase):
    def test_percentage_cap_salary_plus_allowances(self):
        emp = make_employee(salary=5000, allowances=1000, advancePercentage=20)
        self.assertEqual(compute_cap(emp), 1200.0)

    def test_percentage_cap_plan_scenario(self):
        emp = make_employee(salary=5000, allowances=0, advancePercentage=20)
        self.assertEqual(compute_cap(emp), 1000.0)

    def test_percentage_zero_or_null_unconfigured(self):
        self.assertIsNone(compute_cap(make_employee(advancePercentage=0)))
        self.assertIsNone(compute_cap(make_employee(advancePercentage=None)))

    def test_fixed_cap(self):
        emp = make_employee(
            advance_limit_mode='fixed',
            advance_fixed_limit=200,
            advancePercentage=0,
        )
        self.assertEqual(compute_cap(emp), 200.0)

    def test_fixed_cap_zero_or_null_unconfigured(self):
        self.assertIsNone(
            compute_cap(make_employee(advance_limit_mode='fixed', advance_fixed_limit=0))
        )
        self.assertIsNone(
            compute_cap(make_employee(advance_limit_mode='fixed', advance_fixed_limit=None))
        )

    def test_invalid_mode_falls_back_to_percentage(self):
        emp = make_employee(advance_limit_mode='unknown', advancePercentage=10, salary=1000)
        self.assertEqual(get_limit_mode(emp), 'percentage')
        self.assertEqual(compute_cap(emp), 100.0)

    def test_base_salary(self):
        self.assertEqual(compute_base_salary(make_employee(salary=4000, allowances=500)), 4500.0)

    def test_default_period_monthly(self):
        self.assertEqual(get_limit_period(make_employee(advance_limit_period=None)), 'monthly')
        self.assertEqual(get_limit_period(make_employee(advance_limit_period='daily')), 'daily')


class TestNormalizeFields(unittest.TestCase):
    def test_valid_payload(self):
        result = normalize_limit_fields_from_data({
            'advance_limit_mode': 'Fixed',
            'advance_limit_period': 'WEEKLY',
            'advance_fixed_limit': '250.5',
            'advancePercentage': '15',
        })
        self.assertEqual(result['advance_limit_mode'], 'fixed')
        self.assertEqual(result['advance_limit_period'], 'weekly')
        self.assertEqual(result['advance_fixed_limit'], 250.5)
        self.assertEqual(result['advancePercentage'], 15.0)

    def test_null_clears_values(self):
        result = normalize_limit_fields_from_data({
            'advance_fixed_limit': None,
            'advancePercentage': '',
        })
        self.assertIsNone(result['advance_fixed_limit'])
        self.assertIsNone(result['advancePercentage'])

    def test_invalid_mode(self):
        with self.assertRaises(ValueError):
            normalize_limit_fields_from_data({'advance_limit_mode': 'percent'})

    def test_invalid_period(self):
        with self.assertRaises(ValueError):
            normalize_limit_fields_from_data({'advance_limit_period': 'yearly'})

    def test_negative_fixed(self):
        with self.assertRaises(ValueError):
            normalize_limit_fields_from_data({'advance_fixed_limit': -1})

    def test_percentage_out_of_range(self):
        with self.assertRaises(ValueError):
            normalize_limit_fields_from_data({'advancePercentage': 101})
        with self.assertRaises(ValueError):
            normalize_limit_fields_from_data({'advancePercentage': -5})

    def test_valid_modes_and_periods_constants(self):
        self.assertEqual(set(VALID_MODES), {'percentage', 'fixed'})
        self.assertEqual(set(VALID_PERIODS), {'daily', 'weekly', 'monthly'})


class TestEmployeePayload(unittest.TestCase):
    def test_payload_shape(self):
        emp = make_employee(
            advance_limit_mode='fixed',
            advance_fixed_limit=300,
            advance_limit_period='daily',
            advancePercentage=10,
        )
        payload = employee_limit_fields_payload(emp)
        self.assertEqual(payload['advance_limit_mode'], 'fixed')
        self.assertEqual(payload['advance_fixed_limit'], 300.0)
        self.assertEqual(payload['advance_limit_period'], 'daily')
        self.assertEqual(payload['advancePercentage'], 10.0)


class TestUsedAmount(unittest.TestCase):
    def test_used_includes_recorded_and_pending(self):
        with patch.object(svc, '_sum_pending_transactions', return_value=150.0), \
             patch.object(svc, '_sum_recorded_advances', return_value=250.0):
            used = get_used_amount(1, date(2026, 11, 1), date(2026, 12, 1))
        self.assertEqual(used, 400.0)


class TestBuildStatusAndValidate(unittest.TestCase):
    def test_status_percentage_monthly_full_remaining(self):
        emp = make_employee(salary=5000, allowances=0, advancePercentage=20)
        with patch.object(svc, 'get_used_amount', return_value=0.0):
            status = build_limit_status(emp, ref_date='2026-11-19')
        self.assertTrue(status['configured'])
        self.assertTrue(status['allowed'])
        self.assertEqual(status['cap'], 1000.0)
        self.assertEqual(status['remaining'], 1000.0)
        self.assertEqual(status['period'], 'monthly')
        self.assertEqual(status['period_label'], 'الشهر')
        self.assertEqual(status['period_start'], '2026-11-01')

    def test_status_exhausted_not_allowed(self):
        emp = make_employee(salary=5000, advancePercentage=20)
        with patch.object(svc, 'get_used_amount', return_value=1000.0):
            status = build_limit_status(emp, ref_date='2026-11-19')
        self.assertTrue(status['configured'])
        self.assertFalse(status['allowed'])
        self.assertEqual(status['remaining'], 0.0)

    def test_status_unconfigured(self):
        emp = make_employee(advancePercentage=0, advance_limit_mode='percentage')
        with patch.object(svc, 'get_used_amount', return_value=0.0):
            status = build_limit_status(emp)
        self.assertFalse(status['configured'])
        self.assertFalse(status['allowed'])
        self.assertIsNone(status['cap'])
        self.assertEqual(status['remaining'], 0.0)

    def test_status_fixed_daily(self):
        emp = make_employee(
            advance_limit_mode='fixed',
            advance_fixed_limit=200,
            advance_limit_period='daily',
            advancePercentage=0,
        )
        with patch.object(svc, 'get_used_amount', return_value=50.0):
            status = build_limit_status(emp, ref_date='2026-11-19')
        self.assertEqual(status['cap'], 200.0)
        self.assertEqual(status['remaining'], 150.0)
        self.assertEqual(status['period_label'], 'اليوم')
        self.assertEqual(status['period_start'], '2026-11-19')

    def test_validate_rejects_non_positive_amount(self):
        with self.assertRaises(AdvanceLimitError) as ctx:
            validate_advance_request(make_employee(), 0)
        self.assertIn('أكبر من صفر', ctx.exception.message)

    def test_validate_rejects_unconfigured(self):
        emp = make_employee(advancePercentage=0)
        with patch.object(svc, 'get_used_amount', return_value=0.0):
            with self.assertRaises(AdvanceLimitError) as ctx:
                validate_advance_request(emp, 100)
        self.assertIn('لا يوجد حد سلفة', ctx.exception.message)

    def test_validate_plan_scenario_second_request_rejected(self):
        """راتب 5000 ونسبة 20% → سقف 1000؛ بعد 600 طلب 500 يُرفض."""
        emp = make_employee(salary=5000, allowances=0, advancePercentage=20)
        with patch.object(svc, 'get_used_amount', return_value=600.0):
            with self.assertRaises(AdvanceLimitError) as ctx:
                validate_advance_request(emp, 500, ref_date='2026-11-19')
        msg = ctx.exception.message
        self.assertIn('تجاوز حد السلفة', msg)
        self.assertIn('1000.00', msg)
        self.assertIn('400.00', msg)
        self.assertIn('500.00', msg)

    def test_validate_plan_scenario_first_request_ok(self):
        emp = make_employee(salary=5000, allowances=0, advancePercentage=20)
        with patch.object(svc, 'get_used_amount', return_value=0.0):
            status = validate_advance_request(emp, 600, ref_date='2026-11-19')
        self.assertEqual(status['remaining'], 1000.0)

    def test_validate_fixed_daily_stacking_rejected(self):
        emp = make_employee(
            advance_limit_mode='fixed',
            advance_fixed_limit=200,
            advance_limit_period='daily',
        )
        with patch.object(svc, 'get_used_amount', return_value=150.0):
            with self.assertRaises(AdvanceLimitError):
                validate_advance_request(emp, 100, ref_date='2026-11-19')

    def test_validate_exact_remaining_allowed(self):
        emp = make_employee(
            advance_limit_mode='fixed',
            advance_fixed_limit=200,
            advance_limit_period='daily',
        )
        with patch.object(svc, 'get_used_amount', return_value=150.0):
            status = validate_advance_request(emp, 50, ref_date='2026-11-19')
        self.assertEqual(status['remaining'], 50.0)

    def test_validate_passes_exclude_transaction_id(self):
        emp = make_employee(salary=5000, advancePercentage=20)
        with patch.object(svc, 'get_used_amount', return_value=900.0) as used_mock:
            validate_advance_request(emp, 50, ref_date='2026-11-10', exclude_transaction_id=99)
        self.assertEqual(used_mock.call_args[0][3], 99)


class TestPendingTransactionsFiltering(unittest.TestCase):
    def test_sum_pending_filters_by_window_and_exclude(self):
        tx_in = SimpleNamespace(
            id=1,
            created_at=datetime(2026, 11, 5, 10, 0),
            get_details=lambda: {'amount': 100, 'date': '2026-11-05'},
        )
        tx_out = SimpleNamespace(
            id=2,
            created_at=datetime(2026, 10, 1, 10, 0),
            get_details=lambda: {'amount': 999, 'date': '2026-10-01'},
        )

        query = MagicMock()
        query.filter.return_value = query
        query.all.return_value = [tx_in, tx_out]

        with patch.object(svc.Transaction, 'query') as q:
            q.filter.return_value = query
            total = svc._sum_pending_transactions(
                1, date(2026, 11, 1), date(2026, 12, 1)
            )
            self.assertEqual(total, 100.0)

            query2 = MagicMock()
            query2.filter.return_value = query2
            query2.all.return_value = [tx_in]
            q.filter.return_value = query2
            total2 = svc._sum_pending_transactions(
                1, date(2026, 11, 1), date(2026, 12, 1), exclude_transaction_id=3
            )
            self.assertEqual(total2, 100.0)
            query2.filter.assert_called()


class TestRecordedAdvancesQuery(unittest.TestCase):
    def test_sum_recorded_uses_scalar(self):
        class _Col:
            def __eq__(self, other):
                return True

            def __ge__(self, other):
                return True

            def __lt__(self, other):
                return True

            def __hash__(self):
                return id(self)

        chain = MagicMock()
        chain.filter.return_value = chain
        chain.scalar.return_value = 321.5
        svc.db.session.query.return_value = chain
        svc.db.func.coalesce.return_value = 'coalesce'
        svc.db.func.sum.return_value = 'sum'

        original_date = svc.Advance.date
        original_employee_id = svc.Advance.employee_id
        original_amount = svc.Advance.amount
        try:
            svc.Advance.date = _Col()
            svc.Advance.employee_id = _Col()
            svc.Advance.amount = _Col()
            total = svc._sum_recorded_advances(7, date(2026, 11, 1), date(2026, 12, 1))
        finally:
            svc.Advance.date = original_date
            svc.Advance.employee_id = original_employee_id
            svc.Advance.amount = original_amount

        self.assertEqual(total, 321.5)
        chain.filter.assert_called_once()
        chain.scalar.assert_called_once()


if __name__ == '__main__':
    unittest.main(verbosity=2)

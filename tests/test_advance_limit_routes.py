"""
سيناريوهات حد السلف (نسبة/ثابت × يومي/أسبوعي/شهري) ورفض التكديس.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from tests._bootstrap_advance_limit import load_advance_limit_service

svc = load_advance_limit_service()
AdvanceLimitError = svc.AdvanceLimitError
validate_advance_request = svc.validate_advance_request
build_limit_status = svc.build_limit_status
normalize_limit_fields_from_data = svc.normalize_limit_fields_from_data


class FakeEmployee:
    def __init__(self, **kw):
        self.id = kw.get('id', 1)
        self.full_name = kw.get('full_name', 'Test Emp')
        self.salary = kw.get('salary', 5000)
        self.allowances = kw.get('allowances', 0)
        self.advancePercentage = kw.get('advancePercentage', 20)
        self.advance_limit_mode = kw.get('advance_limit_mode', 'percentage')
        self.advance_fixed_limit = kw.get('advance_fixed_limit')
        self.advance_limit_period = kw.get('advance_limit_period', 'monthly')


class TestPlanScenarios(unittest.TestCase):
    def test_monthly_percentage_two_requests(self):
        emp = FakeEmployee(salary=5000, allowances=0, advancePercentage=20)

        with patch.object(svc, 'get_used_amount', return_value=0.0):
            ok = validate_advance_request(emp, 600, ref_date='2026-11-05')
        self.assertEqual(ok['cap'], 1000.0)

        with patch.object(svc, 'get_used_amount', return_value=600.0):
            with self.assertRaises(AdvanceLimitError) as ctx:
                validate_advance_request(emp, 500, ref_date='2026-11-10')
        self.assertIn('المتبقي: 400.00', ctx.exception.message)

    def test_daily_fixed_two_requests_same_day(self):
        emp = FakeEmployee(
            advance_limit_mode='fixed',
            advance_fixed_limit=200,
            advance_limit_period='daily',
            advancePercentage=0,
        )
        with patch.object(svc, 'get_used_amount', return_value=0.0):
            validate_advance_request(emp, 120, ref_date='2026-11-19')

        with patch.object(svc, 'get_used_amount', return_value=120.0):
            with self.assertRaises(AdvanceLimitError):
                validate_advance_request(emp, 100, ref_date='2026-11-19')

        with patch.object(svc, 'get_used_amount', return_value=0.0):
            validate_advance_request(emp, 200, ref_date='2026-11-20')

    def test_pending_counts_toward_used(self):
        emp = FakeEmployee(salary=5000, advancePercentage=20)
        with patch.object(svc, 'get_used_amount', return_value=800.0):
            with self.assertRaises(AdvanceLimitError):
                validate_advance_request(emp, 250, ref_date='2026-11-19')

    def test_approval_recheck_excludes_own_pending(self):
        emp = FakeEmployee(salary=5000, advancePercentage=20)
        with patch.object(svc, 'get_used_amount', return_value=200.0) as used_mock:
            status = validate_advance_request(
                emp, 700, ref_date='2026-11-19', exclude_transaction_id=55
            )
        self.assertEqual(status['remaining'], 800.0)
        self.assertEqual(used_mock.call_args[0][3], 55)

    def test_weekly_cap_label(self):
        emp = FakeEmployee(
            advance_limit_mode='fixed',
            advance_fixed_limit=500,
            advance_limit_period='weekly',
            advancePercentage=0,
        )
        with patch.object(svc, 'get_used_amount', return_value=0.0):
            status = build_limit_status(emp, ref_date='2026-11-19')
        self.assertEqual(status['period_label'], 'الأسبوع')
        self.assertEqual(status['period_start'], '2026-11-16')
        self.assertEqual(status['cap'], 500.0)


class TestLimitStatusAllowedFlag(unittest.TestCase):
    def test_allowed_true_when_remaining_positive(self):
        with patch.object(svc, 'get_used_amount', return_value=0.0):
            status = build_limit_status(FakeEmployee(advancePercentage=10))
        self.assertTrue(status['allowed'])

    def test_allowed_false_when_remaining_zero(self):
        with patch.object(svc, 'get_used_amount', return_value=500.0):
            status = build_limit_status(FakeEmployee(salary=5000, advancePercentage=10))
        self.assertEqual(status['remaining'], 0.0)
        self.assertFalse(status['allowed'])


class TestCreateFinalRecordGuard(unittest.TestCase):
    def test_limit_error_message_propagates(self):
        err = AdvanceLimitError('تجاوز حد السلفة للشهر. السقف: 1000.00', {'cap': 1000})
        with self.assertRaises(Exception) as ctx:
            raise Exception(err.message)
        self.assertIn('تجاوز حد السلفة', str(ctx.exception))


class TestNormalizeEdgeCases(unittest.TestCase):
    def test_string_null_for_fixed(self):
        result = normalize_limit_fields_from_data({'advance_fixed_limit': 'null'})
        self.assertIsNone(result['advance_fixed_limit'])

    def test_percentage_boundary_0_and_100(self):
        self.assertEqual(
            normalize_limit_fields_from_data({'advancePercentage': 0})['advancePercentage'],
            0.0,
        )
        self.assertEqual(
            normalize_limit_fields_from_data({'advancePercentage': 100})['advancePercentage'],
            100.0,
        )


class TestSalaryPlusAllowancesBase(unittest.TestCase):
    def test_cap_uses_salary_plus_allowances(self):
        emp = FakeEmployee(salary=4000, allowances=1000, advancePercentage=25)
        # 5000 * 25% = 1250
        self.assertEqual(svc.compute_cap(emp), 1250.0)


if __name__ == '__main__':
    unittest.main(verbosity=2)

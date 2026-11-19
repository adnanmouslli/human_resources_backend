"""اختبارات قفل التطبيق حسب بصمة الدخول/الخروج."""
from __future__ import annotations

import unittest
from datetime import date, datetime, time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from tests._bootstrap_shift_access import load_shift_access_service

svc = load_shift_access_service()
evaluate_attendance_app_access = svc.evaluate_attendance_app_access
evaluate_user_app_access = svc.evaluate_user_app_access


def make_employee(**kw):
    return SimpleNamespace(
        id=kw.get('id', 1),
        work_system=kw.get('work_system', 'shift'),
        shift_id=kw.get('shift_id', 10),
    )


def make_user(**kw):
    return SimpleNamespace(
        id=kw.get('id', 5),
        user_type=kw.get('user_type', 'employee'),
        employee_id=kw.get('employee_id', 1),
        app_access_require_checkin=kw.get('app_access_require_checkin', False),
        allow_manual_attendance=kw.get('allow_manual_attendance', False),
        is_super_admin=lambda: kw.get('user_type') in ('super_admin', 'dev'),
        employee=kw.get('employee'),
    )


class TestAttendanceAppAccess(unittest.TestCase):
    def test_setting_disabled_allows(self):
        emp = make_employee()
        user = make_user(app_access_require_checkin=False)
        status = evaluate_attendance_app_access(emp, user=user, at=datetime(2026, 11, 19, 10, 0))
        self.assertTrue(status['allowed'])
        self.assertFalse(status['enforced'])
        self.assertEqual(status['reason'], 'setting_disabled')

    def test_no_checkin_denied_when_enabled(self):
        emp = make_employee()
        user = make_user(app_access_require_checkin=True)

        empty_q = MagicMock()
        empty_q.filter.return_value = empty_q
        empty_q.order_by.return_value = empty_q
        empty_q.first.return_value = None
        empty_q.all.return_value = []
        empty_q.count.return_value = 0

        with patch.object(svc.Attendance, 'query', empty_q):
            status = evaluate_attendance_app_access(emp, user=user, at=datetime(2026, 11, 19, 10, 0))

        self.assertFalse(status['allowed'])
        self.assertEqual(status['reason'], 'no_checkin')
        self.assertIn('بصمة الدخول', status['message'])

    def test_open_session_allows(self):
        emp = make_employee()
        user = make_user(app_access_require_checkin=True)
        open_att = SimpleNamespace(
            checkInTime=time(8, 15),
            checkOutTime=None,
            createdAt=date(2026, 11, 19),
        )

        # _today_attendance_summary then _find_open_attendance
        summary_q = MagicMock()
        summary_q.filter.return_value = summary_q
        summary_q.order_by.return_value = summary_q
        summary_q.all.return_value = [open_att]

        open_q = MagicMock()
        open_q.filter.return_value = open_q
        open_q.order_by.return_value = open_q
        open_q.first.return_value = open_att

        with patch.object(svc.Attendance, 'query') as q:
            # first call: summary, second: open
            q.filter.side_effect = [summary_q.filter.return_value, open_q.filter.return_value]
            # Actually both go through Attendance.query.filter(...)
            # Simpler: make filter return chain that serves both
            chain = MagicMock()
            chain.filter.return_value = chain
            chain.order_by.return_value = chain
            chain.all.return_value = [open_att]
            chain.first.return_value = open_att
            chain.count.return_value = 0
            q.filter.return_value = chain

            status = evaluate_attendance_app_access(emp, user=user, at=datetime(2026, 11, 19, 10, 0))

        self.assertTrue(status['allowed'])
        self.assertEqual(status['reason'], 'checked_in')
        self.assertEqual(status['check_in_time'], '08:15')

    def test_checked_out_denied(self):
        emp = make_employee()
        user = make_user(app_access_require_checkin=True)
        closed = SimpleNamespace(
            checkInTime=time(8, 0),
            checkOutTime=time(16, 30),
            createdAt=date(2026, 11, 19),
        )

        chain = MagicMock()
        chain.filter.return_value = chain
        chain.order_by.return_value = chain
        chain.all.return_value = [closed]
        chain.first.return_value = None  # no open session
        chain.count.return_value = 0

        with patch.object(svc.Attendance, 'query') as q:
            q.filter.return_value = chain
            status = evaluate_attendance_app_access(emp, user=user, at=datetime(2026, 11, 19, 17, 0))

        self.assertFalse(status['allowed'])
        self.assertEqual(status['reason'], 'checked_out')
        self.assertIn('الخروج', status['message'])

    def test_manager_exempt(self):
        user = make_user(user_type='branch_head', app_access_require_checkin=True)
        status = evaluate_user_app_access(user, at=datetime(2026, 11, 19, 3, 0))
        self.assertTrue(status['allowed'])
        self.assertEqual(status['reason'], 'manager_exempt')

    def test_user_without_employee_allowed(self):
        user = make_user(employee_id=None, employee=None, app_access_require_checkin=True)
        user.employee_id = None
        status = evaluate_user_app_access(user, at=datetime(2026, 11, 19, 10, 0))
        self.assertTrue(status['allowed'])
        self.assertEqual(status['reason'], 'no_employee')


if __name__ == '__main__':
    unittest.main(verbosity=2)

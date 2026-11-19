"""
خدمة حد السلف: حساب السقف والفترة والمستخدم (سلف معتمدة + طلبات معلّقة).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Optional, Tuple

from app import db
from app.models.advance import Advance
from app.models.transaction import Transaction


VALID_MODES = ('percentage', 'fixed')
VALID_PERIODS = ('daily', 'weekly', 'monthly')

PERIOD_LABELS = {
    'daily': 'اليوم',
    'weekly': 'الأسبوع',
    'monthly': 'الشهر',
}


class AdvanceLimitError(Exception):
    """تجاوز حد السلفة أو إعداد حد غير صالح."""

    def __init__(self, message: str, status: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.status = status or {}


def _to_float(value, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_date(value) -> date:
    if value is None:
        return date.today()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if 'T' in text:
        text = text.split('T')[0]
    elif ' ' in text:
        text = text.split(' ')[0]
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d'):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return date.today()


def get_period_window(period: str, ref_date: date) -> Tuple[date, date]:
    """يرجع (start_inclusive, end_exclusive) للفترة."""
    period = (period or 'monthly').lower()
    if period == 'daily':
        start = ref_date
        end = ref_date + timedelta(days=1)
        return start, end
    if period == 'weekly':
        # أسبوع ISO: الاثنين = 0
        start = ref_date - timedelta(days=ref_date.weekday())
        end = start + timedelta(days=7)
        return start, end
    # monthly
    start = ref_date.replace(day=1)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def get_limit_mode(employee) -> str:
    mode = (getattr(employee, 'advance_limit_mode', None) or 'percentage').lower()
    return mode if mode in VALID_MODES else 'percentage'


def get_limit_period(employee) -> str:
    period = (getattr(employee, 'advance_limit_period', None) or 'monthly').lower()
    return period if period in VALID_PERIODS else 'monthly'


def compute_base_salary(employee) -> float:
    return _to_float(employee.salary) + _to_float(employee.allowances)


def compute_cap(employee) -> Optional[float]:
    """
    يحسب سقف السلفة للفترة.
    يرجع None إذا لم يُضبط حد فعّال.
    """
    mode = get_limit_mode(employee)
    if mode == 'fixed':
        fixed = getattr(employee, 'advance_fixed_limit', None)
        if fixed is None:
            return None
        value = _to_float(fixed)
        return value if value > 0 else None

    pct = _to_float(employee.advancePercentage)
    if pct <= 0:
        return None
    base = compute_base_salary(employee)
    return round(base * pct / 100.0, 2)


def _sum_recorded_advances(employee_id: int, start: date, end: date) -> float:
    total = (
        db.session.query(db.func.coalesce(db.func.sum(Advance.amount), 0))
        .filter(
            Advance.employee_id == employee_id,
            Advance.date >= start,
            Advance.date < end,
        )
        .scalar()
    )
    return _to_float(total)


def _pending_advance_amount(details: dict) -> float:
    if not isinstance(details, dict):
        return 0.0
    return _to_float(details.get('amount'))


def _pending_advance_date(details: dict, fallback: date) -> date:
    if not isinstance(details, dict):
        return fallback
    return _parse_date(details.get('date') or fallback)


def _sum_pending_transactions(
    employee_id: int,
    start: date,
    end: date,
    exclude_transaction_id: Optional[int] = None,
) -> float:
    query = Transaction.query.filter(
        Transaction.employee_id == employee_id,
        Transaction.transaction_type == 'advance',
        Transaction.status == 'pending',
    )
    if exclude_transaction_id is not None:
        query = query.filter(Transaction.id != exclude_transaction_id)

    total = 0.0
    for tx in query.all():
        details = tx.get_details()
        tx_date = _pending_advance_date(details, (tx.created_at.date() if tx.created_at else date.today()))
        if start <= tx_date < end:
            total += _pending_advance_amount(details)
    return total


def get_used_amount(
    employee_id: int,
    start: date,
    end: date,
    exclude_transaction_id: Optional[int] = None,
) -> float:
    recorded = _sum_recorded_advances(employee_id, start, end)
    pending = _sum_pending_transactions(employee_id, start, end, exclude_transaction_id)
    return round(recorded + pending, 2)


def build_limit_status(
    employee,
    ref_date=None,
    exclude_transaction_id: Optional[int] = None,
) -> dict[str, Any]:
    ref = _parse_date(ref_date)
    mode = get_limit_mode(employee)
    period = get_limit_period(employee)
    start, end = get_period_window(period, ref)
    base = compute_base_salary(employee)
    cap = compute_cap(employee)
    used = get_used_amount(employee.id, start, end, exclude_transaction_id) if employee.id else 0.0

    if cap is None:
        remaining = 0.0
        configured = False
    else:
        remaining = max(0.0, round(cap - used, 2))
        configured = True

    return {
        'employee_id': employee.id,
        'mode': mode,
        'period': period,
        'period_label': PERIOD_LABELS.get(period, period),
        'date': ref.isoformat(),
        'period_start': start.isoformat(),
        'period_end_exclusive': end.isoformat(),
        'base_salary': round(base, 2),
        'advance_percentage': _to_float(employee.advancePercentage),
        'advance_fixed_limit': (
            _to_float(employee.advance_fixed_limit)
            if getattr(employee, 'advance_fixed_limit', None) is not None
            else None
        ),
        'cap': cap,
        'used': used,
        'remaining': remaining,
        'configured': configured,
        'allowed': configured and remaining > 0,
    }


def validate_advance_request(
    employee,
    amount,
    ref_date=None,
    exclude_transaction_id: Optional[int] = None,
) -> dict[str, Any]:
    """
    يتحقق من أن المبلغ ضمن حد السلفة.
    يرفع AdvanceLimitError عند الرفض، ويرجع status عند النجاح.
    """
    amount_value = _to_float(amount)
    if amount_value <= 0:
        raise AdvanceLimitError('قيمة السلفة يجب أن تكون أكبر من صفر')

    status = build_limit_status(employee, ref_date, exclude_transaction_id)

    if not status['configured'] or status['cap'] is None:
        raise AdvanceLimitError(
            'لا يوجد حد سلفة مُعدّ لهذا الموظف. يرجى ضبط نسبة السلفة أو القيمة الثابتة أولاً.',
            status,
        )

    cap = status['cap']
    used = status['used']
    remaining = status['remaining']
    period_label = status['period_label']

    if amount_value > remaining + 1e-9:
        raise AdvanceLimitError(
            (
                f'تجاوز حد السلفة لـ{period_label}. '
                f'السقف: {cap:.2f}، المستخدم: {used:.2f}، المتبقي: {remaining:.2f}، '
                f'المطلوب: {amount_value:.2f}.'
            ),
            status,
        )

    return status


def employee_limit_fields_payload(employee) -> dict[str, Any]:
    """حقول حد السلفة لإدراجها في ردود الموظف."""
    return {
        'advance_limit_mode': get_limit_mode(employee),
        'advance_fixed_limit': (
            _to_float(employee.advance_fixed_limit)
            if getattr(employee, 'advance_fixed_limit', None) is not None
            else None
        ),
        'advance_limit_period': get_limit_period(employee),
        'advancePercentage': _to_float(employee.advancePercentage),
    }


def normalize_limit_fields_from_data(data: dict) -> dict[str, Any]:
    """استخراج وتطبيع حقول الحد من جسم الطلب."""
    result: dict[str, Any] = {}

    if 'advance_limit_mode' in data and data['advance_limit_mode'] is not None:
        mode = str(data['advance_limit_mode']).strip().lower()
        if mode not in VALID_MODES:
            raise ValueError('نوع حد السلفة غير صالح. القيم المسموحة: percentage أو fixed')
        result['advance_limit_mode'] = mode

    if 'advance_limit_period' in data and data['advance_limit_period'] is not None:
        period = str(data['advance_limit_period']).strip().lower()
        if period not in VALID_PERIODS:
            raise ValueError('فترة حد السلفة غير صالحة. القيم المسموحة: daily أو weekly أو monthly')
        result['advance_limit_period'] = period

    if 'advance_fixed_limit' in data:
        raw = data['advance_fixed_limit']
        if raw is None or raw == '' or raw == 'null':
            result['advance_fixed_limit'] = None
        else:
            try:
                value = float(raw)
            except (TypeError, ValueError):
                raise ValueError('القيمة الثابتة للسلفة غير صحيحة')
            if value < 0:
                raise ValueError('القيمة الثابتة للسلفة لا يمكن أن تكون سالبة')
            result['advance_fixed_limit'] = value

    if 'advancePercentage' in data:
        raw = data['advancePercentage']
        if raw is None or raw == '' or raw == 'null':
            result['advancePercentage'] = None
        else:
            try:
                value = float(raw)
            except (TypeError, ValueError):
                raise ValueError('نسبة السلفة غير صحيحة')
            if value < 0 or value > 100:
                raise ValueError('نسبة السلفة يجب أن تكون بين 0 و 100')
            result['advancePercentage'] = value

    return result

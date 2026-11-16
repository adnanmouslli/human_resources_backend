# shift_exception.py — استثناءات يومية على وردية (تأخير دخول / خروج مبكر)

from datetime import datetime, date
from app import db


class ShiftException(db.Model):
    """
    استثناء يومي لوردية معيّنة:
    - check_in: السماح بالتأخير وتسجيل الدخول كبداية الوردية ضمن المدة (أو مفتوح)
    - check_out: السماح بالخروج المبكر وتسجيله كنهاية الوردية ضمن المدة (أو مفتوح)
    """
    __tablename__ = 'shift_exceptions'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    shift_id = db.Column(db.Integer, db.ForeignKey('shift.id'), nullable=False, index=True)
    exception_date = db.Column(db.Date, nullable=False, index=True)
    punch_type = db.Column(db.String(20), nullable=False)  # check_in | check_out
    reason = db.Column(db.String(500), nullable=False)
    # null مع is_open=True = مفتوح (أي بصمة تُحسب ضمن الاستثناء)
    duration_minutes = db.Column(db.Integer, nullable=True)
    is_open = db.Column(db.Boolean, nullable=False, default=False)
    note = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    shift = db.relationship('Shift', backref=db.backref('exceptions', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('shift_id', 'exception_date', 'punch_type', name='uq_shift_exception_day_type'),
    )

    def __repr__(self):
        return f"<ShiftException shift={self.shift_id} {self.exception_date} {self.punch_type}>"

    def to_dict(self):
        return {
            'id': self.id,
            'shift_id': self.shift_id,
            'shift_name': self.shift.name if self.shift else None,
            'exception_date': self.exception_date.strftime('%Y-%m-%d') if self.exception_date else None,
            'punch_type': self.punch_type,
            'reason': self.reason,
            'duration_minutes': self.duration_minutes,
            'is_open': bool(self.is_open),
            'note': self.note,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


def _as_date(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value[:10])
    return value


def get_shift_exception(shift_id, target_date, punch_type):
    """جلب استثناء وردية لتاريخ ونوع بصمة."""
    if not shift_id:
        return None
    target = _as_date(target_date)
    if not target:
        return None
    return ShiftException.query.filter_by(
        shift_id=shift_id,
        exception_date=target,
        punch_type=punch_type,
    ).first()


def resolve_check_in_grace_minutes(shift, target_date):
    """
    دقائق السماح بعد بداية الوردية قبل اعتبار التأخير.
    يرجع: (grace_minutes | None, is_open, exception|None)
    إذا is_open=True فـ grace_minutes=None (غير محدود).
    """
    base = int(getattr(shift, 'allowed_delay_minutes', 0) or 0)
    exc = get_shift_exception(shift.id, target_date, 'check_in')
    if not exc:
        return base, False, None
    if exc.is_open or exc.duration_minutes is None:
        return None, True, exc
    return base + int(exc.duration_minutes), False, exc


def resolve_check_out_grace_minutes(shift, target_date):
    """
    دقائق السماح قبل نهاية الوردية قبل اعتبار الخروج المبكر.
    يرجع: (grace_minutes | None, is_open, exception|None)
    """
    base = int(getattr(shift, 'allowed_exit_minutes', 0) or 0)
    exc = get_shift_exception(shift.id, target_date, 'check_out')
    if not exc:
        return base, False, None
    if exc.is_open or exc.duration_minutes is None:
        return None, True, exc
    return base + int(exc.duration_minutes), False, exc

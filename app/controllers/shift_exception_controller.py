from datetime import date, datetime
from app import db
from app.models import Shift
from app.models.shift_exception import ShiftException

VALID_PUNCH_TYPES = {'check_in', 'check_out'}


class ShiftExceptionController:
    @staticmethod
    def _parse_date(value):
        if value is None or value == '':
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            try:
                return date.fromisoformat(value[:10])
            except ValueError:
                return 'invalid'
        return 'invalid'

    @staticmethod
    def _validate_payload(data, partial=False):
        errors = []

        shift_id = data.get('shift_id')
        if not partial or 'shift_id' in data:
            if not shift_id:
                errors.append('shift_id مطلوب')
            elif not Shift.query.get(shift_id):
                errors.append('الوردية غير موجودة')

        punch_type = data.get('punch_type')
        if not partial or 'punch_type' in data:
            if punch_type not in VALID_PUNCH_TYPES:
                errors.append('punch_type يجب أن يكون check_in أو check_out')

        exception_date = ShiftExceptionController._parse_date(data.get('exception_date'))
        if not partial or 'exception_date' in data:
            if exception_date == 'invalid' or exception_date is None:
                errors.append('exception_date غير صالح (YYYY-MM-DD)')

        reason = (data.get('reason') or '').strip()
        if not partial or 'reason' in data:
            if not reason:
                errors.append('السبب مطلوب')

        is_open = bool(data.get('is_open', False))
        duration_minutes = data.get('duration_minutes')

        if is_open:
            duration_minutes = None
        else:
            if duration_minutes is None or duration_minutes == '':
                errors.append('المدة بالدقائق مطلوبة أو فعّل الوضع المفتوح')
            else:
                try:
                    duration_minutes = int(duration_minutes)
                    if duration_minutes < 1:
                        errors.append('المدة يجب أن تكون دقيقة واحدة على الأقل')
                except (TypeError, ValueError):
                    errors.append('المدة بالدقائق غير صالحة')

        if errors:
            return None, errors

        return {
            'shift_id': int(shift_id) if shift_id is not None else None,
            'exception_date': exception_date,
            'punch_type': punch_type,
            'reason': reason,
            'duration_minutes': duration_minutes,
            'is_open': is_open,
            'note': data.get('note'),
        }, None

    @staticmethod
    def list_exceptions(filters=None):
        filters = filters or {}
        query = ShiftException.query

        if filters.get('shift_id'):
            query = query.filter(ShiftException.shift_id == int(filters['shift_id']))
        if filters.get('punch_type') in VALID_PUNCH_TYPES:
            query = query.filter(ShiftException.punch_type == filters['punch_type'])

        date_from = ShiftExceptionController._parse_date(filters.get('date_from'))
        date_to = ShiftExceptionController._parse_date(filters.get('date_to'))
        exception_date = ShiftExceptionController._parse_date(filters.get('exception_date'))

        if exception_date and exception_date != 'invalid':
            query = query.filter(ShiftException.exception_date == exception_date)
        else:
            if date_from and date_from != 'invalid':
                query = query.filter(ShiftException.exception_date >= date_from)
            if date_to and date_to != 'invalid':
                query = query.filter(ShiftException.exception_date <= date_to)

        rows = query.order_by(
            ShiftException.exception_date.desc(),
            ShiftException.id.desc()
        ).all()
        return [r.to_dict() for r in rows], 200

    @staticmethod
    def get_by_id(exception_id):
        row = ShiftException.query.get(exception_id)
        if not row:
            return {'message': 'الاستثناء غير موجود'}, 404
        return row.to_dict(), 200

    @staticmethod
    def create(data, user_id=None):
        payload, errors = ShiftExceptionController._validate_payload(data)
        if errors:
            return {'message': '؛ '.join(errors)}, 400

        existing = ShiftException.query.filter_by(
            shift_id=payload['shift_id'],
            exception_date=payload['exception_date'],
            punch_type=payload['punch_type'],
        ).first()
        if existing:
            return {
                'message': 'يوجد استثناء بنفس الوردية والتاريخ ونوع البصمة. عدّله أو احذفه أولاً.'
            }, 409

        row = ShiftException(
            shift_id=payload['shift_id'],
            exception_date=payload['exception_date'],
            punch_type=payload['punch_type'],
            reason=payload['reason'],
            duration_minutes=payload['duration_minutes'],
            is_open=payload['is_open'],
            note=payload.get('note'),
            created_by=user_id,
        )
        db.session.add(row)
        db.session.commit()
        return {'message': 'تم إنشاء الاستثناء', 'exception': row.to_dict()}, 201

    @staticmethod
    def update(exception_id, data):
        row = ShiftException.query.get(exception_id)
        if not row:
            return {'message': 'الاستثناء غير موجود'}, 404

        merged = {
            'shift_id': data.get('shift_id', row.shift_id),
            'exception_date': data.get('exception_date', row.exception_date.strftime('%Y-%m-%d')),
            'punch_type': data.get('punch_type', row.punch_type),
            'reason': data.get('reason', row.reason),
            'is_open': data.get('is_open', row.is_open),
            'duration_minutes': data.get('duration_minutes', row.duration_minutes),
            'note': data.get('note', row.note),
        }
        payload, errors = ShiftExceptionController._validate_payload(merged)
        if errors:
            return {'message': '؛ '.join(errors)}, 400

        conflict = ShiftException.query.filter(
            ShiftException.shift_id == payload['shift_id'],
            ShiftException.exception_date == payload['exception_date'],
            ShiftException.punch_type == payload['punch_type'],
            ShiftException.id != exception_id,
        ).first()
        if conflict:
            return {
                'message': 'يوجد استثناء آخر بنفس الوردية والتاريخ ونوع البصمة'
            }, 409

        row.shift_id = payload['shift_id']
        row.exception_date = payload['exception_date']
        row.punch_type = payload['punch_type']
        row.reason = payload['reason']
        row.duration_minutes = payload['duration_minutes']
        row.is_open = payload['is_open']
        row.note = payload.get('note')
        db.session.commit()
        return {'message': 'تم تحديث الاستثناء', 'exception': row.to_dict()}, 200

    @staticmethod
    def delete(exception_id):
        row = ShiftException.query.get(exception_id)
        if not row:
            return {'message': 'الاستثناء غير موجود'}, 404
        db.session.delete(row)
        db.session.commit()
        return {'message': 'تم حذف الاستثناء'}, 200

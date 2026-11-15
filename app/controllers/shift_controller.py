from datetime import time, date
from flask import jsonify
from app import db
from app.models import Shift

VALID_DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
VALID_WEEK_START_DAYS = set(VALID_DAYS)


class ShiftController:
    @staticmethod
    def _validate_daily_schedule(daily_schedule, field_name='daily_schedule'):
        if not isinstance(daily_schedule, dict):
            return f'{field_name} must be a valid JSON object'

        for day, schedule in daily_schedule.items():
            if day not in VALID_DAYS:
                return f'Invalid day in {field_name}: {day}. Valid days are: {", ".join(VALID_DAYS)}'

            if not isinstance(schedule, dict):
                return f'{field_name}.{day} must be an object'

            if schedule.get('is_active', False):
                if not schedule.get('start_time') or not schedule.get('end_time'):
                    return f'start_time and end_time are required for active day: {day} ({field_name})'

                try:
                    time.fromisoformat(schedule['start_time'])
                    time.fromisoformat(schedule['end_time'])
                except ValueError:
                    return f'Invalid time format for day {day} in {field_name}. Use HH:MM:SS format'

        return None

    @staticmethod
    def _parse_anchor_date(value):
        if value is None or value == '':
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                return date.fromisoformat(value[:10])
            except ValueError:
                return 'invalid'
        return 'invalid'

    @staticmethod
    def _validate_rotation_fields(data, existing_shift=None):
        """
        يتحقق من حقول التناوب. عند التفعيل يجب توفر الجدول البديل وتاريخ المرجع.
        يرجع (error_message | None, normalized_fields_dict)
        """
        if existing_shift is not None:
            enabled = data.get(
                'weekly_rotation_enabled',
                getattr(existing_shift, 'weekly_rotation_enabled', False)
            )
            alternate = data.get(
                'alternate_daily_schedule',
                getattr(existing_shift, 'alternate_daily_schedule', None)
            )
            week_start = data.get(
                'rotation_week_start_day',
                getattr(existing_shift, 'rotation_week_start_day', 'saturday') or 'saturday'
            )
            anchor_raw = data.get(
                'rotation_anchor_date',
                getattr(existing_shift, 'rotation_anchor_date', None)
            )
        else:
            enabled = data.get('weekly_rotation_enabled', False)
            alternate = data.get('alternate_daily_schedule')
            week_start = data.get('rotation_week_start_day', 'saturday') or 'saturday'
            anchor_raw = data.get('rotation_anchor_date')

        enabled = bool(enabled)
        week_start = str(week_start).lower()

        if week_start not in VALID_WEEK_START_DAYS:
            return (
                f'Invalid rotation_week_start_day. Valid days are: {", ".join(VALID_DAYS)}',
                None
            )

        anchor = ShiftController._parse_anchor_date(anchor_raw)
        if anchor == 'invalid':
            return ('Invalid rotation_anchor_date. Use YYYY-MM-DD format', None)

        if enabled:
            if not alternate:
                return ('alternate_daily_schedule is required when weekly rotation is enabled', None)
            err = ShiftController._validate_daily_schedule(alternate, 'alternate_daily_schedule')
            if err:
                return (err, None)
            if not anchor:
                return ('rotation_anchor_date is required when weekly rotation is enabled', None)
        elif alternate:
            # حتى لو التناوب مغلق، نتحقق من الشكل إن وُجد جدول بديل محفوظ
            err = ShiftController._validate_daily_schedule(alternate, 'alternate_daily_schedule')
            if err:
                return (err, None)

        return None, {
            'weekly_rotation_enabled': enabled,
            'alternate_daily_schedule': alternate,
            'rotation_week_start_day': week_start,
            'rotation_anchor_date': anchor,
        }

    @staticmethod
    def _serialize_shift(shift):
        shift_data = {
            'id': shift.id,
            'name': shift.name,
            'daily_schedule': shift.daily_schedule,
            'allowed_delay_minutes': shift.allowed_delay_minutes,
            'allowed_exit_minutes': shift.allowed_exit_minutes,
            'note': shift.note,
            'absence_minutes': shift.absence_minutes,
            'extra_minutes': shift.extra_minutes,
            'weekly_rotation_enabled': bool(getattr(shift, 'weekly_rotation_enabled', False)),
            'alternate_daily_schedule': getattr(shift, 'alternate_daily_schedule', None),
            'rotation_week_start_day': getattr(shift, 'rotation_week_start_day', None) or 'saturday',
            'rotation_anchor_date': (
                shift.rotation_anchor_date.strftime('%Y-%m-%d')
                if getattr(shift, 'rotation_anchor_date', None) else None
            ),
        }

        if shift.start_time:
            shift_data['start_time'] = shift.start_time.strftime('%H:%M:%S')
        if shift.end_time:
            shift_data['end_time'] = shift.end_time.strftime('%H:%M:%S')

        return shift_data

    @staticmethod
    def create_shift(data):
        required_fields = ['name', 'daily_schedule']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return {'message': f'Missing fields: {", ".join(missing_fields)}'}, 400

        daily_schedule = data.get('daily_schedule')
        err = ShiftController._validate_daily_schedule(daily_schedule, 'daily_schedule')
        if err:
            return {'message': err}, 400

        rot_err, rot_fields = ShiftController._validate_rotation_fields(data)
        if rot_err:
            return {'message': rot_err}, 400

        shift = Shift(
            name=data['name'],
            daily_schedule=daily_schedule,
            start_time=data.get('start_time'),
            end_time=data.get('end_time'),
            allowed_delay_minutes=data.get('allowed_delay_minutes', 0),
            allowed_exit_minutes=data.get('allowed_exit_minutes', 0),
            note=data.get('note'),
            absence_minutes=data.get('absence_minutes', 0),
            extra_minutes=data.get('extra_minutes', 0),
            weekly_rotation_enabled=rot_fields['weekly_rotation_enabled'],
            alternate_daily_schedule=rot_fields['alternate_daily_schedule'],
            rotation_week_start_day=rot_fields['rotation_week_start_day'],
            rotation_anchor_date=rot_fields['rotation_anchor_date'],
        )

        db.session.add(shift)
        db.session.commit()

        return {
            'message': 'Shift created',
            'shift': {'id': shift.id, 'name': shift.name}
        }, 201

    @staticmethod
    def get_all_shifts():
        shifts = Shift.query.all()
        return [ShiftController._serialize_shift(shift) for shift in shifts], 200

    @staticmethod
    def get_shift_by_id(id):
        shift = Shift.query.get(id)

        if not shift:
            return {'message': 'Shift not found'}, 404

        return ShiftController._serialize_shift(shift), 200

    @staticmethod
    def update_shift(id, data):
        shift = Shift.query.get(id)

        if not shift:
            return {'message': 'Shift not found'}, 404

        if 'daily_schedule' in data:
            err = ShiftController._validate_daily_schedule(data['daily_schedule'], 'daily_schedule')
            if err:
                return {'message': err}, 400

        rotation_keys = {
            'weekly_rotation_enabled',
            'alternate_daily_schedule',
            'rotation_week_start_day',
            'rotation_anchor_date',
        }
        if rotation_keys.intersection(data.keys()) or getattr(shift, 'weekly_rotation_enabled', False):
            rot_err, rot_fields = ShiftController._validate_rotation_fields(data, existing_shift=shift)
            if rot_err:
                return {'message': rot_err}, 400
            data = {**data, **rot_fields}

        allowed_keys = {
            'name', 'daily_schedule', 'start_time', 'end_time',
            'allowed_delay_minutes', 'allowed_exit_minutes', 'note',
            'absence_minutes', 'extra_minutes',
            'weekly_rotation_enabled', 'alternate_daily_schedule',
            'rotation_week_start_day', 'rotation_anchor_date',
        }

        for key, value in data.items():
            if key in allowed_keys and hasattr(shift, key):
                setattr(shift, key, value)

        db.session.commit()

        return {
            'message': 'Shift updated',
            'shift': {'id': shift.id, 'name': shift.name}
        }, 200

    @staticmethod
    def delete_shift(id):
        shift = Shift.query.get(id)

        if not shift:
            return {'message': 'Shift not found'}, 404

        db.session.delete(shift)
        db.session.commit()

        return {'message': 'Shift deleted'}, 200

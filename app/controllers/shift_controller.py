from datetime import time
from flask import jsonify
from app import db
from app.models import Shift

class ShiftController:
    @staticmethod
    def create_shift(data):
        # Validate required fields
        required_fields = [
            'name', 'start_time', 'end_time', 'allowed_delay_minutes',
            'allowed_exit_minutes', 'absence_minutes', 'extra_minutes'
        ]
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return {'message': f'Missing fields: {", ".join(missing_fields)}'}, 400

        shift = Shift(
            name=data['name'],
            start_time=data['start_time'],
            end_time=data['end_time'],
            allowed_delay_minutes=data['allowed_delay_minutes'],
            allowed_exit_minutes=data['allowed_exit_minutes'],
            note=data.get('note'),
            absence_minutes=data['absence_minutes'],
            extra_minutes=data['extra_minutes']
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
        return [{
            key: (value.strftime('%H:%M:%S') if isinstance(value, time) else value)
            for key, value in shift.__dict__.items()
            if not key.startswith('_')
        } for shift in shifts], 200

    @staticmethod
    def get_shift_by_id(id):
        shift = Shift.query.get(id)

        if not shift:
            return {'message': 'Shift not found'}, 404

        return {
            'id': shift.id,
            'name': shift.name,
            'start_time': shift.start_time.strftime('%H:%M:%S') if shift.start_time else None,
            'end_time': shift.end_time.strftime('%H:%M:%S') if shift.end_time else None,
            'allowed_delay_minutes': shift.allowed_delay_minutes,
            'allowed_exit_minutes': shift.allowed_exit_minutes,
            'note': shift.note,
            'absence_minutes': shift.absence_minutes,
            'extra_minutes': shift.extra_minutes
        }, 200

    @staticmethod
    def update_shift(id, data):
        shift = Shift.query.get(id)

        if not shift:
            return {'message': 'Shift not found'}, 404

        for key, value in data.items():
            if hasattr(shift, key):
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
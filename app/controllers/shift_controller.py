from datetime import time
from flask import jsonify
from app import db
from app.models import Shift

class ShiftController:
    @staticmethod
    def create_shift(data):
        # Validate required fields
        required_fields = ['name', 'daily_schedule']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return {'message': f'Missing fields: {", ".join(missing_fields)}'}, 400

        # التحقق من صحة daily_schedule
        daily_schedule = data.get('daily_schedule')
        if not isinstance(daily_schedule, dict):
            return {'message': 'daily_schedule must be a valid JSON object'}, 400

        # التحقق من أيام الأسبوع
        valid_days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        for day, schedule in daily_schedule.items():
            if day not in valid_days:
                return {'message': f'Invalid day: {day}. Valid days are: {", ".join(valid_days)}'}, 400
            
            if schedule.get('is_active', False):
                if not schedule.get('start_time') or not schedule.get('end_time'):
                    return {'message': f'start_time and end_time are required for active day: {day}'}, 400
                
                # التحقق من صحة تنسيق الوقت
                try:
                    time.fromisoformat(schedule['start_time'])
                    time.fromisoformat(schedule['end_time'])
                except ValueError:
                    return {'message': f'Invalid time format for day {day}. Use HH:MM:SS format'}, 400

        shift = Shift(
            name=data['name'],
            daily_schedule=daily_schedule,
            start_time=data.get('start_time'),  # للتوافق مع النظام القديم
            end_time=data.get('end_time'),      # للتوافق مع النظام القديم
            allowed_delay_minutes=data.get('allowed_delay_minutes', 0),
            allowed_exit_minutes=data.get('allowed_exit_minutes', 0),
            note=data.get('note'),
            absence_minutes=data.get('absence_minutes', 0),
            extra_minutes=data.get('extra_minutes', 0)
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
        result = []
        
        for shift in shifts:
            shift_data = {
                'id': shift.id,
                'name': shift.name,
                'daily_schedule': shift.daily_schedule,
                'allowed_delay_minutes': shift.allowed_delay_minutes,
                'allowed_exit_minutes': shift.allowed_exit_minutes,
                'note': shift.note,
                'absence_minutes': shift.absence_minutes,
                'extra_minutes': shift.extra_minutes
            }
            
            # إضافة الحقول القديمة للتوافق
            if shift.start_time:
                shift_data['start_time'] = shift.start_time.strftime('%H:%M:%S')
            if shift.end_time:
                shift_data['end_time'] = shift.end_time.strftime('%H:%M:%S')
            
            result.append(shift_data)
        
        return result, 200

    @staticmethod
    def get_shift_by_id(id):
        shift = Shift.query.get(id)

        if not shift:
            return {'message': 'Shift not found'}, 404

        result = {
            'id': shift.id,
            'name': shift.name,
            'daily_schedule': shift.daily_schedule,
            'allowed_delay_minutes': shift.allowed_delay_minutes,
            'allowed_exit_minutes': shift.allowed_exit_minutes,
            'note': shift.note,
            'absence_minutes': shift.absence_minutes,
            'extra_minutes': shift.extra_minutes
        }
        
        # إضافة الحقول القديمة للتوافق
        if shift.start_time:
            result['start_time'] = shift.start_time.strftime('%H:%M:%S')
        if shift.end_time:
            result['end_time'] = shift.end_time.strftime('%H:%M:%S')

        return result, 200

    @staticmethod
    def update_shift(id, data):
        shift = Shift.query.get(id)

        if not shift:
            return {'message': 'Shift not found'}, 404

        # التحقق من daily_schedule إذا تم تمريره
        if 'daily_schedule' in data:
            daily_schedule = data['daily_schedule']
            if not isinstance(daily_schedule, dict):
                return {'message': 'daily_schedule must be a valid JSON object'}, 400

            # التحقق من أيام الأسبوع
            valid_days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            for day, schedule in daily_schedule.items():
                if day not in valid_days:
                    return {'message': f'Invalid day: {day}. Valid days are: {", ".join(valid_days)}'}, 400
                
                if schedule.get('is_active', False):
                    if not schedule.get('start_time') or not schedule.get('end_time'):
                        return {'message': f'start_time and end_time are required for active day: {day}'}, 400
                    
                    # التحقق من صحة تنسيق الوقت
                    try:
                        time.fromisoformat(schedule['start_time'])
                        time.fromisoformat(schedule['end_time'])
                    except ValueError:
                        return {'message': f'Invalid time format for day {day}. Use HH:MM:SS format'}, 400

        # تحديث البيانات
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
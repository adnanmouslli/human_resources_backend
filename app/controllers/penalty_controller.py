from app import db
from app.models import Penalty, Employee

class PenaltyController:
    @staticmethod
    def create_penalty(data):
        # التحقق من الحقول المطلوبة
        required_fields = ['employee_id', 'amount', 'document_number']
        missing_fields = [field for field in required_fields if field not in data or not data[field]]
        if missing_fields:
            return {'message': f'Missing fields: {", ".join(missing_fields)}'}, 400

        # التحقق من وجود الموظف
        employee = Employee.query.get(data['employee_id'])
        if not employee:
            return {'message': 'Employee not found'}, 404

        try:
            penalty = Penalty(
                employee_id=data['employee_id'],
                amount=data['amount'],
                document_number=data['document_number'],
                notes=data.get('notes')  # ملاحظات اختيارية
            )
            db.session.add(penalty)
            db.session.commit()
            return {
                'message': 'Penalty created',
                'penalty': {
                    'id': penalty.id,
                    'employee_id': penalty.employee_id,
                    'amount': str(penalty.amount),
                    'document_number': penalty.document_number,
                    'notes': penalty.notes,
                    'date': str(penalty.date)
                }
            }, 201
        except Exception as e:
            return {'message': 'Error creating penalty', 'error': str(e)}, 500

    @staticmethod
    def get_all_penalties():
        try:
            penalties = Penalty.query.join(Employee).all()
            return [
                {
                    'id': penalty.id,
                    'employee': {
                        'id': penalty.employee.id,
                        'name': penalty.employee.full_name,
                    },
                    'amount': str(penalty.amount),
                    'document_number': penalty.document_number,
                    'notes': penalty.notes,
                    'date': str(penalty.date)
                } for penalty in penalties
            ], 200
        except Exception as e:
            return {'message': 'Error fetching penalties', 'error': str(e)}, 500

    @staticmethod
    def get_penalty_by_id(id):
        penalty = Penalty.query.get(id)
        if not penalty:
            return {'message': 'Penalty not found'}, 404
        return {
            'id': penalty.id,
            'employee_id': penalty.employee_id,
            'amount': str(penalty.amount),
            'document_number': penalty.document_number,
            'notes': penalty.notes,
            'date': str(penalty.date)
        }, 200

    @staticmethod
    def update_penalty(id, data):
        penalty = Penalty.query.get(id)
        if not penalty:
            return {'message': 'Penalty not found'}, 404

        try:
            if 'amount' in data:
                penalty.amount = data['amount']
            if 'document_number' in data:
                penalty.document_number = data['document_number']
            if 'notes' in data:
                penalty.notes = data['notes']

            db.session.commit()
            return {
                'message': 'Penalty updated',
                'penalty': {
                    'id': penalty.id,
                    'employee_id': penalty.employee_id,
                    'amount': str(penalty.amount),
                    'document_number': penalty.document_number,
                    'notes': penalty.notes,
                    'date': str(penalty.date)
                }
            }, 200
        except Exception as e:
            return {'message': 'Error updating penalty', 'error': str(e)}, 500

    @staticmethod
    def delete_penalty(id):
        penalty = Penalty.query.get(id)
        if not penalty:
            return {'message': 'Penalty not found'}, 404

        try:
            db.session.delete(penalty)
            db.session.commit()
            return {'message': 'Penalty deleted'}, 200
        except Exception as e:
            return {'message': 'Error deleting penalty', 'error': str(e)}, 500

    @staticmethod
    def get_penalties_by_employee_id(emp_id):
        employee = Employee.query.get(emp_id)
        if not employee:
            return {'message': 'Employee not found'}, 404

        try:
            penalties = Penalty.query.filter_by(employee_id=emp_id).all()
            return [
                {
                    'id': penalty.id,
                    'employee': {
                        'id': employee.id,
                        'name': employee.full_name,
                    },
                    'amount': str(penalty.amount),
                    'document_number': penalty.document_number,
                    'notes': penalty.notes,
                    'date': str(penalty.date)
                } for penalty in penalties
            ], 200
        except Exception as e:
            return {'message': 'Error fetching penalties by employee ID', 'error': str(e)}, 500
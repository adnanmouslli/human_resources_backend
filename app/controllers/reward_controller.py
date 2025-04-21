from app import db
from app.models import Reward, Employee

class RewardController:
    @staticmethod
    def create_reward(data):
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
            reward = Reward(
                employee_id=data['employee_id'],
                amount=data['amount'],
                document_number=data['document_number'],
                notes=data.get('notes')  # ملاحظات اختيارية
            )
            db.session.add(reward)
            db.session.commit()
            return {
                'message': 'Reward created',
                'reward': {
                    'id': reward.id,
                    'employee_id': reward.employee_id,
                    'amount': str(reward.amount),
                    'document_number': reward.document_number,
                    'notes': reward.notes,
                    'date': str(reward.date)
                }
            }, 201
        except Exception as e:
            return {'message': 'Error creating reward', 'error': str(e)}, 500

    @staticmethod
    def get_all_rewards():
        try:
            rewards = Reward.query.join(Employee).all()
            return [
                {
                    'id': reward.id,
                    'employee': {
                        'id': reward.employee.id,
                        'name': reward.employee.full_name,
                    },
                    'amount': str(reward.amount),
                    'document_number': reward.document_number,
                    'notes': reward.notes,
                    'date': str(reward.date)
                } for reward in rewards
            ], 200
        except Exception as e:
            return {'message': 'Error fetching rewards', 'error': str(e)}, 500

    @staticmethod
    def get_reward_by_id(id):
        reward = Reward.query.get(id)
        if not reward:
            return {'message': 'Reward not found'}, 404
        return {
            'id': reward.id,
            'employee_id': reward.employee_id,
            'amount': str(reward.amount),
            'document_number': reward.document_number,
            'notes': reward.notes,
            'date': str(reward.date)
        }, 200

    @staticmethod
    def update_reward(id, data):
        reward = Reward.query.get(id)
        if not reward:
            return {'message': 'Reward not found'}, 404

        try:
            if 'amount' in data:
                reward.amount = data['amount']
            if 'document_number' in data:
                reward.document_number = data['document_number']
            if 'notes' in data:
                reward.notes = data['notes']

            db.session.commit()
            return {
                'message': 'Reward updated',
                'reward': {
                    'id': reward.id,
                    'employee_id': reward.employee_id,
                    'amount': str(reward.amount),
                    'document_number': reward.document_number,
                    'notes': reward.notes,
                    'date': str(reward.date)
                }
            }, 200
        except Exception as e:
            return {'message': 'Error updating reward', 'error': str(e)}, 500

    @staticmethod
    def delete_reward(id):
        reward = Reward.query.get(id)
        if not reward:
            return {'message': 'Reward not found'}, 404

        try:
            db.session.delete(reward)
            db.session.commit()
            return {'message': 'Reward deleted'}, 200
        except Exception as e:
            return {'message': 'Error deleting reward', 'error': str(e)}, 500

    @staticmethod
    def get_rewards_by_employee_id(emp_id):
        employee = Employee.query.get(emp_id)
        if not employee:
            return {'message': 'Employee not found'}, 404

        try:
            rewards = Reward.query.filter_by(employee_id=emp_id).all()
            return [
                {
                    'id': reward.id,
                    'employee': {
                        'id': employee.id,
                        'name': employee.full_name,
                    },
                    'amount': str(reward.amount),
                    'document_number': reward.document_number,
                    'notes': reward.notes,
                    'date': str(reward.date)
                } for reward in rewards
            ], 200
        except Exception as e:
            return {'message': 'Error fetching rewards by employee ID', 'error': str(e)}, 500
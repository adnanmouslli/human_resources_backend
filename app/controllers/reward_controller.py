# app/controllers/reward_controller.py

from flask import request, jsonify
from app import db
from app.models.employee import Employee
from app.models.reward import Reward

# Create Reward
def create_reward():
    data = request.get_json()

    required_fields = ['employee_id', 'amount', 'document_number']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return jsonify({'message': f'Missing fields: {", ".join(missing_fields)}'}), 400

    employee = Employee.query.get(data['employee_id'])
    if not employee:
        return jsonify({'message': 'Employee not found'}), 404

    reward = Reward(
        employee_id=data['employee_id'],
        amount=data['amount'],
        document_number=data['document_number'],
        notes=data.get('notes')
    )
    db.session.add(reward)
    db.session.commit()

    return jsonify({
        'id': reward.id,
        'date': str(reward.date),
        'amount': str(reward.amount),
        'document_number': reward.document_number,
        'notes': reward.notes,
        'employee': {
            'id': employee.id,
            'full_name': employee.full_name
        }
    }), 201

# Get All Rewards with Employee Details
def get_all_rewards():
    rewards = Reward.query.join(Employee).all()
    return jsonify([{
        'id': reward.id,
        'employee': {
            'id': reward.employee.id,
            'name': reward.employee.full_name,
        },
        'amount': str(reward.amount),
        'document_number': reward.document_number,
        'notes': reward.notes,
        'date': str(reward.date)
    } for reward in rewards]), 200

# Get Reward by ID
def get_reward_by_id(id):
    reward = Reward.query.get(id)
    if not reward:
        return jsonify({'message': 'Reward not found'}), 404

    return jsonify({
        'id': reward.id,
        'employee_id': reward.employee_id,
        'amount': str(reward.amount),
        'document_number': reward.document_number,
        'notes': reward.notes,
        'date': str(reward.date)
    }), 200

# Update Reward
def update_reward(id):
    reward = Reward.query.get(id)
    if not reward:
        return jsonify({'message': 'Reward not found'}), 404

    data = request.get_json()
    for key, value in data.items():
        if hasattr(reward, key) and key != 'employee':
            setattr(reward, key, value)

    db.session.commit()

    employee = Employee.query.get(reward.employee_id)
    if not employee:
        return jsonify({'message': 'Employee not found'}), 404

    return jsonify({
        'id': reward.id,
        'date': str(reward.date),
        'amount': str(reward.amount),
        'document_number': reward.document_number,
        'notes': reward.notes,
        'employee': {
            'id': employee.id,
            'name': employee.full_name
        }
    }), 200

# Delete Reward
def delete_reward(id):
    reward = Reward.query.get(id)
    if not reward:
        return jsonify({'message': 'Reward not found'}), 404

    db.session.delete(reward)
    db.session.commit()

    return jsonify({'message': 'Reward deleted'}), 200

# Get Rewards by Employee ID
def get_rewards_by_employee_id(emp_id):
    employee = Employee.query.get(emp_id)
    if not employee:
        return jsonify({'message': 'Employee not found'}), 404

    rewards = Reward.query.filter_by(employee_id=emp_id).all()
    return jsonify([{
        'id': reward.id,
        'employee': {
            'id': employee.id,
            'name': employee.full_name,
        },
        'amount': str(reward.amount),
        'document_number': reward.document_number,
        'notes': reward.notes,
        'date': str(reward.date)
    } for reward in rewards]), 200
# app/controllers/penalty_controller.py

from flask import request, jsonify
from app import db
from app.models.employee import Employee
from app.models.penalty import Penalty

# Create Penalty
def create_penalty():
    data = request.get_json()

    required_fields = ['employee_id', 'amount', 'document_number']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return jsonify({'message': f'Missing fields: {", ".join(missing_fields)}'}), 400

    employee = Employee.query.get(data['employee_id'])
    if not employee:
        return jsonify({'message': 'Employee not found'}), 404

    penalty = Penalty(
        employee_id=data['employee_id'],
        amount=data['amount'],
        document_number=data['document_number'],
        notes=data.get('notes')
    )
    db.session.add(penalty)
    db.session.commit()

    return jsonify({
        'id': penalty.id,
        'date': str(penalty.date),
        'amount': str(penalty.amount),
        'document_number': penalty.document_number,
        'notes': penalty.notes,
        'employee': {
            'id': employee.id,
            'full_name': employee.full_name
        }
    }), 201

# Get All Penalties with Employee Details
def get_all_penalties():
    penalties = Penalty.query.join(Employee).all()
    return jsonify([{
        'id': penalty.id,
        'employee': {
            'id': penalty.employee.id,
            'name': penalty.employee.full_name,
        },
        'amount': str(penalty.amount),
        'document_number': penalty.document_number,
        'notes': penalty.notes,
        'date': str(penalty.date)
    } for penalty in penalties]), 200

# Get Penalty by ID
def get_penalty_by_id(id):
    penalty = Penalty.query.get(id)
    if not penalty:
        return jsonify({'message': 'Penalty not found'}), 404

    return jsonify({
        'id': penalty.id,
        'employee_id': penalty.employee_id,
        'amount': str(penalty.amount),
        'document_number': penalty.document_number,
        'notes': penalty.notes,
        'date': str(penalty.date)
    }), 200

# Update Penalty
def update_penalty(id):
    penalty = Penalty.query.get(id)
    if not penalty:
        return jsonify({'message': 'Penalty not found'}), 404

    data = request.get_json()
    for key, value in data.items():
        if hasattr(penalty, key) and key != 'employee':
            setattr(penalty, key, value)

    db.session.commit()

    employee = Employee.query.get(penalty.employee_id)
    if not employee:
        return jsonify({'message': 'Employee not found'}), 404

    return jsonify({
        'id': penalty.id,
        'date': str(penalty.date),
        'amount': str(penalty.amount),
        'document_number': penalty.document_number,
        'notes': penalty.notes,
        'employee': {
            'id': employee.id,
            'name': employee.full_name
        }
    }), 200

# Delete Penalty
def delete_penalty(id):
    penalty = Penalty.query.get(id)
    if not penalty:
        return jsonify({'message': 'Penalty not found'}), 404

    db.session.delete(penalty)
    db.session.commit()

    return jsonify({'message': 'Penalty deleted'}), 200

# Get Penalties by Employee ID
def get_penalties_by_employee_id(emp_id):
    employee = Employee.query.get(emp_id)
    if not employee:
        return jsonify({'message': 'Employee not found'}), 404

    penalties = Penalty.query.filter_by(employee_id=emp_id).all()
    return jsonify([{
        'id': penalty.id,
        'employee': {
            'id': employee.id,
            'name': employee.full_name,
        },
        'amount': str(penalty.amount),
        'document_number': penalty.document_number,
        'notes': penalty.notes,
        'date': str(penalty.date)
    } for penalty in penalties]), 200
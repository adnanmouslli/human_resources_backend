# app/routes/penalty_routes.py

from flask import Blueprint
from app.controllers.penalty_controller import (
    create_penalty,
    get_all_penalties,
    get_penalty_by_id,
    update_penalty,
    delete_penalty,
    get_penalties_by_employee_id
)
from app.utils import token_required

penalties_bp = Blueprint('penalties', __name__)

# Create Penalty
@penalties_bp.route('/api/penalties', methods=['POST'])
@token_required
def create():
    return create_penalty()

# Get All Penalties with Employee Details
@penalties_bp.route('/api/penalties', methods=['GET'])
@token_required
def get_all():
    return get_all_penalties()

# Get Penalty by ID
@penalties_bp.route('/api/penalties/<int:id>', methods=['GET'])
@token_required
def get_by_id(id):
    return get_penalty_by_id(id)

# Update Penalty
@penalties_bp.route('/api/penalties/<int:id>', methods=['PUT'])
@token_required
def update(id):
    return update_penalty(id)

# Delete Penalty
@penalties_bp.route('/api/penalties/<int:id>', methods=['DELETE'])
@token_required
def delete(id):
    return delete_penalty(id)

# Get Penalties by Employee ID
@penalties_bp.route('/api/penalties/employee/<int:emp_id>', methods=['GET'])
@token_required
def get_by_employee_id(emp_id):
    return get_penalties_by_employee_id(emp_id)
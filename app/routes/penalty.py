from flask import Blueprint, request, jsonify
from app.controllers.penalty_controller import PenaltyController
from app.utils import token_required

penalties_bp = Blueprint('penalties', __name__)

@penalties_bp.route('/api/penalties', methods=['POST'])
@token_required
def create_penalty(user_id):
    data = request.get_json()
    response, status_code = PenaltyController.create_penalty(data)
    return jsonify(response), status_code

@penalties_bp.route('/api/penalties', methods=['GET'])
@token_required
def get_all_penalties(user_id):
    response, status_code = PenaltyController.get_all_penalties()
    return jsonify(response), status_code

@penalties_bp.route('/api/penalties/<int:id>', methods=['GET'])
@token_required
def get_penalty(user_id, id):
    response, status_code = PenaltyController.get_penalty_by_id(id)
    return jsonify(response), status_code

@penalties_bp.route('/api/penalties/<int:id>', methods=['PUT'])
@token_required
def update_penalty(user_id, id):
    data = request.get_json()
    response, status_code = PenaltyController.update_penalty(id, data)
    return jsonify(response), status_code

@penalties_bp.route('/api/penalties/<int:id>', methods=['DELETE'])
@token_required
def delete_penalty(user_id, id):
    response, status_code = PenaltyController.delete_penalty(id)
    return jsonify(response), status_code

@penalties_bp.route('/api/penalties/employee/<int:emp_id>', methods=['GET'])
@token_required
def get_penalties_by_employee(user_id, emp_id):
    response, status_code = PenaltyController.get_penalties_by_employee_id(emp_id)
    return jsonify(response), status_code
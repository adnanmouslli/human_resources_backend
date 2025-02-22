from flask import Blueprint, request, jsonify
from app.controllers.shift_controller import ShiftController
from app.utils import token_required

shift_bp = Blueprint('shift', __name__)

@shift_bp.route('/api/shifts', methods=['POST'])
@token_required
def create_shift(user_id):
    data = request.get_json()
    response, status_code = ShiftController.create_shift(data)
    return jsonify(response), status_code

@shift_bp.route('/api/shifts', methods=['GET'])
@token_required
def get_all_shifts(user_id):
    response, status_code = ShiftController.get_all_shifts()
    return jsonify(response), status_code

@shift_bp.route('/api/shifts/<int:id>', methods=['GET'])
@token_required
def get_shift(user_id, id):
    response, status_code = ShiftController.get_shift_by_id(id)
    return jsonify(response), status_code

@shift_bp.route('/api/shifts/<int:id>', methods=['PUT'])
@token_required
def update_shift(user_id, id):
    data = request.get_json()
    response, status_code = ShiftController.update_shift(id, data)
    return jsonify(response), status_code

@shift_bp.route('/api/shifts/<int:id>', methods=['DELETE'])
@token_required
def delete_shift(user_id, id):
    response, status_code = ShiftController.delete_shift(id)
    return jsonify(response), status_code
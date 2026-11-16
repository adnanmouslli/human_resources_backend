from flask import Blueprint, request, jsonify
from app.controllers.shift_controller import ShiftController
from app.controllers.shift_exception_controller import ShiftExceptionController
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


# ——— استثناءات الوردية ———

@shift_bp.route('/api/shifts/exceptions', methods=['GET'])
@token_required
def list_shift_exceptions(user):
    filters = {
        'shift_id': request.args.get('shift_id'),
        'punch_type': request.args.get('punch_type'),
        'exception_date': request.args.get('exception_date'),
        'date_from': request.args.get('date_from'),
        'date_to': request.args.get('date_to'),
    }
    response, status_code = ShiftExceptionController.list_exceptions(filters)
    return jsonify(response), status_code


@shift_bp.route('/api/shifts/exceptions/<int:exception_id>', methods=['GET'])
@token_required
def get_shift_exception(user, exception_id):
    response, status_code = ShiftExceptionController.get_by_id(exception_id)
    return jsonify(response), status_code


@shift_bp.route('/api/shifts/exceptions', methods=['POST'])
@token_required
def create_shift_exception(user):
    data = request.get_json() or {}
    response, status_code = ShiftExceptionController.create(data, user_id=getattr(user, 'id', None))
    return jsonify(response), status_code


@shift_bp.route('/api/shifts/exceptions/<int:exception_id>', methods=['PUT'])
@token_required
def update_shift_exception(user, exception_id):
    data = request.get_json() or {}
    response, status_code = ShiftExceptionController.update(exception_id, data)
    return jsonify(response), status_code


@shift_bp.route('/api/shifts/exceptions/<int:exception_id>', methods=['DELETE'])
@token_required
def delete_shift_exception(user, exception_id):
    response, status_code = ShiftExceptionController.delete(exception_id)
    return jsonify(response), status_code
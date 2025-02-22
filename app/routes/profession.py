
from flask import Blueprint, request, jsonify
from app.controllers.profession_controller import ProfessionController
from app.utils import token_required

profession_bp = Blueprint('profession', __name__)

@profession_bp.route('/api/professions', methods=['POST'])
@token_required
def create_profession(user_id):
    data = request.get_json()
    response, status_code = ProfessionController.create_profession(data)
    return jsonify(response), status_code

@profession_bp.route('/api/professions', methods=['GET'])
@token_required
def get_all_professions(user_id):
    response, status_code = ProfessionController.get_all_professions()
    return jsonify(response), status_code

@profession_bp.route('/api/professions/<int:id>', methods=['GET'])
@token_required
def get_profession(user_id, id):
    response, status_code = ProfessionController.get_profession_by_id(id)
    return jsonify(response), status_code

@profession_bp.route('/api/professions/<int:id>', methods=['PUT'])
@token_required
def update_profession(user_id, id):
    data = request.get_json()
    response, status_code = ProfessionController.update_profession(id, data)
    return jsonify(response), status_code

@profession_bp.route('/api/professions/<int:id>', methods=['DELETE'])
@token_required
def delete_profession(user_id, id):
    response, status_code = ProfessionController.delete_profession(id)
    return jsonify(response), status_code
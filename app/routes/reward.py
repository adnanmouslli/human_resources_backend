from flask import Blueprint, request, jsonify
from app.controllers.reward_controller import RewardController
from app.utils import token_required

rewards_bp = Blueprint('rewards', __name__)

@rewards_bp.route('/api/rewards', methods=['POST'])
@token_required
def create_reward(user_id):
    data = request.get_json()
    response, status_code = RewardController.create_reward(data)
    return jsonify(response), status_code

@rewards_bp.route('/api/rewards', methods=['GET'])
@token_required
def get_all_rewards(user_id):
    response, status_code = RewardController.get_all_rewards()
    return jsonify(response), status_code

@rewards_bp.route('/api/rewards/<int:id>', methods=['GET'])
@token_required
def get_reward(user_id, id):
    response, status_code = RewardController.get_reward_by_id(id)
    return jsonify(response), status_code

@rewards_bp.route('/api/rewards/<int:id>', methods=['PUT'])
@token_required
def update_reward(user_id, id):
    data = request.get_json()
    response, status_code = RewardController.update_reward(id, data)
    return jsonify(response), status_code

@rewards_bp.route('/api/rewards/<int:id>', methods=['DELETE'])
@token_required
def delete_reward(user_id, id):
    response, status_code = RewardController.delete_reward(id)
    return jsonify(response), status_code

@rewards_bp.route('/api/rewards/employee/<int:emp_id>', methods=['GET'])
@token_required
def get_rewards_by_employee(user_id, emp_id):
    response, status_code = RewardController.get_rewards_by_employee_id(emp_id)
    return jsonify(response), status_code
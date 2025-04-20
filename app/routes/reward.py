# app/routes/reward_routes.py

from flask import Blueprint
from app.controllers.reward_controller import (
    create_reward,
    get_all_rewards,
    get_reward_by_id,
    update_reward,
    delete_reward,
    get_rewards_by_employee_id
)
from app.utils import token_required

rewards_bp = Blueprint('rewards', __name__)

# Create Reward
@rewards_bp.route('/api/rewards', methods=['POST'])
@token_required
def create():
    return create_reward()

# Get All Rewards with Employee Details
@rewards_bp.route('/api/rewards', methods=['GET'])
@token_required
def get_all():
    return get_all_rewards()

# Get Reward by ID
@rewards_bp.route('/api/rewards/<int:id>', methods=['GET'])
@token_required
def get_by_id(id):
    return get_reward_by_id(id)

# Update Reward
@rewards_bp.route('/api/rewards/<int:id>', methods=['PUT'])
@token_required
def update(id):
    return update_reward(id)

# Delete Reward
@rewards_bp.route('/api/rewards/<int:id>', methods=['DELETE'])
@token_required
def delete(id):
    return delete_reward(id)

# Get Rewards by Employee ID
@rewards_bp.route('/api/rewards/employee/<int:emp_id>', methods=['GET'])
@token_required
def get_by_employee_id(emp_id):
    return get_rewards_by_employee_id(emp_id)
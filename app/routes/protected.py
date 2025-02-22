from flask import Blueprint, request, jsonify
from app.utils import verify_token
from app.models import User

protected_routes = Blueprint('protected', __name__)

@protected_routes.route('/protected', methods=['GET'])
def protected():
    token = request.headers.get('x-access-token')

    if not token:
        return jsonify({'message': 'Token is missing!'}), 403

    user_id = verify_token(token)
    if not user_id:
        return jsonify({'message': 'Token is invalid!'}), 403

    user = User.query.get(user_id)
    return jsonify({'message': f'Hello, {user.username}!'})

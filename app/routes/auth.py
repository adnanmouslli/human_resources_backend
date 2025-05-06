from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import User
from app.utils import generate_token

auth_routes = Blueprint('auth', __name__)

@auth_routes.route('/api/auth/register', methods=['POST'])
def register():
    from app import db

    data = request.get_json()
    hashed_password = generate_password_hash(data['password'])
    new_user = User(username=data['username'], password=hashed_password)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'message': 'User created successfully'}), 201

@auth_routes.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(username=data['username']).first()

    if not user or not check_password_hash(user.password, data['password']):
        return jsonify({'message': 'Invalid credentials'}), 401

    token = generate_token(user.id)
    return jsonify({'token': token})

@auth_routes.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        'status' : "success" 
    })

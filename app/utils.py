import jwt
import datetime
from flask import current_app

def generate_token(user_id):
    return jwt.encode({
        'user_id': user_id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=12)
    }, current_app.config['SECRET_KEY'], algorithm='HS256')

def verify_token(token):
    try:
        decoded = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
        return decoded['user_id']
    except:
        return None


from functools import wraps
from flask import request, jsonify
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # Check if token is present in the request headers
        if 'Authorization' in request.headers:
            try:
                token = request.headers['Authorization'].split(" ")[1]
            except IndexError:
                return jsonify({'message': 'Token format is invalid'}), 401

        if not token:
            return jsonify({'message': 'Token is missing'}), 401

        # Verify the token
        user_id = verify_token(token)
        if not user_id:
            return jsonify({'message': 'Invalid or expired token'}), 401

        # Pass user_id to the route
        return f(user_id, *args, **kwargs)

    return decorated

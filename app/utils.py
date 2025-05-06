import jwt
import datetime
from flask import current_app

def generate_token(user):
  
    payload = {
        'user_id': user.id,
        'username': user.username,
        'user_type': user.user_type,
        'employee_id': user.employee_id,
        'department_id': user.department_id,
        'branch_id': user.branch_id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=12)
    }
    return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')

def verify_token(token):
  
    try:
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
        return payload
    except:
        return None


from functools import wraps
from flask import request, jsonify
from app.models.user import User

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # التحقق من وجود الرمز في رأس الطلب
        if 'Authorization' in request.headers:
            try:
                token = request.headers['Authorization'].split(" ")[1]
            except IndexError:
                return jsonify({'message': 'صيغة الرمز غير صالحة'}), 401

        if not token:
            return jsonify({'message': 'الرمز مفقود'}), 401

        # التحقق من صحة الرمز
        payload = verify_token(token)
        if not payload:
            return jsonify({'message': 'رمز غير صالح أو منتهي الصلاحية'}), 401

        # الحصول على المستخدم من قاعدة البيانات
        user = User.query.get(payload['user_id'])
        if not user:
            return jsonify({'message': 'المستخدم غير موجود'}), 404
        
        if not user.is_active:
            return jsonify({'message': 'الحساب غير نشط'}), 403

        # تمرير كائن المستخدم إلى المسار
        return f(user, *args, **kwargs)

    return decorated

def permission_required(action, resource):
    def decorator(f):
        @wraps(f)
        def decorated_function(user, *args, **kwargs):
            # التحقق من صلاحيات المستخدم
            if not user.has_permission(action, resource):
                return jsonify({'message': 'ليس لديك صلاحية للوصول إلى هذا المورد'}), 403
            
            return f(user, *args, **kwargs)
        return decorated_function
    return decorator
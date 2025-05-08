from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import User
from app.utils import generate_token
from app import db

auth_routes = Blueprint('auth', __name__)

@auth_routes.route('/api/auth/register', methods=['POST'])
def register():

    data = request.get_json()
    hashed_password = generate_password_hash(data['password'])
    new_user = User(username=data['username'], password=hashed_password)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'message': 'User created successfully'}), 201

@auth_routes.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'message': 'يرجى إدخال اسم المستخدم وكلمة المرور'}), 400
    
    user = User.query.filter_by(username=data.get('username')).first()
    
    if not user or not user.check_password(data.get('password')):
        return jsonify({'message': 'اسم المستخدم أو كلمة المرور غير صحيحة'}), 401
    
    if not user.is_active:
        return jsonify({'message': 'الحساب غير نشط'}), 403
    
    # توليد الرمز
    token = generate_token(user)
    
    # معلومات المستخدم
    user_info = {
        'id': user.id,
        'username': user.username,
        'user_type': user.user_type,
        'employee': {
            'id': user.employee.id,
            'full_name': user.employee.full_name
        } if user.employee else None,
        'department': {
            'id': user.department.id,
            'name': user.department.name
        } if user.department else None,
        'branch': {
            'id': user.branch.id,
            'name': user.branch.name
        } if user.branch else None,
    }
    
    return jsonify({
        'token': token,
        'user': user_info
    }), 200


def create_super_admin():
    """
    إنشاء حساب super admin إذا لم يكن موجوداً
    """
    # التحقق من وجود super admin
    admin = User.query.filter_by(user_type='super_admin').first()
    if not admin:
        # إنشاء مستخدم super admin جديد
        admin = User(
            username='admin1',
            user_type='super_admin',
            is_active=True
        )
        admin.set_password('admin1')  # كلمة مرور افتراضية (يجب تغييرها)
        
        db.session.add(admin)
        db.session.commit()
        print("تم إنشاء حساب super admin بنجاح")
    else:
        print("حساب super admin موجود بالفعل")

@auth_routes.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        'status' : "success" 
    })

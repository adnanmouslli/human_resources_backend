from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import User
from app.utils import generate_token
from app import db

auth_routes = Blueprint('auth', __name__)

@auth_routes.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()

    # تحقق من الحقول المطلوبة
    required_fields = ['username', 'password', 'user_type', 'is_active']
    for field in required_fields:
        if field not in data:
            return jsonify({'message': f'الرجاء إدخال الحقل: {field}'}), 400

    # تحقق من عدم تكرار اسم المستخدم
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'message': 'اسم المستخدم مستخدم بالفعل'}), 409

    # إنشاء المستخدم
    hashed_password = generate_password_hash(data['password'])
    new_user = User(
        username=data['username'],
        password=hashed_password,
        user_type=data['user_type'],
        is_active=data.get('is_active', True),
        employee_id=data.get('employee_id'),
        department_id=data.get('department_id'),
        branch_id=data.get('branch_id')
    )

    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({'message': 'تم إنشاء المستخدم بنجاح'}), 201

@auth_routes.route('/api/auth/update/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    data = request.get_json()
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'message': 'المستخدم غير موجود'}), 404

    # تحديث اسم المستخدم إن وجد
    if 'username' in data:
        # تحقق من التكرار
        if User.query.filter_by(username=data['username']).first() and data['username'] != user.username:
            return jsonify({'message': 'اسم المستخدم مستخدم بالفعل'}), 409
        user.username = data['username']

    # تحديث كلمة المرور
    if 'password' in data and data['password']:
        user.password = generate_password_hash(data['password'])

    # تحديث نوع المستخدم
    if 'user_type' in data:
        user.user_type = data['user_type']

    # تحديث حالة التفعيل
    if 'is_active' in data:
        user.is_active = data['is_active']

    # تحديث الربط بالموظف، القسم، الفرع
    user.employee_id = data.get('employee_id', user.employee_id)
    user.department_id = data.get('department_id', user.department_id)
    user.branch_id = data.get('branch_id', user.branch_id)

    db.session.commit()

    return jsonify({'message': 'تم تحديث بيانات المستخدم بنجاح'}), 200


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

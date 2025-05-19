from flask import Blueprint, request, jsonify
from app import db
from app.utils import token_required
from app.models import Branch, Department, User, Employee, JobTitle
from sqlalchemy import or_, and_, not_, func
from werkzeug.security import generate_password_hash

# =========================== User Management Routes ===========================

user_bp = Blueprint('user', __name__)

# إنشاء مستخدم جديد
@user_bp.route('/api/users', methods=['POST'])
@token_required
def create_user(current_user_id):
    data = request.get_json()
    
    if not data or not data.get('username') or not data.get('password') or not data.get('user_type'):
        return jsonify({'message': 'جميع البيانات المطلوبة غير مكتملة'}), 400
    
    try:
        # التحقق من عدم وجود مستخدم بنفس اسم المستخدم
        existing_user = User.query.filter_by(username=data['username']).first()
        if existing_user:
            return jsonify({'message': 'اسم المستخدم موجود بالفعل'}), 400
        
        # التحقق من صحة نوع المستخدم
        valid_user_types = ['super_admin', 'branch_head', 'department_head', 'branch_deputy', 'department_deputy', 'employee']
        if data['user_type'] not in valid_user_types:
            return jsonify({'message': 'نوع المستخدم غير صالح'}), 400
        
        # إذا كان المستخدم ليس مدير نظام، يجب تحديد معرف الموظف
        if data['user_type'] != 'super_admin' and not data.get('employee_id'):
            return jsonify({'message': 'معرف الموظف مطلوب لهذا النوع من المستخدمين'}), 400
        
        employee_id = data.get('employee_id')
        department_id = data.get('department_id')
        branch_id = data.get('branch_id')
        
        # التحقق مما إذا كان هناك موظف بالمعرف المحدد
        if employee_id:
            employee = Employee.query.get(employee_id)
            if not employee:
                return jsonify({'message': 'الموظف غير موجود'}), 400
                
            # التحقق مما إذا كان للموظف حساب بالفعل
            existing_employee_user = User.query.filter_by(employee_id=employee_id).first()
            if existing_employee_user:
                return jsonify({'message': 'الموظف لديه حساب مستخدم بالفعل'}), 400
        
        # التحقق من وجود القسم والفرع
        if department_id:
            department = Department.query.get(department_id)
            if not department:
                return jsonify({'message': 'القسم غير موجود'}), 400
                
            # في حالة رئيس القسم، تأكد من عدم وجود رئيس آخر
            if data['user_type'] == 'department_head':
                existing_head = User.query.filter_by(department_id=department_id, user_type='department_head').first()
                if existing_head:
                    return jsonify({'message': 'يوجد رئيس قسم آخر لهذا القسم بالفعل'}), 400
        
        if branch_id:
            branch = Branch.query.get(branch_id)
            if not branch:
                return jsonify({'message': 'الفرع غير موجود'}), 400
                
            # في حالة رئيس الفرع، تأكد من عدم وجود رئيس آخر
            if data['user_type'] == 'branch_head':
                existing_head = User.query.filter_by(branch_id=branch_id, user_type='branch_head').first()
                if existing_head:
                    return jsonify({'message': 'يوجد رئيس فرع آخر لهذا الفرع بالفعل'}), 400
        
        # إنشاء المستخدم الجديد
        user = User(
            username=data['username'],
            user_type=data['user_type'],
            employee_id=employee_id,
            department_id=department_id,
            branch_id=branch_id,
            is_active=data.get('is_active', True)
        )
        
        # تشفير كلمة المرور
        user.set_password(data['password'])
        
        # تحديث معلومات الموظف إذا لزم الأمر
        if employee_id:
            employee = Employee.query.get(employee_id)
            
            # إذا كان المستخدم رئيس قسم أو نائب رئيس قسم، تأكد من تعيين القسم للموظف
            if (data['user_type'] in ['department_head', 'department_deputy']) and department_id:
                employee.department_id = department_id
            
            # إذا كان المستخدم رئيس فرع أو نائب رئيس فرع، تأكد من تعيين الفرع للموظف
            if (data['user_type'] in ['branch_head', 'branch_deputy']) and branch_id:
                employee.branch_id = branch_id
        
        db.session.add(user)
        db.session.commit()
        
        return jsonify({
            'message': 'تم إنشاء المستخدم بنجاح',
            'user': {
                'id': user.id,
                'username': user.username,
                'user_type': user.user_type,
                'employee_id': user.employee_id,
                'department_id': user.department_id,
                'branch_id': user.branch_id,
                'is_active': user.is_active
            }
        }), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'حدث خطأ أثناء إنشاء المستخدم: {str(e)}'}), 500

# الحصول على جميع المستخدمين
@user_bp.route('/api/users', methods=['GET'])
@token_required
def get_all_users(current_user_id):
    try:
        users = User.query.all()
        
        result = []
        for user in users:
            employee_data = None
            if user.employee_id:
                employee = user.employee
                employee_data = {
                    'id': employee.id,
                    'full_name': employee.full_name,
                    'fingerprint_id': employee.fingerprint_id
                }
            
            department_data = None
            if user.department_id:
                department = user.department
                department_data = {
                    'id': department.id,
                    'name': department.name
                }
            
            branch_data = None
            if user.branch_id:
                branch = user.branch
                branch_data = {
                    'id': branch.id,
                    'name': branch.name
                }
            
            result.append({
                'id': user.id,
                'username': user.username,
                'user_type': user.user_type,
                'is_active': user.is_active,
                'employee': employee_data,
                'department': department_data,
                'branch': branch_data,
                'created_at': user.created_at.isoformat(),
                'updated_at': user.updated_at.isoformat()
            })
        
        return jsonify(result), 200
    
    except Exception as e:
        return jsonify({'message': f'حدث خطأ أثناء جلب المستخدمين: {str(e)}'}), 500

# الحصول على مستخدم محدد
@user_bp.route('/api/users/<int:id>', methods=['GET'])
@token_required
def get_user(current_user_id, id):
    try:
        user = User.query.get(id)
        
        if not user:
            return jsonify({'message': 'المستخدم غير موجود'}), 404
        
        employee_data = None
        if user.employee_id:
            employee = user.employee
            employee_data = {
                'id': employee.id,
                'full_name': employee.full_name,
                'fingerprint_id': employee.fingerprint_id,
                'branch_id': employee.branch_id,
                'department_id': employee.department_id
            }
        
        department_data = None
        if user.department_id:
            department = user.department
            department_data = {
                'id': department.id,
                'name': department.name
            }
        
        branch_data = None
        if user.branch_id:
            branch = user.branch
            branch_data = {
                'id': branch.id,
                'name': branch.name
            }
        
        return jsonify({
            'id': user.id,
            'username': user.username,
            'user_type': user.user_type,
            'is_active': user.is_active,
            'employee': employee_data,
            'department': department_data,
            'branch': branch_data,
            'created_at': user.created_at.isoformat(),
            'updated_at': user.updated_at.isoformat()
        }), 200
    
    except Exception as e:
        return jsonify({'message': f'حدث خطأ أثناء جلب المستخدم: {str(e)}'}), 500

# تحديث مستخدم
@user_bp.route('/api/users/<int:id>', methods=['PUT'])
@token_required
def update_user(current_user_id, id):
    try:
        user = User.query.get(id)
        
        if not user:
            return jsonify({'message': 'المستخدم غير موجود'}), 404
        
        data = request.get_json()
        
        # تحديث اسم المستخدم
        if data.get('username') and data['username'] != user.username:
            # التحقق من عدم وجود مستخدم آخر بنفس اسم المستخدم
            existing_user = User.query.filter_by(username=data['username']).first()
            if existing_user and existing_user.id != id:
                return jsonify({'message': 'اسم المستخدم موجود بالفعل'}), 400
            
            user.username = data['username']
        
        # تحديث كلمة المرور
        if data.get('password'):
            user.set_password(data['password'])
        
        # تحديث حالة المستخدم
        if 'is_active' in data:
            user.is_active = data['is_active']
        
        # تحديث نوع المستخدم
        if data.get('user_type'):
            valid_user_types = ['super_admin', 'branch_head', 'department_head', 'branch_deputy', 'department_deputy', 'employee']
            if data['user_type'] not in valid_user_types:
                return jsonify({'message': 'نوع المستخدم غير صالح'}), 400
            
            old_user_type = user.user_type
            new_user_type = data['user_type']
            
            # إذا كان التغيير من مدير نظام إلى نوع آخر، يجب تحديد معرف الموظف
            if old_user_type == 'super_admin' and new_user_type != 'super_admin' and not user.employee_id and not data.get('employee_id'):
                return jsonify({'message': 'معرف الموظف مطلوب لهذا النوع من المستخدمين'}), 400
            
            # تحديث معرف الموظف
            if data.get('employee_id') and data['employee_id'] != user.employee_id:
                employee = Employee.query.get(data['employee_id'])
                if not employee:
                    return jsonify({'message': 'الموظف غير موجود'}), 400
                
                # التحقق مما إذا كان للموظف حساب بالفعل
                existing_employee_user = User.query.filter_by(employee_id=data['employee_id']).first()
                if existing_employee_user and existing_employee_user.id != id:
                    return jsonify({'message': 'الموظف لديه حساب مستخدم بالفعل'}), 400
                
                user.employee_id = data['employee_id']
            
            # تحديث معرف القسم
            if data.get('department_id') is not None:
                if data['department_id']:
                    department = Department.query.get(data['department_id'])
                    if not department:
                        return jsonify({'message': 'القسم غير موجود'}), 400
                    
                    # في حالة رئيس القسم، تأكد من عدم وجود رئيس آخر
                    if new_user_type == 'department_head' and (old_user_type != 'department_head' or user.department_id != data['department_id']):
                        existing_head = User.query.filter_by(department_id=data['department_id'], user_type='department_head').first()
                        if existing_head and existing_head.id != id:
                            return jsonify({'message': 'يوجد رئيس قسم آخر لهذا القسم بالفعل'}), 400
                
                user.department_id = data['department_id']
                
                # تحديث معلومات الموظف
                if user.employee_id and new_user_type in ['department_head', 'department_deputy']:
                    employee = Employee.query.get(user.employee_id)
                    employee.department_id = data['department_id']
            
            # تحديث معرف الفرع
            if data.get('branch_id') is not None:
                if data['branch_id']:
                    branch = Branch.query.get(data['branch_id'])
                    if not branch:
                        return jsonify({'message': 'الفرع غير موجود'}), 400
                    
                    # في حالة رئيس الفرع، تأكد من عدم وجود رئيس آخر
                    if new_user_type == 'branch_head' and (old_user_type != 'branch_head' or user.branch_id != data['branch_id']):
                        existing_head = User.query.filter_by(branch_id=data['branch_id'], user_type='branch_head').first()
                        if existing_head and existing_head.id != id:
                            return jsonify({'message': 'يوجد رئيس فرع آخر لهذا الفرع بالفعل'}), 400
                
                user.branch_id = data['branch_id']
                
                # تحديث معلومات الموظف
                if user.employee_id and new_user_type in ['branch_head', 'branch_deputy']:
                    employee = Employee.query.get(user.employee_id)
                    employee.branch_id = data['branch_id']
            
            # تحديث نوع المستخدم بعد التحقق من كل شيء
            user.user_type = new_user_type
        
        db.session.commit()
        
        return jsonify({
            'message': 'تم تحديث المستخدم بنجاح',
            'user': {
                'id': user.id,
                'username': user.username,
                'user_type': user.user_type,
                'employee_id': user.employee_id,
                'department_id': user.department_id,
                'branch_id': user.branch_id,
                'is_active': user.is_active
            }
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'حدث خطأ أثناء تحديث المستخدم: {str(e)}'}), 500

# حذف مستخدم
@user_bp.route('/api/users/<int:id>', methods=['DELETE'])
@token_required
def delete_user(current_user_id, id):
    try:
        user = User.query.get(id)
        
        if not user:
            return jsonify({'message': 'المستخدم غير موجود'}), 404
        
        # التحقق من عدم محاولة حذف المستخدم لنفسه
        if id == current_user_id:
            return jsonify({'message': 'لا يمكن حذف المستخدم الحالي'}), 400
        
        # التحقق من دور المستخدم قبل الحذف
        user_type = user.user_type
        employee_id = user.employee_id
        department_id = user.department_id
        branch_id = user.branch_id
        
        db.session.delete(user)
        db.session.commit()
        
        return jsonify({
            'message': 'تم حذف المستخدم بنجاح'
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'حدث خطأ أثناء حذف المستخدم: {str(e)}'}), 500

# تغيير كلمة المرور
@user_bp.route('/api/users/<int:id>/change-password', methods=['PUT'])
@token_required
def change_password(current_user_id, id):
    try:
        user = User.query.get(id)
        
        if not user:
            return jsonify({'message': 'المستخدم غير موجود'}), 404
        
        data = request.get_json()
        
        if not data or not data.get('new_password'):
            return jsonify({'message': 'كلمة المرور الجديدة مطلوبة'}), 400
        
        # التحقق من كلمة المرور القديمة إذا كان المستخدم يغير كلمة المرور الخاصة به
        if current_user_id == id:
            if not data.get('old_password'):
                return jsonify({'message': 'كلمة المرور القديمة مطلوبة'}), 400
            
            if not user.check_password(data['old_password']):
                return jsonify({'message': 'كلمة المرور القديمة غير صحيحة'}), 400
        
        # تغيير كلمة المرور
        user.set_password(data['new_password'])
        db.session.commit()
        
        return jsonify({
            'message': 'تم تغيير كلمة المرور بنجاح'
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'حدث خطأ أثناء تغيير كلمة المرور: {str(e)}'}), 500

# تعطيل أو تفعيل مستخدم
@user_bp.route('/api/users/<int:id>/toggle-status', methods=['PUT'])
@token_required
def toggle_user_status(current_user_id, id):
    try:
        user = User.query.get(id)
        
        if not user:
            return jsonify({'message': 'المستخدم غير موجود'}), 404
        
        # التحقق من عدم محاولة تعطيل المستخدم لنفسه
        if id == current_user_id:
            return jsonify({'message': 'لا يمكن تعطيل المستخدم الحالي'}), 400
        
        # تغيير حالة المستخدم
        user.is_active = not user.is_active
        db.session.commit()
        
        status = 'تفعيل' if user.is_active else 'تعطيل'
        
        return jsonify({
            'message': f'تم {status} المستخدم بنجاح',
            'is_active': user.is_active
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'حدث خطأ أثناء تغيير حالة المستخدم: {str(e)}'}), 500

# الحصول على مستخدمي القسم
@user_bp.route('/api/departments/<int:dept_id>/users', methods=['GET'])
@token_required
def get_department_users(current_user_id, dept_id):
    try:
        department = Department.query.get(dept_id)
        
        if not department:
            return jsonify({'message': 'القسم غير موجود'}), 404
        
        users = User.query.filter_by(department_id=dept_id).all()
        
        result = []
        for user in users:
            employee_data = None
            if user.employee_id:
                employee = user.employee
                employee_data = {
                    'id': employee.id,
                    'full_name': employee.full_name,
                    'fingerprint_id': employee.fingerprint_id
                }
            
            result.append({
                'id': user.id,
                'username': user.username,
                'user_type': user.user_type,
                'is_active': user.is_active,
                'employee': employee_data,
                'created_at': user.created_at.isoformat(),
                'updated_at': user.updated_at.isoformat()
            })
        
        return jsonify(result), 200
    
    except Exception as e:
        return jsonify({'message': f'حدث خطأ أثناء جلب مستخدمي القسم: {str(e)}'}), 500

# الحصول على مستخدمي الفرع
@user_bp.route('/api/branches/<int:branch_id>/users', methods=['GET'])
@token_required
def get_branch_users(current_user_id, branch_id):
    try:
        branch = Branch.query.get(branch_id)
        
        if not branch:
            return jsonify({'message': 'الفرع غير موجود'}), 404
        
        users = User.query.filter_by(branch_id=branch_id).all()
        
        result = []
        for user in users:
            employee_data = None
            if user.employee_id:
                employee = user.employee
                employee_data = {
                    'id': employee.id,
                    'full_name': employee.full_name,
                    'fingerprint_id': employee.fingerprint_id
                }
            
            department_data = None
            if user.department_id:
                department = user.department
                department_data = {
                    'id': department.id,
                    'name': department.name
                }
            
            result.append({
                'id': user.id,
                'username': user.username,
                'user_type': user.user_type,
                'is_active': user.is_active,
                'employee': employee_data,
                'department': department_data,
                'created_at': user.created_at.isoformat(),
                'updated_at': user.updated_at.isoformat()
            })
        
        return jsonify(result), 200
    
    except Exception as e:
        return jsonify({'message': f'حدث خطأ أثناء جلب مستخدمي الفرع: {str(e)}'}), 500
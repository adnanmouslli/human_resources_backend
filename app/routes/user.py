from flask import Blueprint, request, jsonify
from app import db
from app.models.user import UserBranchHead, UserDepartmentHead
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
        
        # التحقق مما إذا كان هناك موظف بالمعرف المحدد
        if employee_id:
            employee = Employee.query.get(employee_id)
            if not employee:
                return jsonify({'message': 'الموظف غير موجود'}), 400
                
            # التحقق مما إذا كان للموظف حساب بالفعل
            existing_employee_user = User.query.filter_by(employee_id=employee_id).first()
            if existing_employee_user:
                return jsonify({'message': 'الموظف لديه حساب مستخدم بالفعل'}), 400
        
        # إنشاء المستخدم الجديد
        user = User(
            username=data['username'],
            user_type=data['user_type'],
            employee_id=employee_id,
            is_active=data.get('is_active', True)
        )
        
        # تشفير كلمة المرور
        user.set_password(data['password'])
        
        db.session.add(user)
        db.session.flush()  # للحصول على معرف المستخدم
        
        # إضافة الصلاحيات الإدارية (الأقسام والفروع)
        managed_departments = data.get('managed_departments', [])
        managed_branches = data.get('managed_branches', [])
        
        # إضافة إدارة الأقسام
        for dept_info in managed_departments:
            if isinstance(dept_info, dict):
                dept_id = dept_info.get('id')
                role_type = dept_info.get('role_type', 'head')
            else:
                dept_id = dept_info
                role_type = 'head' if data['user_type'] == 'department_head' else 'deputy'
            
            if dept_id:
                department = Department.query.get(dept_id)
                if department:
                    user.add_department_management(dept_id, role_type)
        
        # إضافة إدارة الفروع
        for branch_info in managed_branches:
            if isinstance(branch_info, dict):
                branch_id = branch_info.get('id')
                role_type = branch_info.get('role_type', 'head')
            else:
                branch_id = branch_info
                role_type = 'head' if data['user_type'] == 'branch_head' else 'deputy'
            
            if branch_id:
                branch = Branch.query.get(branch_id)
                if branch:
                    user.add_branch_management(branch_id, role_type)
        
        # للتوافق مع النظام القديم - إضافة أول قسم/فرع كقيم افتراضي
        if managed_departments and not user.department_id:
            first_dept = managed_departments[0]
            dept_id = first_dept.get('id') if isinstance(first_dept, dict) else first_dept
            user.department_id = dept_id
        
        if managed_branches and not user.branch_id:
            first_branch = managed_branches[0]
            branch_id = first_branch.get('id') if isinstance(first_branch, dict) else first_branch
            user.branch_id = branch_id
        
        db.session.commit()
        
        return jsonify({
            'message': 'تم إنشاء المستخدم بنجاح',
            'user': {
                'id': user.id,
                'username': user.username,
                'user_type': user.user_type,
                'employee_id': user.employee_id,
                'managed_departments': user.get_managed_department_ids(),
                'managed_branches': user.get_managed_branch_ids(),
                'is_active': user.is_active
            }
        }), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'حدث خطأ أثناء إنشاء المستخدم: {str(e)}'}), 500


# الحصول على جميع المستخدمين مع معلومات الإدارة
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
            
            # الأقسام المُدارة
            managed_departments = []
            for dept_id in user.get_managed_department_ids():
                dept = Department.query.get(dept_id)
                if dept:
                    # الحصول على نوع الدور
                    management = UserDepartmentHead.query.filter_by(
                        user_id=user.id, 
                        department_id=dept_id
                    ).first()
                    role_type = management.role_type if management else 'head'
                    
                    managed_departments.append({
                        'id': dept.id,
                        'name': dept.name,
                        'role_type': role_type
                    })
            
            # الفروع المُدارة
            managed_branches = []
            for branch_id in user.get_managed_branch_ids():
                branch = Branch.query.get(branch_id)
                if branch:
                    # الحصول على نوع الدور
                    management = UserBranchHead.query.filter_by(
                        user_id=user.id, 
                        branch_id=branch_id
                    ).first()
                    role_type = management.role_type if management else 'head'
                    
                    managed_branches.append({
                        'id': branch.id,
                        'name': branch.name,
                        'role_type': role_type
                    })
            
            # للتوافق مع النظام القديم
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
                'department': department_data,  # للتوافق القديم
                'branch': branch_data,  # للتوافق القديم
                'managed_departments': managed_departments,
                'managed_branches': managed_branches,
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
        
        # بيانات الموظف
        employee_data = None
        if user.employee_id:
            employee = user.employee
            employee_data = {
                'id': employee.id,
                'full_name': employee.full_name,
                'fingerprint_id': employee.fingerprint_id,
                'branch': {
                    'id': employee.branch.id,
                    'name': employee.branch.name
                } if employee.branch else None,
                'department': {
                    'id': employee.department.id,
                    'name': employee.department.name
                } if employee.department else None
            }
        
        # بيانات القسم المرتبط بالمستخدم
        department_data = None
        if user.department_id:
            department = user.department
            department_data = {
                'id': department.id,
                'name': department.name
            }
        
        # بيانات الفرع المرتبط بالمستخدم
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
def delete_user(current_user, id):
    try:
        user = User.query.get(id)
        
        if not user:
            return jsonify({'message': 'المستخدم غير موجود'}), 404
        
        # التحقق من عدم محاولة حذف المستخدم لنفسه
        if id == current_user.id:
            return jsonify({'message': 'لا يمكن حذف المستخدم الحالي'}), 400
        
        # التحقق من الصلاحيات
        if not current_user.is_super_admin():
            if current_user.is_branch_head():
                if user.user_type in ['branch_head'] and current_user.branch_id != user.branch_id:
                    return jsonify({'message': 'ليس لديك صلاحية لحذف رئيس فرع من فرع آخر'}), 403
                if user.user_type == 'super_admin':
                    return jsonify({'message': 'ليس لديك صلاحية لحذف مدير النظام'}), 403
            else:
                return jsonify({'message': 'ليس لديك صلاحية لحذف المستخدمين'}), 403
        
        # حفظ معلومات المستخدم للسجل
        username = user.username
        user_type = user.user_type
        employee_id = user.employee_id
        
        print(f"Deleting user: {username} (Type: {user_type})")
        
        deleted_count = 0
        
        # 1. حذف علاقات النظام الجديد - إدارة الأقسام
        try:
            from app.models.user import UserDepartmentHead
            UserDepartmentHead.query.filter_by(user_id=user.id).delete()
            print("Deleted department management relations")
        except ImportError:
            pass
        
        # 2. حذف علاقات النظام الجديد - إدارة الفروع  
        try:
            from app.models.user import UserBranchHead
            UserBranchHead.query.filter_by(user_id=user.id).delete()
            print("Deleted branch management relations")
        except ImportError:
            pass
        
        # 3. حذف سجلات transaction_history
        try:
            from app.models.transaction_history import TransactionHistory
            TransactionHistory.query.filter_by(user_id=user.id).delete()
            print("Deleted transaction history")
        except ImportError:
            pass
        
        # 4. حذف transaction_approvals
        try:
            from app.models.transaction import TransactionApproval
            TransactionApproval.query.filter_by(approver_id=user.id).delete()
            print("Deleted transaction approvals")
        except ImportError:
            pass
        
        # 5. حذف المعاملات التي طلبها المستخدم
        try:
            from app.models.transaction import Transaction
            # حذف الموافقات المرتبطة أولاً
            user_transactions = Transaction.query.filter_by(requested_by=user.id).all()
            for transaction in user_transactions:
                try:
                    TransactionApproval.query.filter_by(transaction_id=transaction.id).delete()
                except:
                    pass
            # ثم حذف المعاملات
            Transaction.query.filter_by(requested_by=user.id).delete()
            print("Deleted user transactions")
        except ImportError:
            pass
        
        # 6. تحديث الموظف المرتبط
        if employee_id:
            from app.models.employee import Employee
            employee = Employee.query.get(employee_id)
            if employee:
                employee.branch_id = None
                employee.department_id = None
                if hasattr(employee, 'is_manager'):
                    employee.is_manager = False
                print(f"Cleared employee {employee.full_name} assignment")
        
        # 7. حذف المستخدم نفسه
        db.session.delete(user)
        db.session.commit()
        
        print(f"Successfully deleted user: {username}")
        
        return jsonify({
            'message': 'تم حذف المستخدم وجميع البيانات المرتبطة به بنجاح',
            'deleted_user': {
                'username': username,
                'user_type': user_type,
                'employee_id': employee_id
            }
        }), 200
    
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting user: {str(e)}")
        return jsonify({
            'message': f'حدث خطأ أثناء حذف المستخدم: {str(e)}'
        }), 500
       
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
    


# الحصول على الموظفين الذين يمكن للمستخدم الوصول إليهم
@user_bp.route('/api/users/<int:id>/accessible-employees', methods=['GET'])
@token_required
def get_user_accessible_employees(current_user_id, id):
    try:
        user = User.query.get(id)
        
        if not user:
            return jsonify({'message': 'المستخدم غير موجود'}), 404
        
        accessible_employees = user.get_accessible_employees()
        
        result = []
        for employee in accessible_employees:
            department_data = None
            if employee.department:
                department_data = {
                    'id': employee.department.id,
                    'name': employee.department.name
                }
            
            branch_data = None
            if employee.branch:
                branch_data = {
                    'id': employee.branch.id,
                    'name': employee.branch.name
                }
            
            result.append({
                'id': employee.id,
                'full_name': employee.full_name,
                'fingerprint_id': employee.fingerprint_id,
                'department': department_data,
                'branch': branch_data
            })
        
        return jsonify({
            'user_id': user.id,
            'username': user.username,
            'user_type': user.user_type,
            'managed_departments': user.get_managed_department_ids(),
            'managed_branches': user.get_managed_branch_ids(),
            'accessible_employees': result,
            'total_count': len(result)
        }), 200
    
    except Exception as e:
        return jsonify({'message': f'حدث خطأ أثناء جلب الموظفين: {str(e)}'}), 500


from app import db
from flask import Blueprint, request, jsonify

from app.models import Branch, Department, BranchDepartment, Employee, User, JobTitle, UserBranchHead, UserDepartmentHead, Transaction, TransactionApproval, TransactionHistory

from app.models.transaction import TransactionApproval
from app.models.transaction_history import TransactionHistory
from app.models.user import UserBranchHead, UserDepartmentHead
from app.utils import token_required

from sqlalchemy import or_, and_, not_, func

from werkzeug.security import generate_password_hash
import re

# إنشاء كائن Blueprint للفروع والأقسام
branch_dept_bp = Blueprint('branch_dept', __name__)

# ==================== Branch Routes ====================


# إنشاء فرع جديد
@branch_dept_bp.route('/api/branches', methods=['POST'])
@token_required
def create_branch(user_id):
    data = request.get_json()
    
    # التحقق من البيانات المطلوبة
    if not data or not data.get('name'):
        return jsonify({'message': 'اسم الفرع مطلوب'}), 400
    
    try:
        # التحقق من عدم وجود فرع بنفس الاسم
        existing_branch = Branch.query.filter_by(name=data['name']).first()
        if existing_branch:
            return jsonify({'message': 'يوجد فرع بنفس الاسم بالفعل'}), 400
        
        # إنشاء فرع جديد
        branch = Branch(
            name=data['name'],
            address=data.get('address'),
            phone=data.get('phone'),
            email=data.get('email'),
            notes=data.get('notes')
        )
        
        db.session.add(branch)
        db.session.commit()
        
        return jsonify({
            'message': 'تم إنشاء الفرع بنجاح',
            'branch': {
                'id': branch.id,
                'name': branch.name
            }
        }), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'حدث خطأ أثناء إنشاء الفرع: {str(e)}'}), 500

# الحصول على جميع الفروع
@branch_dept_bp.route('/api/branches', methods=['GET'])
@token_required
def get_all_branches(user_id):
    try:
        branches = Branch.query.all()
        
        return jsonify([{
            'id': branch.id,
            'name': branch.name,
            'address': branch.address,
            'phone': branch.phone,
            'email': branch.email,
            'notes': branch.notes,
            'departments': [{'id': dept.id, 'name': dept.name} for dept in branch.departments],
            'created_at': branch.created_at.isoformat(),
            'updated_at': branch.updated_at.isoformat()
        } for branch in branches]), 200
    
    except Exception as e:
        return jsonify({'message': f'حدث خطأ أثناء جلب الفروع: {str(e)}'}), 500

# الحصول على فرع محدد
@branch_dept_bp.route('/api/branches/<int:id>', methods=['GET'])
@token_required
def get_branch(user_id, id):
    try:
        branch = Branch.query.get(id)
        
        if not branch:
            return jsonify({'message': 'الفرع غير موجود'}), 404
        
        # الحصول على رئيس الفرع
        branch_head = branch.get_branch_head()
        head_info = None
        if branch_head and branch_head.employee:
            head_info = {
                'id': branch_head.employee.id,
                'full_name': branch_head.employee.full_name
            }
        
        return jsonify({
            'id': branch.id,
            'name': branch.name,
            'address': branch.address,
            'phone': branch.phone,
            'email': branch.email,
            'notes': branch.notes,
            'departments': [{'id': dept.id, 'name': dept.name} for dept in branch.departments],
            'head': head_info,
            'created_at': branch.created_at.isoformat(),
            'updated_at': branch.updated_at.isoformat()
        }), 200
    
    except Exception as e:
        return jsonify({'message': f'حدث خطأ أثناء جلب الفرع: {str(e)}'}), 500

# تحديث فرع
@branch_dept_bp.route('/api/branches/<int:id>', methods=['PUT'])
@token_required
def update_branch(user_id, id):
    try:
        branch = Branch.query.get(id)
        
        if not branch:
            return jsonify({'message': 'الفرع غير موجود'}), 404
        
        data = request.get_json()
        
        # التحقق من عدم وجود فرع آخر بنفس الاسم الجديد
        if data.get('name') and data['name'] != branch.name:
            existing_branch = Branch.query.filter_by(name=data['name']).first()
            if existing_branch:
                return jsonify({'message': 'يوجد فرع آخر بنفس الاسم'}), 400
        
        if data.get('name'):
            branch.name = data['name']
        if 'address' in data:
            branch.address = data['address']
        if 'phone' in data:
            branch.phone = data['phone']
        if 'email' in data:
            branch.email = data['email']
        if 'notes' in data:
            branch.notes = data['notes']
        
        db.session.commit()
        
        return jsonify({
            'message': 'تم تحديث الفرع بنجاح',
            'branch': {
                'id': branch.id,
                'name': branch.name
            }
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'حدث خطأ أثناء تحديث الفرع: {str(e)}'}), 500

# حذف فرع
@branch_dept_bp.route('/api/branches/<int:id>', methods=['DELETE'])
@token_required
def delete_branch(user_id, id):
    try:
        branch = Branch.query.get(id)
        
        if not branch:
            return jsonify({'message': 'الفرع غير موجود'}), 404
        
        # التحقق من وجود موظفين مرتبطين بالفرع
        has_employees = Employee.query.filter_by(branch_id=id).first()
        if has_employees:
            return jsonify({
                'status': 400,
                'message': 'لا يمكن حذف الفرع لوجود موظفين مرتبطين به'
            }), 200
        
        # التحقق من وجود مستخدمين مرتبطين بالفرع
        has_users = User.query.filter_by(branch_id=id).first()
        if has_users:
            return jsonify({
                'status': 400,
                'message': 'لا يمكن حذف الفرع لوجود مستخدمين مرتبطين به'
            }), 200
        
        # حذف العلاقات مع الأقسام أولاً
        BranchDepartment.query.filter_by(branch_id=id).delete()
        
        # حذف الفرع
        db.session.delete(branch)
        db.session.commit()
        
        return jsonify({
            'status': 200,
            'message': 'تم حذف الفرع بنجاح'
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'حدث خطأ أثناء حذف الفرع: {str(e)}'}), 500

# ==================== Department Routes ====================

# إنشاء قسم جديد
@branch_dept_bp.route('/api/departments', methods=['POST'])
@token_required
def create_department(user_id):
    data = request.get_json()
    
    # التحقق من البيانات المطلوبة
    if not data or not data.get('name'):
        return jsonify({'message': 'اسم القسم مطلوب'}), 400
    
    try:
        # التحقق من عدم وجود قسم بنفس الاسم
        existing_department = Department.query.filter_by(name=data['name']).first()
        if existing_department:
            return jsonify({'message': 'يوجد قسم بنفس الاسم بالفعل'}), 400
        
        # إنشاء قسم جديد
        department = Department(
            name=data['name'],
            description=data.get('description')
        )
        
        # ربط القسم مع الفروع إذا تم تحديد الفروع
        if data.get('branch_ids'):
            for branch_id in data['branch_ids']:
                branch = Branch.query.get(branch_id)
                if branch:
                    department.branches.append(branch)
        
        db.session.add(department)
        db.session.commit()
        
        return jsonify({
            'message': 'تم إنشاء القسم بنجاح',
            'department': {
                'id': department.id,
                'name': department.name
            }
        }), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'حدث خطأ أثناء إنشاء القسم: {str(e)}'}), 500



@branch_dept_bp.route('/api/departments', methods=['GET'])
@token_required
def get_all_departments(user):
    try:
        
        departments = Department.query.all()
        result = []

        for dept in departments:
            # الحصول على معلومات رئيس القسم
            head = dept.get_department_head()
            head_info = None
            
            if head and head.employee:
                head_info = {
                    'id': head.employee.id,
                    'full_name': head.employee.full_name
                }
            
            result.append({
                'id': dept.id,
                'name': dept.name,
                'description': dept.description,
                'head': head_info,
                'branches': [{'id': branch.id, 'name': branch.name} for branch in dept.branches],
                'created_at': dept.created_at.isoformat(),
                'updated_at': dept.updated_at.isoformat()
            })

        return jsonify(result), 200

    except Exception as e:
        return jsonify({'message': f'حدث خطأ أثناء جلب الأقسام: {str(e)}'}), 500

# الحصول على قسم محدد
@branch_dept_bp.route('/api/departments/<int:id>', methods=['GET'])
@token_required
def get_department(user_id, id):
    try:
        department = Department.query.get(id)
        
        if not department:
            return jsonify({'message': 'القسم غير موجود'}), 404
        
        # الحصول على معلومات رئيس القسم
        head = department.get_department_head()
        head_info = None
        if head and head.employee:
            head_info = {
                'id': head.employee.id,
                'full_name': head.employee.full_name
            }
        
        # الحصول على معلومات الموظفين في القسم
        employees = department.employees.all()
        employee_list = [{
            'id': emp.id,
            'full_name': emp.full_name,
            'is_department_head': emp.is_department_head()
        } for emp in employees]
        
        return jsonify({
            'id': department.id,
            'name': department.name,
            'description': department.description,
            'head': head_info,
            'branches': [{'id': branch.id, 'name': branch.name} for branch in department.branches],
            'employees': employee_list,
            'created_at': department.created_at.isoformat(),
            'updated_at': department.updated_at.isoformat()
        }), 200
    
    except Exception as e:
        return jsonify({'message': f'حدث خطأ أثناء جلب القسم: {str(e)}'}), 500

# تحديث قسم
@branch_dept_bp.route('/api/departments/<int:id>', methods=['PUT'])
@token_required
def update_department(user_id, id):
    try:
        department = Department.query.get(id)
        
        if not department:
            return jsonify({'message': 'القسم غير موجود'}), 404
        
        data = request.get_json()
        
        # التحقق من عدم وجود قسم آخر بنفس الاسم الجديد
        if data.get('name') and data['name'] != department.name:
            existing_department = Department.query.filter_by(name=data['name']).first()
            if existing_department:
                return jsonify({'message': 'يوجد قسم آخر بنفس الاسم'}), 400
        
        if data.get('name'):
            department.name = data['name']
        if 'description' in data:
            department.description = data['description']
        
        # تحديث الفروع المرتبطة بالقسم
        if 'branch_ids' in data:
            # إزالة الارتباطات القديمة
            BranchDepartment.query.filter_by(department_id=id).delete()
            
            # إضافة الارتباطات الجديدة
            for branch_id in data['branch_ids']:
                branch = Branch.query.get(branch_id)
                if branch:
                    department.branches.append(branch)
        
        db.session.commit()
        
        return jsonify({
            'message': 'تم تحديث القسم بنجاح',
            'department': {
                'id': department.id,
                'name': department.name
            }
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'حدث خطأ أثناء تحديث القسم: {str(e)}'}), 500

# حذف قسم
@branch_dept_bp.route('/api/departments/<int:id>', methods=['DELETE'])
@token_required
def delete_department(user_id, id):
    try:
        department = Department.query.get(id)
        
        if not department:
            return jsonify({'message': 'القسم غير موجود'}), 404
        
        # التحقق من وجود موظفين مرتبطين بالقسم
        has_employees = department.employees.first()
        if has_employees:
            return jsonify({
                'status': 400,
                'message': 'لا يمكن حذف القسم لوجود موظفين مرتبطين به'
            }), 200
        
        # التحقق من وجود مستخدمين مرتبطين بالقسم
        has_users = department.users.first()
        if has_users:
            return jsonify({
                'status': 400,
                'message': 'لا يمكن حذف القسم لوجود مستخدمين مرتبطين به'
            }), 200
        
        # حذف العلاقات مع الفروع أولاً
        BranchDepartment.query.filter_by(department_id=id).delete()
        
        # حذف القسم
        db.session.delete(department)
        db.session.commit()
        
        return jsonify({
            'status': 200,
            'message': 'تم حذف القسم بنجاح'
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'حدث خطأ أثناء حذف القسم: {str(e)}'}), 500
    

# =========================== Branch Department Relationship Routes ===========================

# ربط قسم بفرع
@branch_dept_bp.route('/api/branches/<int:branch_id>/departments/<int:dept_id>', methods=['POST'])
@token_required
def link_branch_department(user_id, branch_id, dept_id):
    try:
        branch = Branch.query.get(branch_id)
        department = Department.query.get(dept_id)
        
        if not branch:
            return jsonify({'message': 'الفرع غير موجود'}), 404
        if not department:
            return jsonify({'message': 'القسم غير موجود'}), 404
        
        # التحقق من عدم وجود ارتباط مسبق
        existing_link = BranchDepartment.query.filter_by(
            branch_id=branch_id, department_id=dept_id
        ).first()
        
        if existing_link:
            return jsonify({'message': 'القسم مرتبط بالفعل بهذا الفرع'}), 400
        
        branch.departments.append(department)
        db.session.commit()
        
        return jsonify({
            'message': 'تم ربط القسم بالفرع بنجاح',
            'branch': branch.name,
            'department': department.name
        }), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'حدث خطأ أثناء ربط القسم بالفرع: {str(e)}'}), 500

# إلغاء ربط قسم بفرع
@branch_dept_bp.route('/api/branches/<int:branch_id>/departments/<int:dept_id>', methods=['DELETE'])
@token_required
def unlink_branch_department(user_id, branch_id, dept_id):
    try:
        link = BranchDepartment.query.filter_by(
            branch_id=branch_id, department_id=dept_id
        ).first()
        
        if not link:
            return jsonify({'message': 'الارتباط غير موجود'}), 404
        
        # التحقق من عدم وجود موظفين في الفرع من هذا القسم
        employees_in_branch_dept = Employee.query.filter_by(
            branch_id=branch_id, department_id=dept_id
        ).first()
        
        if employees_in_branch_dept:
            return jsonify({
                'message': 'لا يمكن إلغاء الارتباط لوجود موظفين في القسم بهذا الفرع'
            }), 400
        
        db.session.delete(link)
        db.session.commit()
        
        return jsonify({
            'message': 'تم إلغاء ربط القسم بالفرع بنجاح'
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'حدث خطأ أثناء إلغاء ربط القسم بالفرع: {str(e)}'}), 500

# الحصول على أقسام فرع معين
@branch_dept_bp.route('/api/branches/<int:branch_id>/departments', methods=['GET'])
@token_required
def get_branch_departments(user_id, branch_id):
    try:
        branch = Branch.query.get(branch_id)
        
        if not branch:
            return jsonify({'message': 'الفرع غير موجود'}), 404
        
        departments = branch.departments
        
        result = []
        for dept in departments:
            # الحصول على معلومات رئيس القسم
            head = dept.get_department_head()
            head_info = None
            if head and head.employee:
                head_info = {
                    'id': head.employee.id,
                    'full_name': head.employee.full_name
                }
                    
            # عدد الموظفين في القسم في هذا الفرع
            employees_count = Employee.query.filter_by(
                department_id=dept.id, 
                branch_id=branch_id
            ).count()
            
            result.append({
                'id': dept.id,
                'name': dept.name,
                'description': dept.description,
                'head': head_info,
                'employees_count': employees_count,
                'created_at': dept.created_at.isoformat(),
                'updated_at': dept.updated_at.isoformat()
            })
        
        return jsonify(result), 200
    
    except Exception as e:
        return jsonify({'message': f'حدث خطأ أثناء جلب أقسام الفرع: {str(e)}'}), 500

# الحصول على فروع قسم معين
@branch_dept_bp.route('/api/departments/<int:dept_id>/branches', methods=['GET'])
@token_required
def get_department_branches(user_id, dept_id):
    try:
        department = Department.query.get(dept_id)
        
        if not department:
            return jsonify({'message': 'القسم غير موجود'}), 404
        
        branches = department.branches
        
        result = []
        for branch in branches:
            # عدد الموظفين في هذا الفرع من هذا القسم
            employees_count = Employee.query.filter_by(
                department_id=dept_id, 
                branch_id=branch.id
            ).count()
            
            result.append({
                'id': branch.id,
                'name': branch.name,
                'address': branch.address,
                'phone': branch.phone,
                'email': branch.email,
                'employees_count': employees_count,
                'created_at': branch.created_at.isoformat(),
                'updated_at': branch.updated_at.isoformat()
            })
        
        return jsonify(result), 200
    
    except Exception as e:
        return jsonify({'message': f'حدث خطأ أثناء جلب فروع القسم: {str(e)}'}), 500

# =========================== Department Management Routes ===========================

# تعيين مستخدم كرئيس قسم
@branch_dept_bp.route('/api/departments/<int:dept_id>/head/<int:user_id>', methods=['POST'])
@token_required
def assign_department_head(current_user_id, dept_id, user_id):
    try:
        department = Department.query.get(dept_id)
        user = User.query.get(user_id)
        
        if not department:
            return jsonify({'message': 'القسم غير موجود'}), 404
        if not user:
            return jsonify({'message': 'المستخدم غير موجود'}), 404
        if not user.employee_id:
            return jsonify({'message': 'المستخدم ليس موظفاً'}), 400
        
        data = request.get_json() or {}
        role_type = data.get('role_type', 'head')
        
        if role_type not in ['head', 'deputy']:
            return jsonify({'message': 'نوع الدور يجب أن يكون head أو deputy'}), 400
        
        # التحقق من عدم وجود إدارة سابقة لنفس المستخدم في نفس القسم
        existing_management = UserDepartmentHead.query.filter_by(
            user_id=user_id, 
            department_id=dept_id
        ).first()
        
        if existing_management:
            return jsonify({'message': 'المستخدم يدير هذا القسم بالفعل'}), 400
        
        # إضافة الإدارة الجديدة
        success = user.add_department_management(dept_id, role_type)
        
        if not success:
            return jsonify({'message': 'فشل في إضافة إدارة القسم'}), 400
        
        # تحديث نوع المستخدم إذا لم يكن مدير بالفعل
        if user.user_type not in ['department_head', 'department_deputy']:
            if role_type == 'head':
                user.user_type = 'department_head'
            else:
                user.user_type = 'department_deputy'
        
        # للتوافق مع النظام القديم - تعيين أول قسم كقيمة افتراضية
        if not user.department_id:
            user.department_id = dept_id
        
        # تأكد من تعيين الموظف في القسم (إذا لم يكن معين)
        employee = user.employee
        if not employee.department_id:
            employee.department_id = dept_id
        
        db.session.commit()
        
        return jsonify({
            'message': f'تم تعيين المستخدم كـ{role_type} للقسم بنجاح',
            'department': department.name,
            'user': user.employee.full_name,
            'role_type': role_type,
            'managed_departments': user.get_managed_department_ids()
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'حدث خطأ أثناء تعيين رئيس القسم: {str(e)}'}), 500

# إلغاء تعيين مستخدم من إدارة قسم
@branch_dept_bp.route('/api/departments/<int:dept_id>/head/<int:user_id>', methods=['DELETE'])
@token_required
def remove_user_from_department(current_user_id, dept_id, user_id):
    try:
        department = Department.query.get(dept_id)
        user = User.query.get(user_id)
        
        if not department:
            return jsonify({'message': 'القسم غير موجود'}), 404
        if not user:
            return jsonify({'message': 'المستخدم غير موجود'}), 404
        
        # إزالة الإدارة
        success = user.remove_department_management(dept_id)
        
        if not success:
            return jsonify({'message': 'المستخدم لا يدير هذا القسم'}), 404
        
        # تحديث نوع المستخدم إذا لم يعد يدير أي قسم
        remaining_departments = user.get_managed_department_ids()
        remaining_branches = user.get_managed_branch_ids()
        
        if not remaining_departments and not remaining_branches:
            user.user_type = 'employee'
            user.department_id = None
            user.branch_id = None
        elif not remaining_departments:
            # لا يزال يدير فروع ولكن لا يدير أقسام
            if user.user_type in ['department_head', 'department_deputy']:
                user.user_type = 'branch_head' if remaining_branches else 'employee'
        
        db.session.commit()
        
        return jsonify({
            'message': 'تم إلغاء تعيين المستخدم من إدارة القسم بنجاح',
            'remaining_managed_departments': remaining_departments,
            'remaining_managed_branches': remaining_branches
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'حدث خطأ أثناء إلغاء تعيين رئيس القسم: {str(e)}'}), 500


# الحصول على جميع مديري القسم (محدث للنظام الجديد)
@branch_dept_bp.route('/api/departments/<int:dept_id>/managers', methods=['GET'])
@token_required
def get_department_managers(user_id, dept_id):
    try:
        department = Department.query.get(dept_id)
        
        if not department:
            return jsonify({'message': 'القسم غير موجود'}), 404
        
        # الحصول على جميع المديرين (رؤساء ونواب)
        managers_query = db.session.query(User, UserDepartmentHead).join(
            UserDepartmentHead, User.id == UserDepartmentHead.user_id
        ).filter(UserDepartmentHead.department_id == dept_id).all()
        
        managers = []
        for user, management in managers_query:
            if user.employee:
                employee = user.employee
                job_title = None
                if employee.position:
                    job = JobTitle.query.get(employee.position)
                    if job:
                        job_title = job.title_name
                        
                branch_name = None
                if employee.branch_id:
                    branch = Branch.query.get(employee.branch_id)
                    if branch:
                        branch_name = branch.name
                
                managers.append({
                    'user_id': user.id,
                    'employee_id': employee.id,
                    'full_name': employee.full_name,
                    'role_type': management.role_type,
                    'position': job_title,
                    'salary': float(employee.salary) if employee.salary else 0,
                    'work_system': employee.work_system,
                    'branch_id': employee.branch_id,
                    'branch_name': branch_name,
                    'date_of_joining': employee.date_of_joining.isoformat() if employee.date_of_joining else None,
                    'mobile_1': employee.mobile_1,
                    'assigned_date': management.created_at.isoformat() if management.created_at else None
                })
        
        return jsonify({
            'department': {
                'id': department.id,
                'name': department.name
            },
            'managers': managers,
            'total_managers': len(managers)
        }), 200
    
    except Exception as e:
        return jsonify({'message': f'حدث خطأ أثناء جلب مديري القسم: {str(e)}'}), 500


# الحصول على رؤساء القسم فقط (للتوافق مع النظام القديم)
@branch_dept_bp.route('/api/departments/<int:dept_id>/head', methods=['GET'])
@token_required
def get_department_head(user_id, dept_id):
    try:
        department = Department.query.get(dept_id)
        
        if not department:
            return jsonify({'message': 'القسم غير موجود'}), 404
        
        # الحصول على رؤساء القسم فقط
        heads_query = db.session.query(User, UserDepartmentHead).join(
            UserDepartmentHead, User.id == UserDepartmentHead.user_id
        ).filter(
            UserDepartmentHead.department_id == dept_id,
            UserDepartmentHead.role_type == 'head'
        ).all()
        
        if not heads_query:
            return jsonify({'message': 'القسم لا يوجد له رئيس حالياً', 'head': None}), 200
        
        # إذا كان هناك أكثر من رئيس، أخذ الأول (للتوافق مع النظام القديم)
        user, management = heads_query[0]
        
        if not user.employee:
            return jsonify({'message': 'رئيس القسم ليس موظفاً', 'head': None}), 200
        
        employee = user.employee
        job_title = None
        if employee.position:
            job = JobTitle.query.get(employee.position)
            if job:
                job_title = job.title_name
                
        branch_name = None
        if employee.branch_id:
            branch = Branch.query.get(employee.branch_id)
            if branch:
                branch_name = branch.name
        
        return jsonify({
            'head': {
                'id': employee.id,
                'full_name': employee.full_name,
                'position': job_title,
                'salary': float(employee.salary) if employee.salary else 0,
                'work_system': employee.work_system,
                'branch_id': employee.branch_id,
                'branch_name': branch_name,
                'date_of_joining': employee.date_of_joining.isoformat() if employee.date_of_joining else None,
                'mobile_1': employee.mobile_1,
                'is_department_head': True,
                'role_type': 'head',
                'total_heads': len(heads_query)  # إضافة معلومة عن العدد الكلي
            }
        }), 200
    
    except Exception as e:
        return jsonify({'message': f'حدث خطأ أثناء جلب معلومات رئيس القسم: {str(e)}'}), 500



# إلغاء تعيين رئيس قسم
@branch_dept_bp.route('/api/departments/<int:dept_id>/head', methods=['DELETE'])
@token_required
def remove_department_head(user_id, dept_id):
    try:
        department = Department.query.get(dept_id)
        
        if not department:
            return jsonify({'message': 'القسم غير موجود'}), 404
        
        # البحث عن رئيس القسم الحالي
        head = department.get_department_head()
        if not head:
            return jsonify({'message': 'القسم لا يوجد له رئيس حالياً'}), 400
        
        # إلغاء تعيين المستخدم كرئيس قسم
        head.user_type = 'employee'
        head.department_id = None
        
        db.session.commit()
        
        return jsonify({
            'message': 'تم إلغاء تعيين رئيس القسم بنجاح'
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'حدث خطأ أثناء إلغاء تعيين رئيس القسم: {str(e)}'}), 500

# الحصول على معلومات رئيس قسم
@branch_dept_bp.route('/api/departments/<int:dept_id>/head', methods=['GET'])
@token_required
def get_department_head_fun(user_id, dept_id):
    try:
        department = Department.query.get(dept_id)
        
        if not department:
            return jsonify({'message': 'القسم غير موجود'}), 404
        
        head = department.get_department_head()
        if not head or not head.employee:
            return jsonify({'message': 'القسم لا يوجد له رئيس حالياً', 'head': None}), 200
        
        employee = head.employee
        job_title = None
        if employee.position:
            job = JobTitle.query.get(employee.position)
            if job:
                job_title = job.title_name
                
        branch_name = None
        if employee.branch_id:
            branch = Branch.query.get(employee.branch_id)
            if branch:
                branch_name = branch.name
        
        return jsonify({
            'head': {
                'id': employee.id,
                'full_name': employee.full_name,
                'position': job_title,
                'salary': float(employee.salary) if employee.salary else 0,
                'work_system': employee.work_system,
                'branch_id': employee.branch_id,
                'branch_name': branch_name,
                'date_of_joining': employee.date_of_joining.isoformat() if employee.date_of_joining else None,
                'mobile_1': employee.mobile_1,
                'is_department_head': True
            }
        }), 200
    
    except Exception as e:
        return jsonify({'message': f'حدث خطأ أثناء جلب معلومات رئيس القسم: {str(e)}'}), 500
    

# =========================== Employee Assignment Routes ===========================

# الحصول على موظفي قسم معين
@branch_dept_bp.route('/api/departments/<int:dept_id>/employees', methods=['GET'])
@token_required
def get_department_employees(user_id, dept_id):
    try:
        department = Department.query.get(dept_id)
        
        if not department:
            return jsonify({'message': 'القسم غير موجود'}), 404
        
        # يمكن تصفية الموظفين حسب الفرع إذا تم تقديم معرف الفرع
        branch_id = request.args.get('branch_id', type=int)
        
        if branch_id:
            employees = Employee.query.filter_by(
                department_id=dept_id, 
                branch_id=branch_id
            ).all()
        else:
            employees = department.employees.all()
        
        result = []
        for emp in employees:
            job_title = None
            if emp.position:
                job = JobTitle.query.get(emp.position)
                if job:
                    job_title = job.title_name
            
            branch_name = None
            if emp.branch_id:
                branch = Branch.query.get(emp.branch_id)
                if branch:
                    branch_name = branch.name
            
            # التحقق من أن الموظف هو رئيس القسم
            is_dept_head = emp.is_department_head()
            
            result.append({
                'id': emp.id,
                'fingerprint_id': emp.fingerprint_id,
                'full_name': emp.full_name,
                'position': job_title,
                'salary': float(emp.salary) if emp.salary else 0,
                'branch_id': emp.branch_id,
                'branch_name': branch_name,
                'is_department_head': is_dept_head,
                'date_of_joining': emp.date_of_joining.isoformat() if emp.date_of_joining else None,
                'work_system': emp.work_system
            })
        
        return jsonify(result), 200
    
    except Exception as e:
        return jsonify({'message': f'حدث خطأ أثناء جلب موظفي القسم: {str(e)}'}), 500

# الحصول على موظفي فرع معين
@branch_dept_bp.route('/api/branches/<int:branch_id>/employees', methods=['GET'])
@token_required
def get_branch_employees(user_id, branch_id):
    try:
        branch = Branch.query.get(branch_id)
        
        if not branch:
            return jsonify({'message': 'الفرع غير موجود'}), 404
        
        # يمكن تصفية الموظفين حسب القسم إذا تم تقديم معرف القسم
        department_id = request.args.get('department_id', type=int)
        
        if department_id:
            employees = Employee.query.filter_by(
                branch_id=branch_id, 
                department_id=department_id
            ).all()
        else:
            employees = branch.employees.all()
        
        result = []
        for emp in employees:
            job_title = None
            if emp.position:
                job = JobTitle.query.get(emp.position)
                if job:
                    job_title = job.title_name
            
            department_name = None
            if emp.department_id:
                dept = Department.query.get(emp.department_id)
                if dept:
                    department_name = dept.name
            
            # التحقق من أن الموظف هو رئيس القسم أو رئيس الفرع
            is_branch_head = emp.is_branch_head()
            is_dept_head = emp.is_department_head()
            
            result.append({
                'id': emp.id,
                'fingerprint_id': emp.fingerprint_id,
                'full_name': emp.full_name,
                'position': job_title,
                'salary': float(emp.salary) if emp.salary else 0,
                'department_id': emp.department_id,
                'department_name': department_name,
                'is_department_head': is_dept_head,
                'is_branch_head': is_branch_head,
                'date_of_joining': emp.date_of_joining.isoformat() if emp.date_of_joining else None,
                'work_system': emp.work_system
            })
        
        return jsonify(result), 200
    
    except Exception as e:
        return jsonify({'message': f'حدث خطأ أثناء جلب موظفي الفرع: {str(e)}'}), 500



# تحديث معلومات القسم والفرع للموظف
@branch_dept_bp.route('/api/employees/<int:emp_id>/assignment', methods=['PUT'])
@token_required
def update_employee_assignment(user_id, emp_id):
    try:
        employee = Employee.query.get(emp_id)
        
        if not employee:
            return jsonify({'message': 'الموظف غير موجود'}), 404
        
        data = request.get_json()
        print(f"Received data: {data}")
        
        # التحقق من نوع العملية - هل هي إزالة كاملة أم تعيين؟
        is_complete_removal = (
            data.get('branch_id') is None and 
            data.get('department_id') is None and
            'managed_departments' in data and data.get('managed_departments') == [] and
            'managed_branches' in data and data.get('managed_branches') == []
        )
        
        if is_complete_removal:
            print(f"Complete removal detected for employee {employee.id}")
            
            # إزالة كاملة للموظف
            if employee.has_user_account():
                user_account = employee.user_account
                username = user_account.username
                
                print(f"Deleting user account: {username}")
                
                # حذف علاقات النظام الجديد
                UserDepartmentHead.query.filter_by(user_id=user_account.id).delete()
                UserBranchHead.query.filter_by(user_id=user_account.id).delete()
                
                # حذف transaction_history
                TransactionHistory.query.filter_by(user_id=user_account.id).delete()
                
                # حذف transaction_approvals
                TransactionApproval.query.filter_by(approver_id=user_account.id).delete()
                
                # حذف المعاملات
                user_transactions = Transaction.query.filter_by(requested_by=user_account.id).all()
                for transaction in user_transactions:
                    TransactionApproval.query.filter_by(transaction_id=transaction.id).delete()
                Transaction.query.filter_by(requested_by=user_account.id).delete()
                
                # فصل الربط مع الموظف
                employee.user_account = None
                
                # حذف المستخدم
                db.session.delete(user_account)
                print(f"User account {username} deleted completely")
            
            # تنظيف الموظف
            employee.branch_id = None
            employee.department_id = None
            if hasattr(employee, 'is_manager'):
                employee.is_manager = False
            
            print(f"Employee {employee.id} completely unassigned")
            
        else:
            # التعيين العادي - معالجة branch_id و department_id
            print(f"Processing normal assignment for employee {employee.id}")
            
            # معالجة التعيين الأساسي للفرع
            if 'branch_id' in data:
                if data['branch_id'] is None:
                    employee.branch_id = None
                    print(f"Removing basic branch assignment")
                elif data['branch_id']:
                    branch = Branch.query.get(data['branch_id'])
                    if not branch:
                        return jsonify({'message': 'الفرع المحدد غير موجود'}), 400
                    employee.branch_id = data['branch_id']
                    print(f"Setting basic branch to: {data['branch_id']}")
            
            # معالجة التعيين الأساسي للقسم
            if 'department_id' in data:
                if data['department_id'] is None:
                    employee.department_id = None
                    print(f"Removing basic department assignment")
                elif data['department_id']:
                    department = Department.query.get(data['department_id'])
                    if not department:
                        return jsonify({'message': 'القسم المحدد غير موجود'}), 400
                    
                    # التحقق من توافق القسم مع الفرع
                    if employee.branch_id:
                        branch = Branch.query.get(employee.branch_id)
                        if branch and department not in branch.departments:
                            return jsonify({'message': 'القسم غير متوفر في الفرع المحدد'}), 400
                    
                    employee.department_id = data['department_id']
                    print(f"Setting basic department to: {data['department_id']}")
            
            # إنشاء حساب مستخدم إذا لم يكن موجودًا وتم تعيين فرع أو قسم
            if not employee.has_user_account() and (employee.branch_id or employee.department_id):
                print(f"Creating user account for employee {employee.id}")
                
                # إنشاء اسم مستخدم فريد مع إبقاء الفراغ كما هو
                base_username = employee.full_name.lower().strip()
                username = base_username
                counter = 1
                while User.query.filter_by(username=username).first():
                    username = f"{base_username} {counter}"
                    counter += 1
                
                # إنشاء كلمة مرور افتراضية أو من البيانات الواردة
                password = data.get('password', '123456')  # كلمة مرور افتراضية
                hashed_password = generate_password_hash(password)
                
                # تحديد نوع المستخدم
                user_type = data.get('user_type', 'employee')

                
                # إنشاء حساب المستخدم
                new_user = User(
                    username=username,
                    password=hashed_password,
                    user_type=user_type,
                    employee_id=employee.id,
                    department_id=employee.department_id,
                    branch_id=employee.branch_id
                )
                db.session.add(new_user)
                db.session.flush()  # للحصول على user_id
                print(f"Created new user account: {username} for employee {employee.id}")
            
            # معالجة الصلاحيات الإدارية إذا كان للموظف حساب مستخدم
            if employee.has_user_account():
                user_account = employee.user_account
                print(f"Processing admin privileges for user {user_account.username}")
                
                # ======================= معالجة إدارة الأقسام =======================
                if 'managed_departments' in data:
                    # إزالة جميع إدارات الأقسام الحالية
                    current_dept_managements = UserDepartmentHead.query.filter_by(user_id=user_account.id).all()
                    for management in current_dept_managements:
                        db.session.delete(management)
                        print(f"Removed department management: {management.department_id}")
                    
                    # إضافة إدارات الأقسام الجديدة
                    managed_departments = data['managed_departments']
                    if isinstance(managed_departments, list) and len(managed_departments) > 0:
                        for dept_info in managed_departments:
                            if isinstance(dept_info, dict):
                                dept_id = dept_info.get('id')
                                role_type = dept_info.get('role_type', 'head')
                            else:
                                dept_id = dept_info
                                role_type = 'head'
                            
                            if dept_id:
                                department = Department.query.get(dept_id)
                                if department:
                                    success = user_account.add_department_management(dept_id, role_type)
                                    if success:
                                        print(f"Added department management: {dept_id} as {role_type}")
                                else:
                                    return jsonify({'message': f'القسم {dept_id} غير موجود'}), 400
                
                # ======================= معالجة إدارة الفروع =======================
                if 'managed_branches' in data:
                    # إزالة جميع إدارات الفروع الحالية
                    current_branch_managements = UserBranchHead.query.filter_by(user_id=user_account.id).all()
                    for management in current_branch_managements:
                        db.session.delete(management)
                        print(f"Removed branch management: {management.branch_id}")
                    
                    # إضافة إدارات الفروع الجديدة
                    managed_branches = data['managed_branches']
                    if isinstance(managed_branches, list) and len(managed_branches) > 0:
                        for branch_info in managed_branches:
                            if isinstance(branch_info, dict):
                                branch_id = branch_info.get('id')
                                role_type = branch_info.get('role_type', 'head')
                            else:
                                branch_id = branch_info
                                role_type = 'head'
                            
                            if branch_id:
                                branch = Branch.query.get(branch_id)
                                if branch:
                                    success = user_account.add_branch_management(branch_id, role_type)
                                    if success:
                                        print(f"Added branch management: {branch_id} as {role_type}")
                                else:
                                    return jsonify({'message': f'الفرع {branch_id} غير موجود'}), 400
        
        db.session.commit()
        print(f"All changes committed successfully")
        
        # تحضير البيانات للرد
        branch_name = None
        if employee.branch_id:
            branch = Branch.query.get(employee.branch_id)
            if branch:
                branch_name = branch.name
        
        department_name = None
        if employee.department_id:
            department = Department.query.get(employee.department_id)
            if department:
                department_name = department.name
        
        # معلومات إضافية عن الصلاحيات الإدارية
        admin_info = {}
        managed_departments_details = []
        managed_branches_details = []
        
        if employee.has_user_account():
            user_account = employee.user_account
            
            # تفاصيل الأقسام المُدارة
            for dept_id in user_account.get_managed_department_ids():
                dept = Department.query.get(dept_id)
                if dept:
                    management = UserDepartmentHead.query.filter_by(
                        user_id=user_account.id,
                        department_id=dept_id
                    ).first()
                    
                    managed_departments_details.append({
                        'id': dept.id,
                        'name': dept.name,
                        'role_type': management.role_type if management else 'head'
                    })
            
            # تفاصيل الفروع المُدارة
            for branch_id in user_account.get_managed_branch_ids():
                branch = Branch.query.get(branch_id)
                if branch:
                    management = UserBranchHead.query.filter_by(
                        user_id=user_account.id,
                        branch_id=branch_id
                    ).first()
                    
                    managed_branches_details.append({
                        'id': branch.id,
                        'name': branch.name,
                        'role_type': management.role_type if management else 'head'
                    })
            
            admin_info = {
                'user_type': user_account.user_type,
                'username': user_account.username,
                'managed_departments': managed_departments_details,
                'managed_branches': managed_branches_details,
                'total_managed_departments': len(managed_departments_details),
                'total_managed_branches': len(managed_branches_details)
            }
        
        return jsonify({
            'message': 'تم تحديث معلومات تعيين الموظف وصلاحياته الإدارية بنجاح',
            'employee': {
                'id': employee.id,
                'full_name': employee.full_name,
                'branch_id': employee.branch_id,
                'branch_name': branch_name,
                'department_id': employee.department_id,
                'department_name': department_name,
                'has_user_account': employee.has_user_account(),
                'is_department_head': employee.is_department_head() if hasattr(employee, 'is_department_head') else False,
                'is_branch_head': employee.is_branch_head() if hasattr(employee, 'is_branch_head') else False
            },
            'admin_info': admin_info,
        }), 200
    
    except Exception as e:
        db.session.rollback()
        print(f"Error updating employee assignment: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'message': 'حدث خطأ أثناء تحديث معلومات تعيين الموظف',
            'error': str(e)
        }), 500
          



# الحصول على الموظفين غير المعينين (بدون أقسام أو فروع)
@branch_dept_bp.route('/api/employees/unassigned', methods=['GET'])
@token_required
def get_unassigned_employees(user_id):
    try:
        # تحديد نوع عدم التعيين (قسم أو فرع أو كلاهما)
        filter_type = request.args.get('filter', 'both')
        
        if filter_type == 'department':
            # الموظفون بدون أقسام
            employees = Employee.query.filter_by(department_id=None).all()
        elif filter_type == 'branch':
            # الموظفون بدون فروع
            employees = Employee.query.filter_by(branch_id=None).all()
        else:
            # الموظفون بدون أقسام أو فروع
            employees = Employee.query.filter(
                or_(
                    Employee.department_id == None,
                    Employee.branch_id == None
                )
            ).all()
        
        result = []
        for emp in employees:
            job_title = None
            if emp.position:
                job = JobTitle.query.get(emp.position)
                if job:
                    job_title = job.title_name
            
            branch_name = None
            if emp.branch_id:
                branch = Branch.query.get(emp.branch_id)
                if branch:
                    branch_name = branch.name
            
            department_name = None
            if emp.department_id:
                department = Department.query.get(emp.department_id)
                if department:
                    department_name = department.name
            
            result.append({
                'id': emp.id,
                'fingerprint_id': emp.fingerprint_id,
                'full_name': emp.full_name,
                'position': job_title,
                'branch_id': emp.branch_id,
                'branch_name': branch_name,
                'department_id': emp.department_id,
                'department_name': department_name,
                'date_of_joining': emp.date_of_joining.isoformat() if emp.date_of_joining else None,
                'work_system': emp.work_system
            })
        
        return jsonify(result), 200
    
    except Exception as e:
        return jsonify({'message': f'حدث خطأ أثناء جلب الموظفين غير المعينين: {str(e)}'}), 500


# تعيين موظفين متعددين لقسم
@branch_dept_bp.route('/api/departments/<int:dept_id>/employees/assign', methods=['POST'])
@token_required
def assign_employees_to_department(user_id, dept_id):
    try:
        department = Department.query.get(dept_id)
        
        if not department:
            return jsonify({'message': 'القسم غير موجود'}), 404
        
        data = request.get_json()
        
        if not data or 'employee_ids' not in data or not isinstance(data['employee_ids'], list):
            return jsonify({'message': 'معرفات الموظفين مطلوبة'}), 400
        
        employee_ids = data['employee_ids']
        branch_id = data.get('branch_id')
        
        # التحقق من وجود الفرع
        if branch_id:
            branch = Branch.query.get(branch_id)
            if not branch:
                return jsonify({'message': 'الفرع غير موجود'}), 400
            
            # التحقق من أن القسم موجود في الفرع باستخدام العلاقات
            if department not in branch.departments:
                return jsonify({'message': 'القسم غير متوفر في الفرع المحدد'}), 400
        
        assigned_employees = []
        not_found_employees = []
        
        for emp_id in employee_ids:
            employee = Employee.query.get(emp_id)
            
            if not employee:
                not_found_employees.append(emp_id)
                continue
            
            employee.department_id = dept_id
            
            if branch_id:
                employee.branch_id = branch_id
            
            assigned_employees.append({
                'id': employee.id,
                'full_name': employee.full_name
            })
        
        db.session.commit()
        
        return jsonify({
            'message': 'تم تعيين الموظفين للقسم بنجاح',
            'assigned_employees': assigned_employees,
            'not_found_employees': not_found_employees
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'حدث خطأ أثناء تعيين الموظفين للقسم: {str(e)}'}), 500
    
# تعيين موظفين متعددين لفرع
@branch_dept_bp.route('/api/branches/<int:branch_id>/employees/assign', methods=['POST'])
@token_required
def assign_employees_to_branch(user_id, branch_id):
    try:
        branch = Branch.query.get(branch_id)
        
        if not branch:
            return jsonify({'message': 'الفرع غير موجود'}), 404
        
        data = request.get_json()
        
        if not data or 'employee_ids' not in data or not isinstance(data['employee_ids'], list):
            return jsonify({'message': 'معرفات الموظفين مطلوبة'}), 400
        
        employee_ids = data['employee_ids']
        department_id = data.get('department_id')
        
        # التحقق من وجود القسم
        if department_id:
            department = Department.query.get(department_id)
            if not department:
                return jsonify({'message': 'القسم غير موجود'}), 400
            
            # التحقق من أن القسم موجود في الفرع باستخدام العلاقات
            if department not in branch.departments:
                return jsonify({'message': 'القسم غير متوفر في الفرع المحدد'}), 400
        
        assigned_employees = []
        not_found_employees = []
        
        for emp_id in employee_ids:
            employee = Employee.query.get(emp_id)
            
            if not employee:
                not_found_employees.append(emp_id)
                continue
            
            employee.branch_id = branch_id
            
            if department_id:
                employee.department_id = department_id
            
            assigned_employees.append({
                'id': employee.id,
                'full_name': employee.full_name
            })
        
        db.session.commit()
        
        return jsonify({
            'message': 'تم تعيين الموظفين للفرع بنجاح',
            'assigned_employees': assigned_employees,
            'not_found_employees': not_found_employees
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'حدث خطأ أثناء تعيين الموظفين للفرع: {str(e)}'}), 500
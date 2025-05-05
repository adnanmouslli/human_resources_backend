from flask import Blueprint, request, jsonify
from app import db
from app.utils import token_required
from app.models import Branch, Department, BranchDepartment, Employee, JobTitle

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
        
        return jsonify({
            'id': branch.id,
            'name': branch.name,
            'address': branch.address,
            'phone': branch.phone,
            'email': branch.email,
            'notes': branch.notes,
            'departments': [{'id': dept.id, 'name': dept.name} for dept in branch.departments],
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

# الحصول على جميع الأقسام
@branch_dept_bp.route('/api/departments', methods=['GET'])
@token_required
def get_all_departments(user_id):
    try:
        departments = Department.query.all()
        
        result = []
        for dept in departments:
            # الحصول على معلومات رئيس القسم
            head_info = None
            if dept.head_id:
                head = Employee.query.get(dept.head_id)
                if head:
                    head_info = {
                        'id': head.id,
                        'full_name': head.full_name
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
        head_info = None
        if department.head_id:
            head = Employee.query.get(department.head_id)
            if head:
                head_info = {
                    'id': head.id,
                    'full_name': head.full_name
                }
        
        # الحصول على معلومات الموظفين في القسم
        employees = Employee.query.filter_by(department_id=id).all()
        employee_list = [{
            'id': emp.id,
            'full_name': emp.full_name,
            'is_department_head': emp.is_department_head
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
        
        # تحديث رئيس القسم
        if 'head_id' in data:
            # إذا كان هناك رئيس قسم سابق، قم بإزالة علامة رئيس القسم عنه
            if department.head_id:
                old_head = Employee.query.get(department.head_id)
                if old_head:
                    old_head.is_department_head = False
            
            # تعيين رئيس قسم جديد
            if data['head_id']:
                new_head = Employee.query.get(data['head_id'])
                if new_head:
                    new_head.is_department_head = True
                    new_head.department_id = id
                    department.head_id = new_head.id
                else:
                    return jsonify({'message': 'الموظف المحدد غير موجود'}), 400
            else:
                department.head_id = None
        
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
        has_employees = Employee.query.filter_by(department_id=id).first()
        if has_employees:
            return jsonify({
                'status': 400,
                'message': 'لا يمكن حذف القسم لوجود موظفين مرتبطين به'
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

# ==================== Branch-Department Relations Routes ====================

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
        
        db.session.delete(link)
        db.session.commit()
        
        return jsonify({
            'message': 'تم إلغاء ربط القسم بالفرع بنجاح'
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'حدث خطأ أثناء إلغاء ربط القسم بالفرع: {str(e)}'}), 500

# ==================== Employee Department Assignment Routes ====================

# تعيين موظف كرئيس قسم
@branch_dept_bp.route('/api/departments/<int:dept_id>/head/<int:emp_id>', methods=['POST'])
@token_required
def assign_department_head(user_id, dept_id, emp_id):
    try:
        department = Department.query.get(dept_id)
        employee = Employee.query.get(emp_id)
        
        if not department:
            return jsonify({'message': 'القسم غير موجود'}), 404
        if not employee:
            return jsonify({'message': 'الموظف غير موجود'}), 404
        
        # التحقق من عدم وجود رئيس آخر للقسم
        if department.head_id and department.head_id != emp_id:
            current_head = Employee.query.get(department.head_id)
            if current_head:
                current_head.is_department_head = False
        
        # تحقق مما إذا كان القسم هو قسم الموظف الحالي
        if employee.department_id != dept_id:
            # إذا كان الموظف منتمي لقسم آخر، قم بتغيير انتماءه للقسم الجديد
            employee.department_id = dept_id
        
        # تعيين الموظف كرئيس للقسم
        employee.is_department_head = True
        department.head_id = emp_id
        
        # تحقق مما إذا كان الموظف مرتبط بالفعل بأحد فروع القسم
        if employee.branch_id:
            # تأكد من أن الفرع متصل بالقسم
            branch_dept = BranchDepartment.query.filter_by(
                branch_id=employee.branch_id, department_id=dept_id
            ).first()
            
            if not branch_dept:
                # إذا كان الفرع غير مرتبط بالقسم، قم بربطهما
                branch = Branch.query.get(employee.branch_id)
                if branch:
                    department.branches.append(branch)
        
        db.session.commit()
        
        return jsonify({
            'message': 'تم تعيين الموظف كرئيس للقسم بنجاح',
            'department': department.name,
            'head': employee.full_name
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'حدث خطأ أثناء تعيين رئيس القسم: {str(e)}'}), 500
    
# =============================== إدارة رؤساء الأقسام ===============================

# إلغاء تعيين رئيس قسم
@branch_dept_bp.route('/api/departments/<int:dept_id>/head', methods=['DELETE'])
@token_required
def remove_department_head(user_id, dept_id):
    try:
        department = Department.query.get(dept_id)
        
        if not department:
            return jsonify({'message': 'القسم غير موجود'}), 404
        
        if not department.head_id:
            return jsonify({'message': 'القسم لا يوجد له رئيس حالياً'}), 400
        
        # إلغاء تعيين الموظف كرئيس قسم
        head = Employee.query.get(department.head_id)
        if head:
            head.is_department_head = False
        
        department.head_id = None
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
def get_department_head(user_id, dept_id):
    try:
        department = Department.query.get(dept_id)
        
        if not department:
            return jsonify({'message': 'القسم غير موجود'}), 404
        
        if not department.head_id:
            return jsonify({'message': 'القسم لا يوجد له رئيس حالياً', 'head': None}), 200
        
        head = Employee.query.get(department.head_id)
        if not head:
            return jsonify({'message': 'معلومات رئيس القسم غير متوفرة', 'head': None}), 200
        
        job_title = None
        if head.position:
            job = JobTitle.query.get(head.position)
            if job:
                job_title = job.title_name
                
        branch_name = None
        if head.branch_id:
            branch = Branch.query.get(head.branch_id)
            if branch:
                branch_name = branch.name
        
        return jsonify({
            'head': {
                'id': head.id,
                'full_name': head.full_name,
                'position': job_title,
                'salary': float(head.salary) if head.salary else 0,
                'work_system': head.work_system,
                'branch_id': head.branch_id,
                'branch_name': branch_name,
                'date_of_joining': head.date_of_joining.isoformat() if head.date_of_joining else None,
                'mobile_1': head.mobile_1,
                'is_department_head': head.is_department_head
            }
        }), 200
    
    except Exception as e:
        return jsonify({'message': f'حدث خطأ أثناء جلب معلومات رئيس القسم: {str(e)}'}), 500


# =============================== العلاقات بين الفروع والأقسام ===============================

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
            head_info = None
            if dept.head_id:
                head = Employee.query.get(dept.head_id)
                if head:
                    head_info = {
                        'id': head.id,
                        'full_name': head.full_name
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


# =============================== إدارة الموظفين مع الفروع والأقسام ===============================

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
            employees = Employee.query.filter_by(department_id=dept_id).all()
        
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
            
            result.append({
                'id': emp.id,
                'fingerprint_id': emp.fingerprint_id,
                'full_name': emp.full_name,
                'position': job_title,
                'salary': float(emp.salary) if emp.salary else 0,
                'branch_id': emp.branch_id,
                'branch_name': branch_name,
                'is_department_head': emp.is_department_head,
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
            employees = Employee.query.filter_by(branch_id=branch_id).all()
        
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
            
            result.append({
                'id': emp.id,
                'fingerprint_id': emp.fingerprint_id,
                'full_name': emp.full_name,
                'position': job_title,
                'salary': float(emp.salary) if emp.salary else 0,
                'department_id': emp.department_id,
                'department_name': department_name,
                'is_department_head': emp.is_department_head,
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
        
        old_department_id = employee.department_id
        old_is_department_head = employee.is_department_head
        
        # تحديث معلومات الفرع
        if 'branch_id' in data:
            if data['branch_id']:
                branch = Branch.query.get(data['branch_id'])
                if not branch:
                    return jsonify({'message': 'الفرع غير موجود'}), 400
                employee.branch_id = data['branch_id']
            else:
                employee.branch_id = None
        
        # تحديث معلومات القسم
        if 'department_id' in data:
            if data['department_id']:
                department = Department.query.get(data['department_id'])
                if not department:
                    return jsonify({'message': 'القسم غير موجود'}), 400
                
                # التحقق من أن القسم موجود في الفرع المحدد
                branch_id = data.get('branch_id', employee.branch_id)
                if branch_id:
                    branch_dept = BranchDepartment.query.filter_by(
                        branch_id=branch_id, department_id=data['department_id']
                    ).first()
                    if not branch_dept:
                        return jsonify({'message': 'القسم غير متوفر في الفرع المحدد'}), 400
                
                employee.department_id = data['department_id']
            else:
                # إذا تم إزالة القسم وكان الموظف رئيس القسم، قم بإزالة علامة رئيس القسم
                if employee.is_department_head:
                    employee.is_department_head = False
                    
                    # تحديث جدول الأقسام
                    if old_department_id:
                        department = Department.query.get(old_department_id)
                        if department and department.head_id == emp_id:
                            department.head_id = None
                
                employee.department_id = None
        
        # تحديث صفة رئيس القسم
        if 'is_department_head' in data:
            is_department_head = data['is_department_head']
            
            # إذا تم تعيين الموظف كرئيس قسم
            if is_department_head and not employee.is_department_head:
                # التحقق من وجود قسم مرتبط
                department_id = data.get('department_id', employee.department_id)
                if not department_id:
                    return jsonify({'message': 'لا يمكن تعيين الموظف كرئيس قسم بدون تحديد القسم'}), 400
                
                # التحقق من عدم وجود رئيس قسم آخر للقسم المحدد
                existing_head = Employee.query.filter_by(
                    department_id=department_id, is_department_head=True
                ).filter(Employee.id != emp_id).first()
                
                if existing_head:
                    return jsonify({'message': f'يوجد رئيس قسم آخر بالفعل لهذا القسم: {existing_head.full_name}'}), 400
                
                employee.is_department_head = True
                
                # تحديث جدول الأقسام
                department = Department.query.get(department_id)
                department.head_id = emp_id
            
            # إذا تمت إزالة صفة رئيس القسم
            elif not is_department_head and employee.is_department_head:
                employee.is_department_head = False
                
                # تحديث جدول الأقسام
                if old_department_id:
                    department = Department.query.get(old_department_id)
                    if department and department.head_id == emp_id:
                        department.head_id = None
        
        db.session.commit()
        
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
        
        return jsonify({
            'message': 'تم تحديث معلومات تعيين الموظف بنجاح',
            'employee': {
                'id': employee.id,
                'full_name': employee.full_name,
                'branch_id': employee.branch_id,
                'branch_name': branch_name,
                'department_id': employee.department_id,
                'department_name': department_name,
                'is_department_head': employee.is_department_head
            }
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'حدث خطأ أثناء تحديث معلومات تعيين الموظف: {str(e)}'}), 500

# الحصول على الموظفين غير المعينين (بدون أقسام أو فروع)
@branch_dept_bp.route('/api/employees/unassigned', methods=['GET'])
@token_required
def get_unassigned_employees(user_id):
    try:
        # تحديد نوع عدم التعيين (قسم أو فرع أو كلاهما)
        filter_type = request.args.get('filter', 'both')
        
        if filter_type == 'department':
            # الموظفون بدون أقسام
            employees = Employee.query.filter(Employee.department_id == None).all()
        elif filter_type == 'branch':
            # الموظفون بدون فروع
            employees = Employee.query.filter(Employee.branch_id == None).all()
        else:
            # الموظفون بدون أقسام أو فروع
            employees = Employee.query.filter(
                db.or_(
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
            
            # التحقق من أن القسم موجود في الفرع
            branch_dept = BranchDepartment.query.filter_by(
                branch_id=branch_id, department_id=dept_id
            ).first()
            if not branch_dept:
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
            
            # التحقق من أن القسم موجود في الفرع
            branch_dept = BranchDepartment.query.filter_by(
                branch_id=branch_id, department_id=department_id
            ).first()
            if not branch_dept:
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
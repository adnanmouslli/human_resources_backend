import os
from datetime import datetime
from flask import Blueprint, current_app, request, jsonify, send_file
from werkzeug.utils import secure_filename

from app import db
from app.models import Employee, EmployeeSalaryComponent, EmployeeCustomDate, EmployeeAttachment
from app.utils import token_required


employee_extras_bp = Blueprint('employee_extras', __name__)

ALLOWED_ATTACHMENT_EXT = {'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx', 'xlsx', 'xls', 'txt', 'zip', 'rar'}


def _allowed_attachment(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_ATTACHMENT_EXT


def _parse_date(value):
    if not value:
        return None
    if hasattr(value, 'date'):
        return value.date() if callable(getattr(value, 'date', None)) else value
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%fZ'):
        try:
            return datetime.strptime(str(value), fmt).date()
        except ValueError:
            continue
    return None


def _ensure_employee_accessible(user, employee_id):
    """تحقق من أن الموظف موجود ومسموح للمستخدم الوصول إليه (يشمل غير المفعلين للتعديل)."""
    employee = Employee.query.get(employee_id)
    if not employee:
        return None, (jsonify({'message': 'الموظف غير موجود'}), 404)

    if user.is_super_admin():
        return employee, None

    accessible_ids = {e.id for e in user.get_accessible_employees(include_inactive=True)}
    if employee.id not in accessible_ids:
        return None, (jsonify({'message': 'ليس لديك صلاحية الوصول لهذا الموظف'}), 403)
    return employee, None


# ============================================================================
# 1) تفعيل / إلغاء تفعيل الموظف
# ============================================================================

@employee_extras_bp.route('/api/employees/<int:employee_id>/toggle-active', methods=['PUT'])
@token_required
def toggle_employee_active(user, employee_id):
    """تبديل حالة تفعيل الموظف (soft delete/restore)"""
    employee, err = _ensure_employee_accessible(user, employee_id)
    if err:
        return err

    data = request.get_json(silent=True) or {}
    if 'is_active' in data:
        new_state = bool(data['is_active'])
    else:
        new_state = not employee.is_active

    employee.is_active = new_state
    employee.deactivated_at = None if new_state else datetime.now()

    # إذا تم إلغاء التفعيل وللموظف حساب مستخدم، أوقف الحساب أيضاً
    if not new_state and employee.user_account:
        employee.user_account.is_active = False

    db.session.commit()

    return jsonify({
        'message': 'تم تفعيل الموظف' if new_state else 'تم إلغاء تفعيل الموظف',
        'employee': {
            'id': employee.id,
            'full_name': employee.full_name,
            'is_active': employee.is_active,
            'deactivated_at': employee.deactivated_at.isoformat() if employee.deactivated_at else None,
        }
    }), 200


@employee_extras_bp.route('/api/employees/all-including-inactive', methods=['GET'])
@token_required
def list_employees_with_inactive(user):
    """عرض جميع الموظفين (مفعلين وغير مفعلين) لشاشة إدارة الموظفين."""
    employees = user.get_accessible_employees(include_inactive=True)
    return jsonify([{
        'id': e.id,
        'full_name': e.full_name,
        'fingerprint_id': e.fingerprint_id,
        'is_active': e.is_active,
        'deactivated_at': e.deactivated_at.isoformat() if e.deactivated_at else None,
        'branch_id': e.branch_id,
        'department_id': e.department_id,
    } for e in employees]), 200


# ============================================================================
# 2) Salary Components (إضافات وخصومات ديناميكية على الراتب)
# ============================================================================

@employee_extras_bp.route('/api/employees/<int:employee_id>/salary-components', methods=['GET'])
@token_required
def list_salary_components(user, employee_id):
    employee, err = _ensure_employee_accessible(user, employee_id)
    if err:
        return err

    component_type = request.args.get('type')
    query = EmployeeSalaryComponent.query.filter_by(employee_id=employee.id)
    if component_type in ('addition', 'deduction'):
        query = query.filter_by(component_type=component_type)

    components = query.order_by(EmployeeSalaryComponent.created_at.asc()).all()
    return jsonify([c.to_dict() for c in components]), 200


@employee_extras_bp.route('/api/employees/<int:employee_id>/salary-components', methods=['POST'])
@token_required
def create_salary_component(user, employee_id):
    employee, err = _ensure_employee_accessible(user, employee_id)
    if err:
        return err

    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    component_type = (data.get('component_type') or '').strip()
    try:
        amount = float(data.get('amount') or 0)
    except (ValueError, TypeError):
        return jsonify({'message': 'قيمة غير صالحة'}), 400

    if not name:
        return jsonify({'message': 'الاسم مطلوب'}), 400
    if component_type not in ('addition', 'deduction'):
        return jsonify({'message': 'component_type يجب أن يكون addition أو deduction'}), 400
    if amount < 0:
        return jsonify({'message': 'القيمة يجب أن تكون >= 0'}), 400

    component = EmployeeSalaryComponent(
        employee_id=employee.id,
        name=name,
        amount=amount,
        component_type=component_type,
        is_active=bool(data.get('is_active', True)),
        notes=(data.get('notes') or None),
    )
    db.session.add(component)
    db.session.commit()
    return jsonify(component.to_dict()), 201


@employee_extras_bp.route('/api/salary-components/<int:component_id>', methods=['PUT'])
@token_required
def update_salary_component(user, component_id):
    component = EmployeeSalaryComponent.query.get(component_id)
    if not component:
        return jsonify({'message': 'المكون غير موجود'}), 404

    _, err = _ensure_employee_accessible(user, component.employee_id)
    if err:
        return err

    data = request.get_json(silent=True) or {}

    if 'name' in data:
        name = (data['name'] or '').strip()
        if not name:
            return jsonify({'message': 'الاسم مطلوب'}), 400
        component.name = name

    if 'amount' in data:
        try:
            amount = float(data['amount'])
        except (ValueError, TypeError):
            return jsonify({'message': 'قيمة غير صالحة'}), 400
        if amount < 0:
            return jsonify({'message': 'القيمة يجب أن تكون >= 0'}), 400
        component.amount = amount

    if 'component_type' in data:
        if data['component_type'] not in ('addition', 'deduction'):
            return jsonify({'message': 'component_type غير صالح'}), 400
        component.component_type = data['component_type']

    if 'is_active' in data:
        component.is_active = bool(data['is_active'])

    if 'notes' in data:
        component.notes = data['notes'] or None

    db.session.commit()
    return jsonify(component.to_dict()), 200


@employee_extras_bp.route('/api/salary-components/<int:component_id>', methods=['DELETE'])
@token_required
def delete_salary_component(user, component_id):
    component = EmployeeSalaryComponent.query.get(component_id)
    if not component:
        return jsonify({'message': 'المكون غير موجود'}), 404

    _, err = _ensure_employee_accessible(user, component.employee_id)
    if err:
        return err

    db.session.delete(component)
    db.session.commit()
    return jsonify({'message': 'تم الحذف'}), 200


# ============================================================================
# 3) Custom Dates (تواريخ ديناميكية)
# ============================================================================

@employee_extras_bp.route('/api/employees/<int:employee_id>/custom-dates', methods=['GET'])
@token_required
def list_custom_dates(user, employee_id):
    employee, err = _ensure_employee_accessible(user, employee_id)
    if err:
        return err
    dates = EmployeeCustomDate.query.filter_by(employee_id=employee.id)\
        .order_by(EmployeeCustomDate.date_value.asc()).all()
    return jsonify([d.to_dict() for d in dates]), 200


@employee_extras_bp.route('/api/employees/<int:employee_id>/custom-dates', methods=['POST'])
@token_required
def create_custom_date(user, employee_id):
    employee, err = _ensure_employee_accessible(user, employee_id)
    if err:
        return err

    data = request.get_json(silent=True) or {}
    label = (data.get('label') or '').strip()
    date_value = _parse_date(data.get('date_value'))

    if not label:
        return jsonify({'message': 'التسمية مطلوبة'}), 400
    if not date_value:
        return jsonify({'message': 'التاريخ مطلوب وبصيغة صحيحة'}), 400

    custom_date = EmployeeCustomDate(
        employee_id=employee.id,
        label=label,
        date_value=date_value,
        notes=(data.get('notes') or None),
    )
    db.session.add(custom_date)
    db.session.commit()
    return jsonify(custom_date.to_dict()), 201


@employee_extras_bp.route('/api/custom-dates/<int:date_id>', methods=['PUT'])
@token_required
def update_custom_date(user, date_id):
    custom_date = EmployeeCustomDate.query.get(date_id)
    if not custom_date:
        return jsonify({'message': 'التاريخ غير موجود'}), 404

    _, err = _ensure_employee_accessible(user, custom_date.employee_id)
    if err:
        return err

    data = request.get_json(silent=True) or {}
    if 'label' in data:
        label = (data['label'] or '').strip()
        if not label:
            return jsonify({'message': 'التسمية مطلوبة'}), 400
        custom_date.label = label

    if 'date_value' in data:
        parsed = _parse_date(data['date_value'])
        if not parsed:
            return jsonify({'message': 'تاريخ غير صالح'}), 400
        custom_date.date_value = parsed

    if 'notes' in data:
        custom_date.notes = data['notes'] or None

    db.session.commit()
    return jsonify(custom_date.to_dict()), 200


@employee_extras_bp.route('/api/custom-dates/<int:date_id>', methods=['DELETE'])
@token_required
def delete_custom_date(user, date_id):
    custom_date = EmployeeCustomDate.query.get(date_id)
    if not custom_date:
        return jsonify({'message': 'التاريخ غير موجود'}), 404

    _, err = _ensure_employee_accessible(user, custom_date.employee_id)
    if err:
        return err

    db.session.delete(custom_date)
    db.session.commit()
    return jsonify({'message': 'تم الحذف'}), 200


# ============================================================================
# 4) Attachments (مرفقات ديناميكية)
# ============================================================================

def _attachments_folder():
    folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'employee_attachments')
    if not os.path.exists(folder):
        os.makedirs(folder)
    return folder


@employee_extras_bp.route('/api/employees/<int:employee_id>/attachments', methods=['GET'])
@token_required
def list_attachments(user, employee_id):
    employee, err = _ensure_employee_accessible(user, employee_id)
    if err:
        return err
    attachments = EmployeeAttachment.query.filter_by(employee_id=employee.id)\
        .order_by(EmployeeAttachment.created_at.desc()).all()
    return jsonify([a.to_dict() for a in attachments]), 200


@employee_extras_bp.route('/api/employees/<int:employee_id>/attachments', methods=['POST'])
@token_required
def upload_attachment(user, employee_id):
    employee, err = _ensure_employee_accessible(user, employee_id)
    if err:
        return err

    if 'file' not in request.files:
        return jsonify({'message': 'لم يتم إرفاق ملف'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'message': 'لم يتم اختيار ملف'}), 400
    if not _allowed_attachment(file.filename):
        return jsonify({'message': 'نوع الملف غير مسموح'}), 400

    label = (request.form.get('label') or '').strip()
    if not label:
        return jsonify({'message': 'التسمية مطلوبة'}), 400

    original = secure_filename(file.filename)
    ext = original.rsplit('.', 1)[1].lower() if '.' in original else ''
    unique_name = f"emp{employee.id}_{int(datetime.now().timestamp() * 1000)}_{original}"

    folder = _attachments_folder()
    full_path = os.path.join(folder, unique_name)
    file.save(full_path)

    file_size = os.path.getsize(full_path)
    relative_path = f"/uploads/employee_attachments/{unique_name}"

    attachment = EmployeeAttachment(
        employee_id=employee.id,
        label=label,
        file_path=relative_path,
        original_filename=original,
        file_type=ext or None,
        file_size=file_size,
        notes=(request.form.get('notes') or None),
    )
    db.session.add(attachment)
    db.session.commit()
    return jsonify(attachment.to_dict()), 201


@employee_extras_bp.route('/api/attachments/<int:attachment_id>', methods=['PUT'])
@token_required
def update_attachment(user, attachment_id):
    """تعديل التسمية أو الملاحظات فقط (لا يتم استبدال الملف هنا)."""
    attachment = EmployeeAttachment.query.get(attachment_id)
    if not attachment:
        return jsonify({'message': 'المرفق غير موجود'}), 404

    _, err = _ensure_employee_accessible(user, attachment.employee_id)
    if err:
        return err

    data = request.get_json(silent=True) or {}
    if 'label' in data:
        label = (data['label'] or '').strip()
        if not label:
            return jsonify({'message': 'التسمية مطلوبة'}), 400
        attachment.label = label
    if 'notes' in data:
        attachment.notes = data['notes'] or None

    db.session.commit()
    return jsonify(attachment.to_dict()), 200


@employee_extras_bp.route('/api/attachments/<int:attachment_id>', methods=['DELETE'])
@token_required
def delete_attachment(user, attachment_id):
    attachment = EmployeeAttachment.query.get(attachment_id)
    if not attachment:
        return jsonify({'message': 'المرفق غير موجود'}), 404

    _, err = _ensure_employee_accessible(user, attachment.employee_id)
    if err:
        return err

    try:
        if attachment.file_path and attachment.file_path.startswith('/uploads/'):
            relative = attachment.file_path.replace('/uploads/', '', 1)
            disk_path = os.path.join(current_app.config['UPLOAD_FOLDER'], relative)
            if os.path.exists(disk_path):
                os.remove(disk_path)
    except Exception as e:
        print(f"Warning: could not delete file on disk: {e}")

    db.session.delete(attachment)
    db.session.commit()
    return jsonify({'message': 'تم الحذف'}), 200


@employee_extras_bp.route('/api/attachments/<int:attachment_id>/download', methods=['GET'])
@token_required
def download_attachment(user, attachment_id):
    attachment = EmployeeAttachment.query.get(attachment_id)
    if not attachment:
        return jsonify({'message': 'المرفق غير موجود'}), 404

    _, err = _ensure_employee_accessible(user, attachment.employee_id)
    if err:
        return err

    relative = attachment.file_path.replace('/uploads/', '', 1) if attachment.file_path.startswith('/uploads/') else attachment.file_path
    disk_path = os.path.join(current_app.config['UPLOAD_FOLDER'], relative)
    if not os.path.exists(disk_path):
        return jsonify({'message': 'الملف غير موجود على القرص'}), 404

    return send_file(
        disk_path,
        as_attachment=True,
        download_name=attachment.original_filename or os.path.basename(disk_path)
    )

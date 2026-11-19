from flask import Blueprint, request, jsonify
from app.controllers.shift_controller import ShiftController
from app.controllers.shift_exception_controller import ShiftExceptionController
from app.models.employee import Employee
from app.models.user import User
from app.services.shift_access_service import evaluate_shift_access, evaluate_user_app_access
from app.utils import token_required

shift_bp = Blueprint('shift', __name__)


@shift_bp.route('/api/shifts/me/shift-access', methods=['GET'])
@token_required
def get_my_shift_access(user):
    """هل يُسمح للمستخدم الحالي باستخدام التطبيق الآن حسب ورديته؟"""
    status = evaluate_user_app_access(user)
    return jsonify(status), 200


@shift_bp.route('/api/shifts/employees/<int:employee_id>/shift-access', methods=['GET'])
@token_required
def get_employee_shift_access(user, employee_id):
    """حالة وصول موظف للوردية (للموظف نفسه أو مدير بصلاحية)."""
    current_user = User.query.get(user.id) if not isinstance(user, User) else user
    employee = Employee.query.get(employee_id)
    if not employee:
        return jsonify({'message': 'الموظف غير موجود'}), 404

    # الموظف نفسه — نمرّر المستخدم لتطبيق إعداد القفل
    if current_user.employee_id == employee_id:
        return jsonify(evaluate_shift_access(employee, user=current_user)), 200

    # للمدراء: نقيّم حسب إعداد حساب الموظف المرتبط إن وُجد
    target_user = User.query.filter_by(employee_id=employee_id).first()

    # مدير عام
    if current_user.is_super_admin():
        return jsonify(evaluate_shift_access(employee, user=target_user)), 200

    # مدير ضمن نطاقه
    if hasattr(current_user, 'get_accessible_employees'):
        accessible_ids = {e.id for e in current_user.get_accessible_employees()}
        if employee_id in accessible_ids:
            return jsonify(evaluate_shift_access(employee, user=target_user)), 200

    return jsonify({'message': 'ليس لديك صلاحية لعرض حالة هذا الموظف'}), 403


@shift_bp.route('/api/shifts', methods=['POST'])
@token_required
def create_shift(user_id):
    data = request.get_json()
    response, status_code = ShiftController.create_shift(data)
    return jsonify(response), status_code

@shift_bp.route('/api/shifts', methods=['GET'])
@token_required
def get_all_shifts(user_id):
    response, status_code = ShiftController.get_all_shifts()
    return jsonify(response), status_code

@shift_bp.route('/api/shifts/<int:id>', methods=['GET'])
@token_required
def get_shift(user_id, id):
    response, status_code = ShiftController.get_shift_by_id(id)
    return jsonify(response), status_code

@shift_bp.route('/api/shifts/<int:id>', methods=['PUT'])
@token_required
def update_shift(user_id, id):
    data = request.get_json()
    response, status_code = ShiftController.update_shift(id, data)
    return jsonify(response), status_code

@shift_bp.route('/api/shifts/<int:id>', methods=['DELETE'])
@token_required
def delete_shift(user_id, id):
    response, status_code = ShiftController.delete_shift(id)
    return jsonify(response), status_code


# ——— استثناءات الوردية ———

@shift_bp.route('/api/shifts/exceptions', methods=['GET'])
@token_required
def list_shift_exceptions(user):
    filters = {
        'shift_id': request.args.get('shift_id'),
        'punch_type': request.args.get('punch_type'),
        'exception_date': request.args.get('exception_date'),
        'date_from': request.args.get('date_from'),
        'date_to': request.args.get('date_to'),
    }
    response, status_code = ShiftExceptionController.list_exceptions(filters)
    return jsonify(response), status_code


@shift_bp.route('/api/shifts/exceptions/<int:exception_id>', methods=['GET'])
@token_required
def get_shift_exception(user, exception_id):
    response, status_code = ShiftExceptionController.get_by_id(exception_id)
    return jsonify(response), status_code


@shift_bp.route('/api/shifts/exceptions', methods=['POST'])
@token_required
def create_shift_exception(user):
    data = request.get_json() or {}
    response, status_code = ShiftExceptionController.create(data, user_id=getattr(user, 'id', None))
    return jsonify(response), status_code


@shift_bp.route('/api/shifts/exceptions/<int:exception_id>', methods=['PUT'])
@token_required
def update_shift_exception(user, exception_id):
    data = request.get_json() or {}
    response, status_code = ShiftExceptionController.update(exception_id, data)
    return jsonify(response), status_code


@shift_bp.route('/api/shifts/exceptions/<int:exception_id>', methods=['DELETE'])
@token_required
def delete_shift_exception(user, exception_id):
    response, status_code = ShiftExceptionController.delete(exception_id)
    return jsonify(response), status_code
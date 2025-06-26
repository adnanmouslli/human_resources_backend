from flask import Blueprint, request, jsonify
from app.controllers.absence_transaction_controller import AbsenceTransactionController
from datetime import datetime, date, timedelta

# إنشاء Blueprint للروات الخاصة بالغياب
absence_transaction_bp = Blueprint('absence_transaction', __name__)

# روت لإنشاء معاملة غياب جديدة
@absence_transaction_bp.route('/api/absence-transactions', methods=['POST'])
def create_absence_transaction():
    data = request.get_json()
    
    employee_id = data.get('employee_id')
    absence_date = data.get('absence_date')  # يجب أن تكون بصيغة "YYYY-MM-DD"
    shift_id = data.get('shift_id')
    created_by = data.get('created_by')

    # تحويل absence_date من سلسلة إلى كائن تاريخ
    try:
        absence_date = datetime.fromisoformat(absence_date).date()
    except ValueError:
        return jsonify({'message': 'صيغة التاريخ غير صحيحة. يجب أن تكون YYYY-MM-DD'}), 400

    result, status = AbsenceTransactionController.create_absence_transaction(
        employee_id=employee_id,
        absence_date=absence_date,
        shift_id=shift_id,
        created_by=created_by
    )
    
    return jsonify(result), status

# روت لجلب المعاملات المعلقة للمستخدم مع إنشاء معاملات الغياب التلقائية
@absence_transaction_bp.route('/api/absence-transactions/pending/<int:user_id>', methods=['GET'])
def get_pending_transactions(user_id):
    """
    جلب المعاملات المعلقة مع إنشاء معاملات غياب تلقائية للشهر الماضي
    """
    result, status = AbsenceTransactionController.get_pending_transactions_for_user(user_id)
    return jsonify(result), status

# روت للموافقة على معاملة
@absence_transaction_bp.route('/api/absence-transactions/approve/<int:transaction_id>', methods=['PUT'])
def approve_transaction(transaction_id):
    data = request.get_json()
    user_id = data.get('user_id')
    is_notified = data.get('is_notified', False)
    is_paid = data.get('is_paid', False)
    manager_notes = data.get('manager_notes')

    result, status = AbsenceTransactionController.approve_transaction(
        transaction_id=transaction_id,
        user_id=user_id,
        is_notified=is_notified,
        is_paid=is_paid,
        manager_notes=manager_notes
    )
    
    return jsonify(result), status

# روت لرفض معاملة
@absence_transaction_bp.route('/api/absence-transactions/reject/<int:transaction_id>', methods=['PUT'])
def reject_transaction(transaction_id):
    data = request.get_json()
    user_id = data.get('user_id')
    manager_notes = data.get('manager_notes')

    result, status = AbsenceTransactionController.reject_transaction(
        transaction_id=transaction_id,
        user_id=user_id,
        manager_notes=manager_notes
    )
    
    return jsonify(result), status

# روت لجلب معاملات الغياب المعتمدة
@absence_transaction_bp.route('/api/absence-transactions/approved', methods=['GET'])
def get_approved_absence_transactions():
    """
    استرجاع جميع معاملات الغياب المعتمدة مع اسم الموظف، تاريخ الغياب، والأسئلة مع إجاباتها
    يمكن تمرير absence_date كمعامل استعلام لتصفية النتائج
    """
    absence_date = request.args.get('absence_date')  # الحصول على absence_date من معاملات الاستعلام
    result, status = AbsenceTransactionController.get_approved_absence_transactions(absence_date)
    return jsonify(result), status
# routes/transaction_routes.py

from flask import Blueprint, request, jsonify
from app import db
from app.utils import token_required
from app.models.transaction import Transaction, TransactionApproval
from app.models.user import User
from app.models.employee import Employee
from datetime import datetime, date
import json

transaction_bp = Blueprint('transaction', __name__)

# =========================== إنشاء معاملة جديدة ===========================

@transaction_bp.route('/api/transactions', methods=['POST'])
@token_required
def create_transaction(user):
    try:
        data = request.get_json()
        
        # التحقق من البيانات المطلوبة
        required_fields = ['transaction_type', 'employee_id']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'message': f'الحقل {field} مطلوب'}), 400
        
        # التحقق من صحة نوع المعاملة
        valid_types = ['advance', 'reward', 'penalty', 'hourly_leave', 'daily_leave']
        if data['transaction_type'] not in valid_types:
            return jsonify({'message': 'نوع المعاملة غير صالح'}), 400
        
        # التحقق من وجود الموظف
        employee = Employee.query.get(data['employee_id'])
        if not employee:
            return jsonify({'message': 'الموظف غير موجود'}), 404
        
        # التحقق من صلاحية المستخدم لإنشاء معاملة لهذا الموظف
        current_user = User.query.get(user.id)
        if not current_user:
            return jsonify({'message': 'المستخدم غير موجود'}), 404
        
        # السوبر أدمن يمكنه إنشاء معاملات لأي موظف
        if not current_user.is_super_admin():
            # التحقق من الصلاحيات حسب الهيكل التنظيمي
            can_create = False
            
            # رئيس الفرع أو نائبه
            if (current_user.is_branch_head() or current_user.is_branch_deputy()) and current_user.branch_id == employee.branch_id:
                can_create = True
            
            # رئيس القسم أو نائبه
            elif (current_user.is_department_head() or current_user.is_department_deputy()) and current_user.department_id == employee.department_id:
                can_create = True
            
            # الموظف نفسه (في حالات معينة)
            elif current_user.employee_id == employee.id and data['transaction_type'] in ['hourly_leave', 'daily_leave' ,'advance']:
                can_create = True
            
            if not can_create:
                return jsonify({'message': 'ليس لديك صلاحية إنشاء معاملة لهذا الموظف'}), 403
        
        # إنشاء المعاملة
        transaction = Transaction(
            transaction_type=data['transaction_type'],
            employee_id=data['employee_id'],
            requested_by=user.id,
            notes=data.get('notes')
        )
        
        # توليد رقم المعاملة
        transaction.transaction_number = transaction.generate_transaction_number()
        
        # تعيين التفاصيل حسب نوع المعاملة
        details = {}
        
        if data['transaction_type'] == 'advance':
            required_advance_fields = ['amount', 'document_number']
            for field in required_advance_fields:
                if not data.get(field):
                    return jsonify({'message': f'الحقل {field} مطلوب للسلفة'}), 400
            
            details = {
                'amount': float(data['amount']),
                'document_number': data['document_number'],
                'date': data.get('date', str(date.today())),
                'notes': data.get('notes')
            }
        
        elif data['transaction_type'] == 'reward':
            required_reward_fields = ['amount', 'document_number']
            for field in required_reward_fields:
                if not data.get(field):
                    return jsonify({'message': f'الحقل {field} مطلوب للمكافأة'}), 400
            
            details = {
                'amount': float(data['amount']),
                'document_number': data['document_number'],
                'date': data.get('date', str(date.today())),
                'notes': data.get('notes')
            }
        
        elif data['transaction_type'] == 'penalty':
            required_penalty_fields = ['amount', 'document_number']
            for field in required_penalty_fields:
                if not data.get(field):
                    return jsonify({'message': f'الحقل {field} مطلوب للجزاء'}), 400
            
            details = {
                'amount': float(data['amount']),
                'document_number': data['document_number'],
                'date': data.get('date', str(date.today())),
                'notes': data.get('notes')
            }
        
        elif data['transaction_type'] == 'hourly_leave':
            required_leave_fields = ['leave_date', 'hours']
            for field in required_leave_fields:
                if not data.get(field):
                    return jsonify({'message': f'الحقل {field} مطلوب للإجازة الساعية'}), 400
            
            details = {
                'leave_date': data['leave_date'],
                'hours': int(data['hours']),
                'reason': data.get('reason'),
                'start_time': data.get('start_time'),
                'end_time': data.get('end_time')
            }
        
        elif data['transaction_type'] == 'daily_leave':
            required_leave_fields = ['start_date', 'days']
            for field in required_leave_fields:
                if not data.get(field):
                    return jsonify({'message': f'الحقل {field} مطلوب للإجازة اليومية'}), 400
            
            details = {
                'start_date': data['start_date'],
                'days': int(data['days']),
                'reason': data.get('reason'),
                'end_date': data.get('end_date')
            }
        
        transaction.set_details(details)
        
        db.session.add(transaction)
        db.session.flush()  # للحصول على معرف المعاملة
        
        # إنشاء سجلات الموافقة المطلوبة
        required_approvers = transaction.get_required_approvers()
        
        for approver in required_approvers:
            approval = TransactionApproval(
                transaction_id=transaction.id,
                approver_id=approver.id
            )
            db.session.add(approval)
        
        db.session.commit()
        
        return jsonify({
            'message': 'تم إنشاء المعاملة بنجاح',
            'transaction': {
                'id': transaction.id,
                'transaction_number': transaction.transaction_number,
                'transaction_type': transaction.transaction_type,
                'status': transaction.status,
                'employee': {
                    'id': employee.id,
                    'full_name': employee.full_name,
                    'fingerprint_id': employee.fingerprint_id
                },
                'details': transaction.get_details(),
                'required_approvals': len(required_approvers),
                'pending_approvals': len(required_approvers)
            }
        }), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'حدث خطأ أثناء إنشاء المعاملة: {str(e)}'}), 500

# =========================== الحصول على جميع المعاملات ===========================

@transaction_bp.route('/api/transactions', methods=['GET'])
@token_required
def get_transactions(user):
    try:
        current_user = User.query.get(user.id)
        if not current_user:
            return jsonify({'message': 'المستخدم غير موجود'}), 404
        
        # فلترة المعاملات حسب صلاحيات المستخدم
        query = Transaction.query
        
        if not current_user.is_super_admin():
            # إظهار المعاملات التي يمكن للمستخدم الوصول إليها
            accessible_employee_ids = [emp.id for emp in current_user.get_accessible_employees()]
            
            if accessible_employee_ids:
                query = query.filter(Transaction.employee_id.in_(accessible_employee_ids))
            else:
                # إذا لم يكن له صلاحية على أي موظف، إظهار المعاملات التي طلبها فقط
                query = query.filter(Transaction.requested_by == user.id)
        
        # فلترة حسب النوع إذا تم تحديده
        transaction_type = request.args.get('type')
        if transaction_type:
            query = query.filter(Transaction.transaction_type == transaction_type)
        
        # فلترة حسب الحالة إذا تم تحديدها
        status = request.args.get('status')
        if status:
            query = query.filter(Transaction.status == status)
        
        # فلترة حسب الموظف إذا تم تحديده
        employee_id = request.args.get('employee_id')
        if employee_id:
            query = query.filter(Transaction.employee_id == employee_id)
        
        # ترتيب النتائج
        query = query.order_by(Transaction.created_at.desc())
        
        # التصفح (pagination)
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        transactions = query.paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        result = []
        for transaction in transactions.items:
            # حساب عدد الموافقات
            total_approvals = transaction.approvals.count()
            approved_count = transaction.approvals.filter_by(status='approved').count()
            rejected_count = transaction.approvals.filter_by(status='rejected').count()
            pending_count = transaction.approvals.filter_by(status='pending').count()
            
            # معلومات الموظف
            employee_data = {
                'id': transaction.employee.id,
                'full_name': transaction.employee.full_name,
                'fingerprint_id': transaction.employee.fingerprint_id
            }
            
            # معلومات طالب المعاملة
            requester_data = {
                'id': transaction.requester.id,
                'username': transaction.requester.username,
                'user_type': transaction.requester.user_type
            }
            
            result.append({
                'id': transaction.id,
                'transaction_number': transaction.transaction_number,
                'transaction_type': transaction.transaction_type,
                'status': transaction.status,
                'employee': employee_data,
                'requester': requester_data,
                'details': transaction.get_details(),
                'notes': transaction.notes,
                'reason_for_rejection': transaction.reason_for_rejection,
                'approvals': {
                    'total': total_approvals,
                    'approved': approved_count,
                    'rejected': rejected_count,
                    'pending': pending_count
                },
                'created_at': transaction.created_at.isoformat(),
                'updated_at': transaction.updated_at.isoformat(),
                'approved_at': transaction.approved_at.isoformat() if transaction.approved_at else None,
                'rejected_at': transaction.rejected_at.isoformat() if transaction.rejected_at else None
            })
        
        return jsonify({
            'transactions': result,
            'pagination': {
                'page': transactions.page,
                'pages': transactions.pages,
                'per_page': transactions.per_page,
                'total': transactions.total,
                'has_next': transactions.has_next,
                'has_prev': transactions.has_prev
            }
        }), 200
    
    except Exception as e:
        return jsonify({'message': f'حدث خطأ أثناء جلب المعاملات: {str(e)}'}), 500

# =========================== الحصول على معاملة محددة ===========================

@transaction_bp.route('/api/transactions/<int:transaction_id>', methods=['GET'])
@token_required
def get_transaction(user, transaction_id):
    try:
        transaction = Transaction.query.get(transaction_id)
        if not transaction:
            return jsonify({'message': 'المعاملة غير موجودة'}), 404
        
        current_user = User.query.get(user.id)
        
        # التحقق من صلاحية الوصول
        if not current_user.is_super_admin():
            accessible_employee_ids = [emp.id for emp in current_user.get_accessible_employees()]
            if transaction.employee_id not in accessible_employee_ids and transaction.requested_by != user.id:
                return jsonify({'message': 'ليس لديك صلاحية للوصول إلى هذه المعاملة'}), 403
        
        # معلومات التفصيلية للموافقات
        approvals_data = []
        for approval in transaction.approvals:
            approvals_data.append({
                'id': approval.id,
                'approver': {
                    'id': approval.approver.id,
                    'username': approval.approver.username,
                    'user_type': approval.approver.user_type,
                    'employee_name': approval.approver.employee.full_name if approval.approver.employee else None
                },
                'status': approval.status,
                'notes': approval.notes,
                'approved_at': approval.approved_at.isoformat() if approval.approved_at else None,
                'rejected_at': approval.rejected_at.isoformat() if approval.rejected_at else None,
                'created_at': approval.created_at.isoformat()
            })
        
        return jsonify({
            'id': transaction.id,
            'transaction_number': transaction.transaction_number,
            'transaction_type': transaction.transaction_type,
            'status': transaction.status,
            'employee': {
                'id': transaction.employee.id,
                'full_name': transaction.employee.full_name,
                'fingerprint_id': transaction.employee.fingerprint_id,
                'department': transaction.employee.department.name if transaction.employee.department else None,
                'branch': transaction.employee.branch.name if transaction.employee.branch else None
            },
            'requester': {
                'id': transaction.requester.id,
                'username': transaction.requester.username,
                'user_type': transaction.requester.user_type,
                'employee_name': transaction.requester.employee.full_name if transaction.requester.employee else None
            },
            'details': transaction.get_details(),
            'notes': transaction.notes,
            'reason_for_rejection': transaction.reason_for_rejection,
            'approvals': approvals_data,
            'can_approve': transaction.can_be_approved_by(current_user),
            'created_at': transaction.created_at.isoformat(),
            'updated_at': transaction.updated_at.isoformat(),
            'approved_at': transaction.approved_at.isoformat() if transaction.approved_at else None,
            'rejected_at': transaction.rejected_at.isoformat() if transaction.rejected_at else None
        }), 200
    
    except Exception as e:
        return jsonify({'message': f'حدث خطأ أثناء جلب المعاملة: {str(e)}'}), 500

# =========================== الموافقة على معاملة ===========================

@transaction_bp.route('/api/transactions/<int:transaction_id>/approve', methods=['POST'])
@token_required
def approve_transaction(user, transaction_id):
    try:
        transaction = Transaction.query.get(transaction_id)
        if not transaction:
            return jsonify({'message': 'المعاملة غير موجودة'}), 404
        
        current_user = User.query.get(user.id)
        
        # التحقق من إمكانية الموافقة
        if not transaction.can_be_approved_by(current_user):
            return jsonify({'message': 'ليس لديك صلاحية للموافقة على هذه المعاملة'}), 403
        
        # التحقق من حالة المعاملة
        if transaction.status != 'pending':
            return jsonify({'message': 'لا يمكن الموافقة على معاملة غير معلقة'}), 400
        
        # البحث عن سجل الموافقة
        approval = TransactionApproval.query.filter_by(
            transaction_id=transaction_id,
            approver_id=user.id
        ).first()
        
        if not approval:
            return jsonify({'message': 'لم يتم العثور على سجل الموافقة'}), 404
        
        # التحقق من عدم وجود موافقة مسبقة
        if approval.status != 'pending':
            return jsonify({'message': 'تم التعامل مع هذه الموافقة مسبقاً'}), 400
        
        data = request.get_json()
        notes = data.get('notes') if data else None
        
        # الموافقة
        approval.approve(notes)
        db.session.commit()
        
        # التحقق من اكتمال جميع الموافقات
        if transaction.is_fully_approved():
            message = 'تم إنشاء السجل النهائي بنجاح'
        else:
            pending_approvers = transaction.get_pending_approvers()
            message = f'تم حفظ موافقتك. في انتظار موافقة {len(pending_approvers)} مستخدم آخر'
        
        return jsonify({
            'message': message,
            'transaction_status': transaction.status,
            'is_fully_approved': transaction.is_fully_approved()
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'حدث خطأ أثناء الموافقة: {str(e)}'}), 500

# =========================== رفض معاملة ===========================

@transaction_bp.route('/api/transactions/<int:transaction_id>/reject', methods=['POST'])
@token_required
def reject_transaction(user, transaction_id):
    try:
        transaction = Transaction.query.get(transaction_id)
        if not transaction:
            return jsonify({'message': 'المعاملة غير موجودة'}), 404
        
        current_user = User.query.get(user.id)
        
        # التحقق من إمكانية الرفض
        if not transaction.can_be_approved_by(current_user):
            return jsonify({'message': 'ليس لديك صلاحية لرفض هذه المعاملة'}), 403
        
        # التحقق من حالة المعاملة
        if transaction.status != 'pending':
            return jsonify({'message': 'لا يمكن رفض معاملة غير معلقة'}), 400
        
        # البحث عن سجل الموافقة
        approval = TransactionApproval.query.filter_by(
            transaction_id=transaction_id,
            approver_id=user.id
        ).first()
        
        if not approval:
            return jsonify({'message': 'لم يتم العثور على سجل الموافقة'}), 404
        
        # التحقق من عدم وجود رفض مسبق
        if approval.status != 'pending':
            return jsonify({'message': 'تم التعامل مع هذه الموافقة مسبقاً'}), 400
        
        data = request.get_json()
        notes = data.get('notes') if data else None
        
        if not notes:
            return jsonify({'message': 'سبب الرفض مطلوب'}), 400
        
        # الرفض
        approval.reject(notes)
        db.session.commit()
        
        return jsonify({
            'message': 'تم رفض المعاملة',
            'transaction_status': transaction.status
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'حدث خطأ أثناء رفض المعاملة: {str(e)}'}), 500

# =========================== الحصول على المعاملات المعلقة للمستخدم ===========================

@transaction_bp.route('/api/transactions/pending-approvals', methods=['GET'])
@token_required
def get_pending_approvals(user):
    try:
        current_user = User.query.get(user.id)
        if not current_user:
            return jsonify({'message': 'المستخدم غير موجود'}), 404
        
        # الحصول على المعاملات التي تحتاج موافقة هذا المستخدم
        pending_approvals = TransactionApproval.query.filter_by(
            approver_id=user.id,
            status='pending'
        ).join(Transaction).filter(
            Transaction.status == 'pending'
        ).all()
        
        result = []
        for approval in pending_approvals:
            transaction = approval.transaction
            
            result.append({
                'approval_id': approval.id,
                'transaction': {
                    'id': transaction.id,
                    'transaction_number': transaction.transaction_number,
                    'transaction_type': transaction.transaction_type,
                    'status': transaction.status,
                    'employee': {
                        'id': transaction.employee.id,
                        'full_name': transaction.employee.full_name,
                        'fingerprint_id': transaction.employee.fingerprint_id
                    },
                    'requester': {
                        'id': transaction.requester.id,
                        'username': transaction.requester.username,
                        'user_type': transaction.requester.user_type
                    },
                    'details': transaction.get_details(),
                    'notes': transaction.notes,
                    'created_at': transaction.created_at.isoformat()
                },
                'created_at': approval.created_at.isoformat()
            })
        
        return jsonify({
            'pending_approvals': result,
            'count': len(result)
        }), 200
    
    except Exception as e:
        return jsonify({'message': f'حدث خطأ أثناء جلب الموافقات المعلقة: {str(e)}'}), 500

# =========================== إحصائيات المعاملات ===========================

@transaction_bp.route('/api/transactions/statistics', methods=['GET'])
@token_required
def get_transaction_statistics(user):
    try:
        current_user = User.query.get(user.id)
        if not current_user:
            return jsonify({'message': 'المستخدم غير موجود'}), 404
        
        # فلترة المعاملات حسب صلاحيات المستخدم
        query = Transaction.query
        
        if not current_user.is_super_admin():
            accessible_employee_ids = [emp.id for emp in current_user.get_accessible_employees()]
            if accessible_employee_ids:
                query = query.filter(Transaction.employee_id.in_(accessible_employee_ids))
            else:
                query = query.filter(Transaction.requested_by == user.id)
        
        # إحصائيات عامة
        total_transactions = query.count()
        pending_transactions = query.filter(Transaction.status == 'pending').count()
        approved_transactions = query.filter(Transaction.status == 'approved').count()
        rejected_transactions = query.filter(Transaction.status == 'rejected').count()
        
        # إحصائيات حسب النوع
        transaction_types = ['advance', 'reward', 'penalty', 'hourly_leave', 'daily_leave']
        type_statistics = {}
        
        for trans_type in transaction_types:
            type_query = query.filter(Transaction.transaction_type == trans_type)
            type_statistics[trans_type] = {
                'total': type_query.count(),
                'pending': type_query.filter(Transaction.status == 'pending').count(),
                'approved': type_query.filter(Transaction.status == 'approved').count(),
                'rejected': type_query.filter(Transaction.status == 'rejected').count()
            }
        
        # المعاملات المعلقة للمستخدم الحالي
        my_pending_approvals = TransactionApproval.query.filter_by(
            approver_id=user.id,
            status='pending'
        ).join(Transaction).filter(
            Transaction.status == 'pending'
        ).count()
        
        return jsonify({
            'overview': {
                'total': total_transactions,
                'pending': pending_transactions,
                'approved': approved_transactions,
                'rejected': rejected_transactions
            },
            'by_type': type_statistics,
            'my_pending_approvals': my_pending_approvals
        }), 200
    
    except Exception as e:
        return jsonify({'message': f'حدث خطأ أثناء جلب الإحصائيات: {str(e)}'}), 500

# =========================== حذف معاملة ===========================

@transaction_bp.route('/api/transactions/<int:transaction_id>', methods=['DELETE'])
@token_required
def delete_transaction(user, transaction_id):
    try:
        transaction = Transaction.query.get(transaction_id)
        if not transaction:
            return jsonify({'message': 'المعاملة غير موجودة'}), 404
        
        current_user = User.query.get(user.id)
        
        # فقط السوبر أدمن أو منشئ المعاملة يمكنهم حذفها
        if not current_user.is_super_admin() and transaction.requested_by != user.id:
            return jsonify({'message': 'ليس لديك صلاحية لحذف هذه المعاملة'}), 403
        
        # لا يمكن حذف المعاملات المقبولة
        if transaction.status == 'approved':
            return jsonify({'message': 'لا يمكن حذف معاملة مقبولة'}), 400
        
        # حذف الموافقات المرتبطة
        TransactionApproval.query.filter_by(transaction_id=transaction_id).delete()
        
        # حذف المعاملة
        db.session.delete(transaction)
        db.session.commit()
        
        return jsonify({'message': 'تم حذف المعاملة بنجاح'}), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'حدث خطأ أثناء حذف المعاملة: {str(e)}'}), 500

# =========================== تحديث معاملة ===========================

@transaction_bp.route('/api/transactions/<int:transaction_id>', methods=['PUT'])
@token_required
def update_transaction(user, transaction_id):
    try:
        transaction = Transaction.query.get(transaction_id)
        if not transaction:
            return jsonify({'message': 'المعاملة غير موجودة'}), 404
        
        current_user = User.query.get(user.id)
        
        # فقط السوبر أدمن أو منشئ المعاملة يمكنهم تحديثها
        if not current_user.is_super_admin() and transaction.requested_by != user.id:
            return jsonify({'message': 'ليس لديك صلاحية لتحديث هذه المعاملة'}), 403
        
        # لا يمكن تحديث المعاملات المقبولة أو المرفوضة
        if transaction.status != 'pending':
            return jsonify({'message': 'لا يمكن تحديث معاملة غير معلقة'}), 400
        
        data = request.get_json()
        
        # تحديث الملاحظات
        if 'notes' in data:
            transaction.notes = data['notes']
        
        # تحديث التفاصيل حسب نوع المعاملة
        current_details = transaction.get_details()
        
        if transaction.transaction_type in ['advance', 'reward', 'penalty']:
            if 'amount' in data:
                current_details['amount'] = float(data['amount'])
            if 'document_number' in data:
                current_details['document_number'] = data['document_number']
            if 'date' in data:
                current_details['date'] = data['date']
        
        elif transaction.transaction_type == 'hourly_leave':
            if 'leave_date' in data:
                current_details['leave_date'] = data['leave_date']
            if 'hours' in data:
                current_details['hours'] = int(data['hours'])
            if 'reason' in data:
                current_details['reason'] = data['reason']
            if 'start_time' in data:
                current_details['start_time'] = data['start_time']
            if 'end_time' in data:
                current_details['end_time'] = data['end_time']
        
        elif transaction.transaction_type == 'daily_leave':
            if 'start_date' in data:
                current_details['start_date'] = data['start_date']
            if 'days' in data:
                current_details['days'] = int(data['days'])
            if 'reason' in data:
                current_details['reason'] = data['reason']
            if 'end_date' in data:
                current_details['end_date'] = data['end_date']
        
        transaction.set_details(current_details)
        transaction.updated_at = datetime.now()
        
        db.session.commit()
        
        return jsonify({
            'message': 'تم تحديث المعاملة بنجاح',
            'transaction': {
                'id': transaction.id,
                'transaction_number': transaction.transaction_number,
                'transaction_type': transaction.transaction_type,
                'status': transaction.status,
                'details': transaction.get_details(),
                'notes': transaction.notes,
                'updated_at': transaction.updated_at.isoformat()
            }
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'حدث خطأ أثناء تحديث المعاملة: {str(e)}'}), 500
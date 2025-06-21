# controllers/absence_transaction_controller.py

from flask import request, jsonify
from datetime import datetime, date, timedelta
from app import db
from app.models import Employee, User, Shift, AbsenceTransaction, TransactionHistory, Attendance

class AbsenceTransactionController:
    
    @staticmethod
    def create_absence_transaction(employee_id, absence_date, shift_id=None, created_by=None):
        """
        إنشاء معاملة غياب جديدة
        """
        try:
            # التحقق من وجود الموظف
            employee = Employee.query.get(employee_id)
            if not employee:
                return {'message': 'الموظف غير موجود'}, 404
            
            # التحقق من عدم وجود معاملة غياب لنفس التاريخ
            existing_transaction = AbsenceTransaction.query.filter_by(
                employee_id=employee_id,
                absence_date=absence_date
            ).first()
            
            if existing_transaction:
                return {'message': 'يوجد معاملة غياب لنفس التاريخ'}, 400
            
            # إنشاء معاملة الغياب
            transaction = AbsenceTransaction(
                employee_id=employee_id,
                absence_date=absence_date,
                shift_id=shift_id,
                created_by=created_by
            )
            
            # توليد رقم المعاملة
            transaction.transaction_number = transaction.generate_transaction_number()
            
            db.session.add(transaction)
            db.session.flush()  # للحصول على ID
            
            # إضافة سجل في التاريخ
            history = TransactionHistory(
                transaction_id=transaction.id,
                action='created',
                new_status='pending',
                user_id=created_by or 1,  # 1 للنظام
                notes='تم إنشاء معاملة الغياب تلقائياً'
            )
            
            db.session.add(history)
            db.session.commit()
            
            return {
                'message': 'تم إنشاء معاملة الغياب بنجاح',
                'transaction': {
                    'id': transaction.id,
                    'transaction_number': transaction.transaction_number,
                    'employee_name': employee.full_name,
                    'absence_date': absence_date.isoformat(),
                    'status': transaction.status
                }
            }, 201
            
        except Exception as e:
            db.session.rollback()
            return {'message': f'خطأ في إنشاء معاملة الغياب: {str(e)}'}, 500
    
    @staticmethod
    def get_pending_transactions_for_user(user_id):
        """
        الحصول على المعاملات المعلقة للمستخدم
        """
        try:
            user = User.query.get(user_id)
            if not user:
                return {'message': 'المستخدم غير موجود'}, 404
            
            # الحصول على الموظفين الذين يمكن للمستخدم إدارتهم
            accessible_employees = user.get_accessible_employees()
            employee_ids = [emp.id for emp in accessible_employees]
            
            if not employee_ids:
                return [], 200
            
            # جلب المعاملات المعلقة
            pending_transactions = AbsenceTransaction.query.filter(
                AbsenceTransaction.employee_id.in_(employee_ids),
                AbsenceTransaction.status == 'pending'
            ).order_by(AbsenceTransaction.created_at.desc()).all()
            
            result = []
            for transaction in pending_transactions:
                result.append({
                    'id': transaction.id,
                    'transaction_number': transaction.transaction_number,
                    'employee_id': transaction.employee_id,
                    'employee_name': transaction.employee.full_name,
                    'employee_fingerprint_id': transaction.employee.fingerprint_id,
                    'absence_date': transaction.absence_date.isoformat(),
                    'shift_name': transaction.shift.name if transaction.shift else None,
                    'status': transaction.status,
                    'is_notified': transaction.is_notified,
                    'is_paid': transaction.is_paid,
                    'absence_reason': transaction.absence_reason,
                    'employee_notes': transaction.employee_notes,
                    'created_at': transaction.created_at.isoformat(),
                    'days_since_absence': (date.today() - transaction.absence_date).days
                })
            
            return result, 200
            
        except Exception as e:
            return {'message': f'خطأ في جلب المعاملات: {str(e)}'}, 500
    
    @staticmethod
    def approve_transaction(transaction_id, user_id, is_notified, is_paid, manager_notes=None):
        """
        الموافقة على معاملة الغياب
        """
        try:
            # جلب المعاملة
            transaction = AbsenceTransaction.query.get(transaction_id)
            if not transaction:
                return {'message': 'المعاملة غير موجودة'}, 404
            
            # التحقق من حالة المعاملة
            if transaction.status != 'pending':
                return {'message': 'لا يمكن تعديل معاملة تم البت فيها مسبقاً'}, 400
            
            # التحقق من صلاحية المستخدم
            user = User.query.get(user_id)
            if not user or not transaction.can_be_approved_by(user):
                return {'message': 'ليس لديك صلاحية للموافقة على هذه المعاملة'}, 403
            
            # تحديث المعاملة
            old_status = transaction.status
            transaction.status = 'approved'
            transaction.is_notified = is_notified
            transaction.is_paid = is_paid
            transaction.manager_notes = manager_notes
            transaction.approved_by = user_id
            transaction.approved_at = datetime.now()
            
            # إضافة سجل في التاريخ
            history = TransactionHistory(
                transaction_id=transaction.id,
                action='approved',
                old_status=old_status,
                new_status='approved',
                user_id=user_id,
                notes=f'الموافقة: مبلغ={is_notified}, مدفوع={is_paid}. {manager_notes or ""}'
            )
            
            db.session.add(history)
            db.session.commit()
            
            return {
                'message': 'تم الموافقة على المعاملة بنجاح',
                'transaction': {
                    'id': transaction.id,
                    'transaction_number': transaction.transaction_number,
                    'status': transaction.status,
                    'is_notified': transaction.is_notified,
                    'is_paid': transaction.is_paid
                }
            }, 200
            
        except Exception as e:
            db.session.rollback()
            return {'message': f'خطأ في الموافقة على المعاملة: {str(e)}'}, 500
    
    @staticmethod
    def reject_transaction(transaction_id, user_id, manager_notes=None):
        """
        رفض معاملة الغياب
        """
        try:
            # جلب المعاملة
            transaction = AbsenceTransaction.query.get(transaction_id)
            if not transaction:
                return {'message': 'المعاملة غير موجودة'}, 404
            
            # التحقق من حالة المعاملة
            if transaction.status != 'pending':
                return {'message': 'لا يمكن تعديل معاملة تم البت فيها مسبقاً'}, 400
            
            # التحقق من صلاحية المستخدم
            user = User.query.get(user_id)
            if not user or not transaction.can_be_approved_by(user):
                return {'message': 'ليس لديك صلاحية لرفض هذه المعاملة'}, 403
            
            # تحديث المعاملة
            old_status = transaction.status
            transaction.status = 'rejected'
            transaction.manager_notes = manager_notes
            transaction.approved_by = user_id
            transaction.approved_at = datetime.now()
            
            # إضافة سجل في التاريخ
            history = TransactionHistory(
                transaction_id=transaction.id,
                action='rejected',
                old_status=old_status,
                new_status='rejected',
                user_id=user_id,
                notes=f'تم رفض المعاملة. {manager_notes or ""}'
            )
            
            db.session.add(history)
            db.session.commit()
            
            return {
                'message': 'تم رفض المعاملة بنجاح',
                'transaction': {
                    'id': transaction.id,
                    'transaction_number': transaction.transaction_number,
                    'status': transaction.status
                }
            }, 200
            
        except Exception as e:
            db.session.rollback()
            return {'message': f'خطأ في رفض المعاملة: {str(e)}'}, 500
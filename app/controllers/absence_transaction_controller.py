from flask import request, jsonify
from datetime import datetime, date, timedelta
from app import db
from app.models import Employee, User, Shift, AbsenceTransaction, TransactionHistory, Attendance, AbsenceQuestion

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
        الحصول على المعاملات المعلقة للمستخدم بعد إنشاء معاملات الغياب التلقائية
        """
        try:
            # الخطوة الأولى: إنشاء معاملات الغياب التلقائية للشهر الماضي
            result, status = AbsenceTransactionController.generate_absence_transactions_for_last_month(user_id)
            if status != 200:
                return {'message': f'فشل في إنشاء معاملات الغياب التلقائية: {result.get("error")}'}, status

            # التحقق من وجود المستخدم
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
    
    @staticmethod
    def get_approved_absence_transactions(absence_date=None):
        """
        جلب جميع معاملات الغياب المعتمدة مع اسم الموظف، تاريخ الغياب، والأسئلة مع إجاباتها
        يمكن تصفية المعاملات بناءً على تاريخ الغياب إذا تم تمريره
        """
        try:
            # الاستعلام عن المعاملات التي حالتها 'approved'
            query = AbsenceTransaction.query.filter_by(status='approved')
            
            # إذا تم تمرير absence_date، قم بتصفية المعاملات بناءً عليه
            if absence_date:
                try:
                    absence_date = datetime.fromisoformat(absence_date).date()
                    query = query.filter(AbsenceTransaction.absence_date == absence_date)
                except ValueError:
                    return {"error": "صيغة التاريخ غير صحيحة. يجب أن تكون YYYY-MM-DD"}, 400

            transactions = query.all()
            result = []

            for transaction in transactions:
                # التحقق من وجود الموظف
                employee_name = transaction.employee.full_name if transaction.employee else "غير متوفر"

                # جمع الأسئلة والإجابات مع إضافة answer_id
                answers = [
                    {
                        "answer_id": answer.id,  # ← الإضافة الجديدة
                        "question_id": answer.absence_question.id,
                        "question_text": answer.absence_question.question_text,
                        "deduction_value": answer.absence_question.deduction_value,
                        "is_answered": answer.is_answered
                    } for answer in transaction.answers
                ]

                # إنشاء كائن النتيجة لكل معاملة
                transaction_data = {
                    "transaction_id": transaction.id,
                    "employee_name": employee_name,
                    "absence_date": transaction.absence_date.isoformat(),
                    "answers": answers
                }
                result.append(transaction_data)

            return {"approved_transactions": result}, 200

        except Exception as e:
            return {"error": f"خطأ أثناء استرجاع معاملات الغياب المعتمدة: {str(e)}"}, 500

    @staticmethod
    def generate_absence_transactions_for_last_month(user_id):
        """
        إنشاء معاملات غياب تلقائية للموظفين الغائبين خلال الشهر الماضي بناءً على سجلات الحضور
        للموظفين الذين يمكن للمستخدم إدارتهم
        """
        try:
            # التحقق من وجود المستخدم
            user = User.query.get(user_id)
            if not user:
                return {"error": "المستخدم غير موجود"}, 404

            # الحصول على الموظفين الذين يمكن للمستخدم إدارتهم
            employees = user.get_accessible_employees()
            if not employees:
                return {"message": "لا يوجد موظفين يمكن للمستخدم إدارتهم", "transactions": []}, 200

            # تحديد نطاق الشهر الماضي (من اليوم إلى 30 يومًا للوراء)
            today = date.today()
            start_date = today - timedelta(days=30)
            date_range = [start_date + timedelta(days=x) for x in range((today - start_date).days + 1)]

            created_transactions = []
            for employee in employees:
                if not hasattr(employee, 'is_active') or not employee.is_active:
                    continue  # تخطي الموظفين غير النشطين إذا كان الحقل موجودًا
                for check_date in date_range:
                    # التحقق من غياب الموظف في التاريخ الحالي
                    is_absent = AbsenceTransactionController.is_employee_absent(employee, check_date)
                    
                    if is_absent:
                        # إنشاء معاملة غياب جديدة
                        result, status = AbsenceTransactionController.create_absence_transaction(
                            employee_id=employee.id,
                            absence_date=check_date,
                            shift_id=employee.shift_id,
                            created_by=user_id  # استخدام user_id بدلاً من 1
                        )
                        
                        if status == 201:
                            created_transactions.append(result['transaction'])

            db.session.commit()
            return {
                "message": f"تم إنشاء {len(created_transactions)} معاملة غياب بنجاح",
                "transactions": created_transactions
            }, 200

        except Exception as e:
            db.session.rollback()
            return {"error": f"خطأ أثناء إنشاء معاملات الغياب: {str(e)}"}, 500

    @staticmethod
    def is_employee_absent(employee, check_date):
        """
        التحقق من غياب موظف في تاريخ محدد
        """
        try:
            # التحقق من وجود وردية للموظف
            if not employee.shift_id:
                return False
            
            shift = Shift.query.get(employee.shift_id)
            if not shift:
                return False
            
            # التحقق من كون اليوم يوم عمل في الوردية
            day_name = check_date.strftime('%A').lower()  # الحصول على اسم اليوم بالإنجليزية بأحرف صغيرة
            if not shift.is_working_day(day_name):
                return False  # ليس يوم عمل
            
            # التحقق من وجود سجل حضور للموظف في ذلك التاريخ
            attendance_exists = Attendance.query.filter(
                Attendance.empId == employee.id,
                db.func.date(Attendance.createdAt) == check_date
            ).first()
            
            if attendance_exists:
                return False  # الموظف حضر
            
            # التحقق من عدم وجود معاملة غياب مسبقة
            existing_transaction = AbsenceTransaction.query.filter_by(
                employee_id=employee.id,
                absence_date=check_date
            ).first()
            
            if existing_transaction:
                return False  # يوجد معاملة مسبقة
            
            return True  # الموظف غائب
            
        except Exception as e:
            print(f"خطأ في التحقق من غياب الموظف {employee.id}: {str(e)}")
            return False

    @staticmethod
    def create_absence_question(data):
        """
        إنشاء سؤال جديد للخصومات
        """
        try:
            # التحقق من وجود الحقول المطلوبة
            if not data.get('question_text') or not isinstance(data.get('deduction_value'), (int, float)):
                return {"error": "question_text و deduction_value مطلوبان"}, 400

            # إنشاء سؤال جديد
            question = AbsenceQuestion(
                question_text=data['question_text'],
                deduction_value=float(data['deduction_value']),
                is_active=data.get('is_active', True)
            )
            db.session.add(question)
            db.session.commit()

            # إرجاع الاستجابة مع المعلومات المرسلة
            return {
                "message": "تم إنشاء السؤال بنجاح",
                "question_id": question.id,
                "question_text": question.question_text,
                "deduction_value": question.deduction_value,
                "is_active": question.is_active
            }, 201

        except Exception as e:
            db.session.rollback()
            return {"error": f"خطأ أثناء إنشاء السؤال: {str(e)}"}, 500
from datetime import datetime
from app import db
from app.models import User
from app.models.absence_answer import AbsenceAnswer
from app.models.absence_transaction import AbsenceTransaction # type: ignore
from app.models.absence_question import AbsenceQuestion
from flask import jsonify

from app.models.transaction_history import TransactionHistory

class AbsenceAnswerController:
    @staticmethod
    def create_absence_answer(data):
        """
        إنشاء إجابات متعددة لمعاملة غياب مع تغيير حالة المعاملة إلى معتمدة
        """
        try:
            # التحقق من وجود الحقول المطلوبة
            required_fields = ['absence_transaction_id', 'user_id', 'questions']
            if not all(field in data for field in required_fields):
                return {"error": "absence_transaction_id، user_id، و questions مطلوبة"}, 400

            # التحقق من أن questions هي مصفوفة وغير فارغة
            if not isinstance(data['questions'], list) or not data['questions']:
                return {"error": "يجب أن تكون questions مصفوفة غير فارغة"}, 400

            # جلب معاملة الغياب
            transaction = AbsenceTransaction.query.get(data['absence_transaction_id'])
            if not transaction:
                return {"error": "معاملة الغياب غير موجودة"}, 404

            # التحقق من حالة المعاملة
            if transaction.status != 'pending':
                return {"message": "لا يمكن تعديل معاملة تم البت فيها مسبقاً"}, 400

            # التحقق من صلاحية المستخدم
            user = User.query.get(data['user_id'])
            if not user or not transaction.can_be_approved_by(user):
                return {"message": "ليس لديك صلاحية للموافقة على هذه المعاملة"}, 403

            # إنشاء إجابات لكل سؤال في المصفوفة
            answer_ids = []
            for question_data in data['questions']:
                # التحقق من وجود الحقول المطلوبة لكل سؤال
                if not all(field in question_data for field in ['absence_question_id', 'is_answered']):
                    return {"error": "كل سؤال يجب أن يحتوي على absence_question_id و is_answered"}, 400

                # جلب السؤال
                question = AbsenceQuestion.query.get(question_data['absence_question_id'])
                if not question:
                    return {"error": f"السؤال {question_data['absence_question_id']} غير موجود"}, 404

                # إنشاء إجابة جديدة
                answer = AbsenceAnswer(
                    absence_transaction_id=data['absence_transaction_id'],
                    absence_question_id=question_data['absence_question_id'],
                    is_answered=question_data['is_answered']
                )
                db.session.add(answer)
                answer_ids.append(answer.id)

            # تحديث المعاملة إلى الحالة "approved"
            old_status = transaction.status
            transaction.status = 'approved'
            transaction.approved_by = data['user_id']
            transaction.approved_at = datetime.now()
            # تحديث الحقول الإضافية إذا كانت موجودة في النموذج
            # if hasattr(transaction, 'is_notified'):
            #     transaction.is_notified = data.get('is_notified', False)
            # if hasattr(transaction, 'is_paid'):
            #     transaction.is_paid = data.get('is_paid', False)
            transaction.manager_notes = data.get('manager_notes')

            # إضافة سجل في التاريخ
            history = TransactionHistory(
                transaction_id=transaction.id,
                action='approved',
                old_status=old_status,
                new_status='approved',
                user_id=data['user_id'],
                notes=f"تمت الموافقة مع إنشاء {len(answer_ids)} إجابات. {data.get('manager_notes') or ''}"
            )
            db.session.add(history)

            db.session.commit()

            # إعداد استجابة النجاح
            response = {
                "message": f"تم إنشاء {len(answer_ids)} إجابات والموافقة على المعاملة بنجاح",
                "answer_ids": answer_ids,
                "transaction": {
                    "id": transaction.id,
                    "transaction_number": transaction.transaction_number,
                    "status": transaction.status
                }
            }
            # إضافة is_notified و is_paid إلى الاستجابة إذا كانت موجودة
            # if hasattr(transaction, 'is_notified'):
            #     response['transaction']['is_notified'] = transaction.is_notified
            # if hasattr(transaction, 'is_paid'):
            #     response['transaction']['is_paid'] = transaction.is_paid

            return response, 201

        except Exception as e:
            db.session.rollback()
            return {"error": f"خطأ أثناء إنشاء الإجابات والموافقة: {str(e)}"}, 500

    @staticmethod
    def get_absence_answers_by_transaction(transaction_id):
        """
        استرجاع جميع الإجابات لمعاملة غياب معينة
        """
        try:
            transaction = AbsenceTransaction.query.get(transaction_id)
            if not transaction:
                return {"error": "معاملة الغياب غير موجودة"}, 404

            answers = transaction.answers.all()
            result = [
                {
                    "id": a.id,
                    "absence_transaction_id": a.absence_transaction_id,
                    "absence_question_id": a.absence_question_id,
                    "question_text": a.absence_question.question_text,
                    "is_answered": a.is_answered,
                    "created_at": a.created_at.isoformat(),
                    "updated_at": a.updated_at.isoformat()
                } for a in answers
            ]
            return {"answers": result}, 200

        except Exception as e:
            return {"error": f"خطأ أثناء استرجاع الإجابات: {str(e)}"}, 500

    @staticmethod
    def get_absence_answer_by_id(answer_id):
        """
        استرجاع إجابة معينة بناءً على المعرف
        """
        try:
            answer = AbsenceAnswer.query.get(answer_id)
            if not answer:
                return {"error": "الإجابة غير موجودة"}, 404

            result = {
                "id": answer.id,
                "absence_transaction_id": answer.absence_transaction_id,
                "absence_question_id": answer.absence_question_id,
                "question_text": answer.absence_question.question_text,
                "is_answered": answer.is_answered,
                "created_at": answer.created_at.isoformat(),
                "updated_at": answer.updated_at.isoformat()
            }
            return result, 200

        except Exception as e:
            return {"error": f"خطأ أثناء استرجاع الإجابة: {str(e)}"}, 500

    

    @staticmethod
    def update_absence_answer(data):
        """
        تحديث جميع الإجابات المرتبطة بمعاملة غياب
        """
        try:
            # التحقق من وجود الحقول المطلوبة
            required_fields = ['absence_transaction_id', 'answers']
            if not all(field in data for field in required_fields):
                return {"error": "absence_transaction_id و answers مطلوبة"}, 400

            # التحقق من أن answers هي مصفوفة وغير فارغة
            if not isinstance(data['answers'], list) or not data['answers']:
                return {"error": "يجب أن تكون answers مصفوفة غير فارغة"}, 400

            # جلب معاملة الغياب
            transaction = AbsenceTransaction.query.get(data['absence_transaction_id'])
            if not transaction:
                return {"error": "معاملة الغياب غير موجودة"}, 404

            updated_answer_ids = []

            # التكرار على الإجابات المراد تحديثها
            for answer_data in data['answers']:
                # التحقق من وجود الحقول المطلوبة لكل إجابة
                if not all(field in answer_data for field in ['answer_id', 'is_answered']):
                    return {"error": "كل إجابة يجب أن تحتوي على answer_id و is_answered"}, 400

                # جلب الإجابة
                answer = AbsenceAnswer.query.get(answer_data['answer_id'])
                if not answer:
                    return {"error": f"الإجابة {answer_data['answer_id']} غير موجودة"}, 404

                # التحقق من أن الإجابة مرتبطة بمعاملة الغياب المحددة
                if answer.absence_transaction_id != data['absence_transaction_id']:
                    return {"error": f"الإجابة {answer_data['answer_id']} غير مرتبطة بمعاملة الغياب هذه"}, 400

                # تحديث الحقول إذا تم تمريرها
                answer.is_answered = answer_data['is_answered']

                if 'absence_question_id' in answer_data:
                    question = AbsenceQuestion.query.get(answer_data['absence_question_id'])
                    if not question:
                        return {"error": f"السؤال {answer_data['absence_question_id']} غير موجود"}, 404
                    answer.absence_question_id = answer_data['absence_question_id']

                updated_answer_ids.append(answer.id)

            db.session.commit()

            return {
                "message": f"تم تحديث {len(updated_answer_ids)} إجابات بنجاح",
                "updated_answer_ids": updated_answer_ids
            }, 200

        except Exception as e:
            db.session.rollback()
            return {"error": f"خطأ أثناء تحديث الإجابات: {str(e)}"}, 500

    @staticmethod
    def delete_absence_answer(answer_id):
        """
        حذف إجابة
        """
        try:
            answer = AbsenceAnswer.query.get(answer_id)
            if not answer:
                return {"error": "الإجابة غير موجودة"}, 404

            db.session.delete(answer)
            db.session.commit()
            return {"message": "تم حذف الإجابة بنجاح"}, 200

        except Exception as e:
            db.session.rollback()
            return {"error": f"خطأ أثناء حذف الإجابة: {str(e)}"}, 500
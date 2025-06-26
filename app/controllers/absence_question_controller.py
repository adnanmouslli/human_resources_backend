from app import db
from app.models.absence_question import AbsenceQuestion
from flask import jsonify


class AbsenceQuestionController:

    @staticmethod
    def create_absence_question(data):
        """
        إنشاء سؤال جديد للخصومات
        """
        try:
            # التحقق من وجود الحقول المطلوبة
            if not data.get('question_text') or not isinstance(data.get('deduction_value'), (int, float)):
                return {
                    "error": "question_text و deduction_value مطلوبان"
                }, 400

            # إنشاء سؤال جديد
            question = AbsenceQuestion(
                question_text=data['question_text'],
                deduction_value=float(data['deduction_value']),
                is_active=data.get('is_active', True)
            )
            db.session.add(question)
            db.session.commit()

            return {
                "message": "تم إنشاء السؤال بنجاح",
                
                    "id": question.id,
                    "question_text": question.question_text,
                    "deduction_value": question.deduction_value,
                    "is_active": question.is_active,
                    "created_at": question.created_at.isoformat(),
                    "updated_at": question.updated_at.isoformat()
                
            }, 201

        except Exception as e:
            db.session.rollback()
            return {"error": f"خطأ أثناء إنشاء السؤال: {str(e)}"}, 500

    @staticmethod
    def get_absence_question():
        """
        استرجاع جميع الأسئلة
        """
        try:
            questions = AbsenceQuestion.query.all()
            result = [
                {
                    "id": q.id,
                    "question_text": q.question_text,
                    "deduction_value": q.deduction_value,
                    "is_active": q.is_active,
                    "created_at": q.created_at.isoformat(),
                    "updated_at": q.updated_at.isoformat()
                } for q in questions
            ]
            return {
                "count": len(result),
                "questions": result
            }, 200

        except Exception as e:
            return {"error": f"خطأ أثناء استرجاع الأسئلة: {str(e)}"}, 500

    @staticmethod
    def get_absence_question_by_id(question_id):
        """
        استرجاع سؤال معين بناءً على المعرف
        """
        try:
            question = AbsenceQuestion.query.get(question_id)
            if not question:
                return {"error": "السؤال غير موجود"}, 404

            return {
                "question": {
                    "id": question.id,
                    "question_text": question.question_text,
                    "deduction_value": question.deduction_value,
                    "is_active": question.is_active,
                    "created_at": question.created_at.isoformat(),
                    "updated_at": question.updated_at.isoformat()
                }
            }, 200

        except Exception as e:
            return {"error": f"خطأ أثناء استرجاع السؤال: {str(e)}"}, 500

    @staticmethod
    def update_absence_question(question_id, data):
        """
        تحديث سؤال موجود
        """
        try:
            question = AbsenceQuestion.query.get(question_id)
            if not question:
                return {"error": "السؤال غير موجود"}, 404

            # تحديث الحقول إذا تم تمريرها
            if 'question_text' in data:
                question.question_text = data['question_text']
            if 'deduction_value' in data:
                if not isinstance(data['deduction_value'], (int, float)):
                    return {"error": "deduction_value يجب أن يكون رقمًا"}, 400
                question.deduction_value = float(data['deduction_value'])
            if 'is_active' in data:
                question.is_active = data['is_active']

            db.session.commit()

            return {
                "message": "تم تحديث السؤال بنجاح",
                
                    "id": question.id,
                    "question_text": question.question_text,
                    "deduction_value": question.deduction_value,
                    "is_active": question.is_active,
                    "created_at": question.created_at.isoformat(),
                    "updated_at": question.updated_at.isoformat()
                
            }, 200

        except Exception as e:
            db.session.rollback()
            return {"error": f"خطأ أثناء تحديث السؤال: {str(e)}"}, 500

    @staticmethod
    def delete_absence_question(question_id):
        """
        حذف سؤال
        """
        try:
            question = AbsenceQuestion.query.get(question_id)
            if not question:
                return {"error": "السؤال غير موجود"}, 404

            db.session.delete(question)
            db.session.commit()
            return {"message": "تم حذف السؤال بنجاح"}, 200

        except Exception as e:
            db.session.rollback()
            return {"error": f"خطأ أثناء حذف السؤال: {str(e)}"}, 500

    @staticmethod
    def toggle_absence_question_status(question_id):
        """
        قلب حالة السؤال (is_active) من True إلى False أو العكس
        """
        try:
            question = AbsenceQuestion.query.get(question_id)
            if not question:
                return {"error": "السؤال غير موجود"}, 404

            # قلب قيمة is_active
            question.is_active = not question.is_active
            db.session.commit()

            return {
                "message": "تم تغيير حالة السؤال بنجاح",
                "question": {
                    "id": question.id,
                    "question_text": question.question_text,
                    "is_active": question.is_active,
                    "updated_at": question.updated_at.isoformat()
                }
            }, 200

        except Exception as e:
            db.session.rollback()
            return {"error": f"خطأ أثناء تغيير حالة السؤال: {str(e)}"}, 500
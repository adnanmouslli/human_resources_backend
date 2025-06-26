from flask import Blueprint, request, jsonify
from app.controllers.absence_question_controller import AbsenceQuestionController

absence_question_bp = Blueprint('absence_question', __name__)

@absence_question_bp.route('/api/absence_questions', methods=['POST'])
def create_absence_question():
    """
    إنشاء سؤال جديد
    """
    data = request.get_json()
    response, status = AbsenceQuestionController.create_absence_question(data)
    return jsonify(response), status

@absence_question_bp.route('/api/absence_questions', methods=['GET'])
def get_absence_questions():
    """
    استرجاع جميع الأسئلة
    """
    response, status = AbsenceQuestionController.get_absence_question()
    return jsonify(response), status

@absence_question_bp.route('/api/absence_questions/<int:question_id>', methods=['GET'])
def get_absence_question(question_id):
    """
    استرجاع سؤال معين
    """
    response, status = AbsenceQuestionController.get_absence_question_by_id(question_id)
    return jsonify(response), status

@absence_question_bp.route('/api/absence_questions/<int:question_id>', methods=['PUT'])
def update_absence_question(question_id):
    """
    تحديث سؤال
    """
    data = request.get_json()
    response, status = AbsenceQuestionController.update_absence_question(question_id, data)
    return jsonify(response), status

@absence_question_bp.route('/api/absence_questions/<int:question_id>', methods=['DELETE'])
def delete_absence_question(question_id):
    """
    حذف سؤال
    """
    response, status = AbsenceQuestionController.delete_absence_question(question_id)
    return jsonify(response), status

@absence_question_bp.route('/api/absence_questions/<int:question_id>/toggle', methods=['PATCH'])
def toggle_absence_question_status(question_id):
    """
    قلب حالة السؤال (is_active) من True إلى False أو العكس
    """
    response, status = AbsenceQuestionController.toggle_absence_question_status(question_id)
    return jsonify(response), status
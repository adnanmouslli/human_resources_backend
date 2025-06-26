from flask import Blueprint, request, jsonify
from app.controllers.absence_answer_controller import AbsenceAnswerController

absence_answer_bp = Blueprint('absence_answer', __name__)

@absence_answer_bp.route('/api/absence_answers', methods=['POST'])
def create_absence_answer():
    """
    إنشاء إجابة جديدة
    """
    data = request.get_json()
    response, status = AbsenceAnswerController.create_absence_answer(data)
    return jsonify(response), status

@absence_answer_bp.route('/api/absence_answers/transaction/<int:transaction_id>', methods=['GET'])
def get_absence_answers_by_transaction(transaction_id):
    """
    استرجاع جميع الإجابات لمعاملة غياب معينة
    """
    response, status = AbsenceAnswerController.get_absence_answers_by_transaction(transaction_id)
    return jsonify(response), status

@absence_answer_bp.route('/api/absence_answers/<int:answer_id>', methods=['GET'])
def get_absence_answer(answer_id):
    """
    استرجاع إجابة معينة
    """
    response, status = AbsenceAnswerController.get_absence_answer_by_id(answer_id)
    return jsonify(response), status

@absence_answer_bp.route('/api/absence_answers', methods=['PUT'])
def update_absence_answers():
    data = request.get_json()

    # التحقق من أن البيانات ليست None
    if not data:
        return jsonify({"error": "بيانات غير صالحة أو غير موجودة في الطلب"}), 400

    # التحقق من وجود absence_transaction_id
    if 'absence_transaction_id' not in data:
        return jsonify({"error": "absence_transaction_id مطلوب في الـ body"}), 400

    # استدعاء التابع مع تمرير data بشكل صحيح
    response, status = AbsenceAnswerController.update_absence_answer(data)
    return jsonify(response), status

@absence_answer_bp.route('/api/absence_answers/<int:answer_id>', methods=['DELETE'])
def delete_absence_answer(answer_id):
    """
    حذف إجابة
    """
    response, status = AbsenceAnswerController.delete_absence_answer(answer_id)
    return jsonify(response), status
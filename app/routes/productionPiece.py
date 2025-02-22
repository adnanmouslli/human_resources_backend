
from flask import Blueprint, request, jsonify
from app.controllers.production_piece_controller import ProductionPieceController
from app.utils import token_required

production_piece_bp = Blueprint('production_piece', __name__)

@production_piece_bp.route('/api/production-pieces', methods=['POST'])
@token_required
def create_production_piece(user_id):
    data = request.get_json()
    response, status_code = ProductionPieceController.create_production_piece(data)
    return jsonify(response), status_code

@production_piece_bp.route('/api/production-pieces', methods=['GET'])
@token_required
def get_all_production_pieces(user_id):
    response, status_code = ProductionPieceController.get_all_production_pieces()
    return jsonify(response), status_code

@production_piece_bp.route('/api/production-pieces/list', methods=['GET'])
@token_required
def get_list_production_pieces(user_id):
    response, status_code = ProductionPieceController.get_production_pieces_list()
    return jsonify(response), status_code

@production_piece_bp.route('/api/production-pieces/<int:id>', methods=['GET'])
@token_required
def get_production_piece(user_id, id):
    response, status_code = ProductionPieceController.get_production_piece_by_id(id)
    return jsonify(response), status_code

@production_piece_bp.route('/api/production-pieces/<int:id>', methods=['PUT'])
@token_required
def update_production_piece(user_id, id):
    data = request.get_json()
    response, status_code = ProductionPieceController.update_production_piece(id, data)
    return jsonify(response), status_code

@production_piece_bp.route('/api/production-pieces/<int:id>', methods=['DELETE'])
@token_required
def delete_production_piece(user_id, id):
    response, status_code = ProductionPieceController.delete_production_piece(id)
    return jsonify(response), status_code

@production_piece_bp.route('/api/production-pieces/number/<string:number>', methods=['GET'])
@token_required
def get_production_piece_by_number(user_id, number):
    response, status_code = ProductionPieceController.get_production_piece_by_number(number)
    return jsonify(response), status_code
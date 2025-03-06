
from app import db
from app.models import ProductionPiece

class ProductionPieceController:
    @staticmethod
    def create_production_piece(data):
        # Validate required fields
        required_fields = ['piece_number', 'piece_name', 'price_levels']
        missing_fields = [field for field in required_fields if field not in data or not data[field]]
        if missing_fields:
            return {'message': f'Missing fields: {", ".join(missing_fields)}'}, 400

        try:
            piece = ProductionPiece(
                piece_number=data['piece_number'],
                piece_name=data['piece_name'],
                price_levels=data['price_levels'],
                is_active=data.get('is_active', True)  # تعيين حالة التفعيل، الافتراضي: مفعّل

            )
            db.session.add(piece)
            db.session.commit()

            return {
                'message': 'Production piece created',
                'piece': {
                    'id': piece.id,
                    'piece_number': piece.piece_number,
                    'piece_name': piece.piece_name,
                    'is_active': piece.is_active
                }
            }, 201

        except Exception as e:
            return {'message': 'Error creating production piece', 'error': str(e)}, 500

    @staticmethod
    def get_all_production_pieces():
        try:
            pieces = ProductionPiece.query.all()
            return [
                {
                    'id': piece.id,
                    'piece_number': piece.piece_number,
                    'piece_name': piece.piece_name,
                    'price_levels': piece.price_levels,
                    'is_active': piece.is_active,
                    'created_at': piece.created_at.isoformat(),
                    'updated_at': piece.updated_at.isoformat()
                } for piece in pieces
            ], 200
        except Exception as e:
            return {'message': 'Error fetching production pieces', 'error': str(e)}, 500

    @staticmethod
    def get_production_pieces_list():
        try:
            # تعديل الاستعلام لجلب القطع الفعالة فقط باستخدام شرط is_active=True
            pieces = ProductionPiece.query.filter_by(is_active=True).all()
            return [
                {
                    'id': piece.id,
                    'piece_name': piece.piece_name,
                    'piece_number': piece.piece_number
                } for piece in pieces
            ], 200
        except Exception as e:
            return {'message': 'Error fetching production pieces list', 'error': str(e)}, 500
    
    @staticmethod
    def get_production_piece_by_id(id):
        piece = ProductionPiece.query.get(id)

        if not piece:
            return {'message': 'Production piece not found'}, 404

        return {
            'id': piece.id,
            'piece_number': piece.piece_number,
            'piece_name': piece.piece_name,
            'price_levels': piece.price_levels,
            'is_active': piece.is_active,
            'created_at': piece.created_at.isoformat(),
            'updated_at': piece.updated_at.isoformat()
        }, 200

    @staticmethod
    def update_production_piece(id, data):
        piece = ProductionPiece.query.get(id)

        if not piece:
            return {'message': 'Production piece not found'}, 404

        try:
            if 'piece_number' in data:
                piece.piece_number = data['piece_number']
            if 'piece_name' in data:
                piece.piece_name = data['piece_name']
            if 'price_levels' in data:
                piece.price_levels = data['price_levels']
            if 'is_active' in data:
                piece.is_active = data['is_active']    

            db.session.commit()

            return {
                'message': 'Production piece updated',
                'piece': {
                    'id': piece.id,
                    'piece_number': piece.piece_number,
                    'piece_name': piece.piece_name
                }
            }, 200

        except Exception as e:
            return {'message': 'Error updating production piece', 'error': str(e)}, 500

    @staticmethod
    def delete_production_piece(id):
        piece = ProductionPiece.query.get(id)

        if not piece:
            return {'message': 'Production piece not found'}, 404

        try:
            db.session.delete(piece)
            db.session.commit()
            return {'message': 'Production piece deleted'}, 200

        except Exception as e:
            return {'message': 'Error deleting production piece', 'error': str(e)}, 500

    @staticmethod
    def get_production_piece_by_number(number):
        piece = ProductionPiece.query.filter_by(piece_number=number).first()

        if not piece:
            return {'message': 'Production piece not found'}, 404

        return {
            'id': piece.id,
            'piece_number': piece.piece_number,
            'piece_name': piece.piece_name,
            'price_levels': piece.price_levels,
            'is_active': piece.is_active

        }, 200
    @staticmethod
    def toggle_piece_activation(id):
        """تبديل حالة تفعيل القطعة"""
        piece = ProductionPiece.query.get(id)

        if not piece:
            return {'message': 'Production piece not found'}, 404

        try:
            piece.is_active = not piece.is_active
            db.session.commit()
            
            status_message = 'تفعيل' if piece.is_active else 'إيقاف'
            return {
                'message': f'تم {status_message} القطعة بنجاح',
                'piece': {
                    'id': piece.id,
                    'piece_number': piece.piece_number,
                    'piece_name': piece.piece_name,
                    'is_active': piece.is_active
                }
            }, 200

        except Exception as e:
            return {'message': 'Error toggling piece activation', 'error': str(e)}, 500
 
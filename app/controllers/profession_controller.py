
from flask import jsonify
from app import db
from app.models import Profession

class ProfessionController:
    @staticmethod
    def create_profession(data):
        # Validate required fields
        required_fields = ['name', 'hourly_rate', 'daily_rate']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return {'message': f'Missing fields: {", ".join(missing_fields)}'}, 400

        profession = Profession(
            name=data['name'],
            hourly_rate=data['hourly_rate'],
            daily_rate=data['daily_rate']
        )
        db.session.add(profession)
        db.session.commit()

        return {
            'id': profession.id,
            'name': profession.name,
            'hourly_rate': profession.hourly_rate,
            'daily_rate': profession.daily_rate
        }, 201

    @staticmethod
    def get_all_professions():
        professions = Profession.query.all()
        return [{
            key: value for key, value in profession.__dict__.items() 
            if not key.startswith('_')
        } for profession in professions], 200

    @staticmethod
    def get_profession_by_id(id):
        profession = Profession.query.get(id)
        if not profession:
            return {'message': 'Profession not found'}, 404

        return {
            'id': profession.id,
            'name': profession.name,
            'hourly_rate': profession.hourly_rate,
            'daily_rate': profession.daily_rate
        }, 200

    @staticmethod
    def update_profession(id, data):
        profession = Profession.query.get(id)
        if not profession:
            return {'message': 'Profession not found'}, 404

        for key, value in data.items():
            if hasattr(profession, key):
                setattr(profession, key, value)

        db.session.commit()

        return {
            'id': profession.id,
            'name': profession.name,
            'hourly_rate': profession.hourly_rate,
            'daily_rate': profession.daily_rate
        }, 200

    @staticmethod
    def delete_profession(id):
        profession = Profession.query.get(id)
        if not profession:
            return {'message': 'Profession not found'}, 404
        
        db.session.delete(profession)
        db.session.commit()
        
        return {'message': 'Profession deleted'}, 200
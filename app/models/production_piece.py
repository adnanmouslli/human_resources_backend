# production_piece.py

from app import db
from sqlalchemy import JSON

class ProductionPiece(db.Model):
    __tablename__ = 'production_pieces'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    piece_number = db.Column(db.String(50), unique=True, nullable=False)  # رقم القطعة
    is_active = db.Column(db.Boolean, default=True)  # حالة تفعيل القطعة
    piece_name = db.Column(db.String(255), nullable=False)  # اسم القطعة
    price_levels = db.Column(JSON, nullable=False)  # تخزين أسعار المستويات كـ JSON
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    def __repr__(self):
        return f"<ProductionPiece {self.piece_name}>"

"""
شرح الجدول:
يمثل جدول القطع الإنتاجية في النظام. يحتوي على رقم القطعة، اسم القطعة، حالتها (مفعلة أو غير مفعلة)، ومستويات الأسعار المخزنة بصيغة JSON.
"""

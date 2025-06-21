# models/transaction_type.py

from app import db
from datetime import datetime

class TransactionType(db.Model):
    """
    أنواع المعاملات
    """
    __tablename__ = 'transaction_types'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)  # اسم نوع المعاملة
    code = db.Column(db.String(20), nullable=False, unique=True)  # رمز المعاملة
    description = db.Column(db.Text, nullable=True)  # وصف المعاملة
    auto_create = db.Column(db.Boolean, default=False)  # هل يتم إنشاؤها تلقائياً
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<TransactionType {self.name}>"
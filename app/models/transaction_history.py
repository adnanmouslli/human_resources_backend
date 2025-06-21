# models/transaction_history.py
from app import db
from datetime import datetime
from sqlalchemy import CheckConstraint

class TransactionHistory(db.Model):
    """
    تاريخ تغييرات المعاملات
    """
    __tablename__ = 'transaction_history'
    
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('absence_transactions.id'), nullable=False)
    action = db.Column(db.String(50), nullable=False)  # created, updated, approved, rejected
    old_status = db.Column(db.String(20), nullable=True)
    new_status = db.Column(db.String(20), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    
    # معلومات المستخدم
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # العلاقات
    transaction = db.relationship('AbsenceTransaction', backref='history')
    user = db.relationship('User', backref='transaction_actions')
    
    def __repr__(self):
        return f"<TransactionHistory {self.action} by {self.user_id}>"
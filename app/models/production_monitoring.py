# production_monitoring.py

from app import db
from datetime import datetime

class ProductionMonitoring(db.Model):
    __tablename__ = 'production_monitoring'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    piece_id = db.Column(db.Integer, db.ForeignKey('production_pieces.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, default=db.func.current_date())
    quantity = db.Column(db.Integer, nullable=False)  # عدد القطع
    quality_grade = db.Column(db.String(1), nullable=False)  # مستوى الجودة (A, B, C, D, E)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
    notes = db.Column(db.Text, nullable=True)  # ملاحظات إضافية



    def __repr__(self):
        return f"<ProductionMonitoring Employee: {self.employee_id}, Piece: {self.piece_id}, Quantity: {self.quantity}, Grade: {self.quality_grade}>"

"""
شرح الجدول:
يمثل هذا الجدول مراقبة الإنتاج حيث يتم تسجيل إنتاج الموظف من القطع.
الربط مع موظف يتم من خلال `employee_id` ومع القطعة من خلال `piece_id`.
"""

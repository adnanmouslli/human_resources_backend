# reward.py

from app import db
from datetime import date

class Reward(db.Model):
    __tablename__ = 'rewards'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    date = db.Column(db.Date, nullable=False, default=db.func.current_date())
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    document_number = db.Column(db.String(50), nullable=False)
    notes = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<Reward {self.id}, Employee {self.employee_id}>"

"""
شرح الجدول:
يمثل جدول المكافآت التي يحصل عليها الموظف. يحتوي على المبلغ، تاريخ المكافأة، رقم المستند، والملاحظات.
يتم الربط مع جدول `Employee` من خلال العمود `employee_id`.
"""
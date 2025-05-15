from app import db
from datetime import datetime


class Department(db.Model):
    __tablename__ = 'departments'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # العلاقة مع الفروع (من خلال جدول العلاقات)
    branches = db.relationship(
        'Branch', 
        secondary='branch_departments', 
        back_populates='departments',
        lazy='dynamic'
    )
    
    # العلاقة مع الموظفين
    employees = db.relationship(
        'Employee',
        foreign_keys='Employee.department_id', 
        backref=db.backref('department', lazy=True),
        lazy='dynamic'
    )

    @property
    def head(self):
        """الحصول على رئيس القسم من خلال Employee.is_department_head"""
        return self.employees.filter_by(is_department_head=True).first()
    
    def __repr__(self):
        return f"<Department {self.name}>"


# جدول العلاقة بين الفروع والأقسام
class BranchDepartment(db.Model):
    __tablename__ = 'branch_departments'
    
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), primary_key=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
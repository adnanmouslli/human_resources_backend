from app import db
from datetime import datetime


class Department(db.Model):
    __tablename__ = 'departments'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)  # اسم القسم
    description = db.Column(db.Text, nullable=True)  # وصف القسم
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # العلاقة مع الفروع (من خلال جدول العلاقات)
    branches = db.relationship('Branch', secondary='branch_departments', back_populates='departments')
    
    # العلاقة مع الموظفين
    employees = db.relationship(
        'Employee',
        foreign_keys='Employee.department_id', 
        backref=db.backref('department', lazy=True),
        lazy=True
    )    

    # العلاقة مع رئيس القسم
    head_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    head = db.relationship(
        'Employee',
        foreign_keys=[head_id],  
        backref=db.backref('headed_department', lazy=True),
        lazy=True
    )

    branches = db.relationship('Branch', secondary='branch_departments', back_populates='departments')

    
    def __repr__(self):
        return f"<Department {self.name}>"
    

# BranchDepartment Model (جدول العلاقة بين الفروع والأقسام)
class BranchDepartment(db.Model):
    __tablename__ = 'branch_departments'
    
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), primary_key=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
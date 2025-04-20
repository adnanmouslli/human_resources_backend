# user.py

from app import db

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)  # اسم المستخدم، يجب أن يكون فريدًا
    password = db.Column(db.String(255), nullable=False)              # كلمة المرور، يتم تخزينها مشفرة عادةً

    def __repr__(self):
        return f"<User {self.username}>"

"""
شرح الجدول:
يمثل جدول المستخدمين الذين يمكنهم تسجيل الدخول إلى لوحة التحكم الخاصة بالنظام.
عادة ما يكون المستخدم مديرًا أو موظف شؤون إدارية.
"""

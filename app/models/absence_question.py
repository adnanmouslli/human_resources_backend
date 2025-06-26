from app import db
from datetime import datetime

class AbsenceQuestion(db.Model):
    """
    جدول الأسئلة الثابتة المتعلقة بالخصومات
    """
    __tablename__ = 'absence_questions'

    id = db.Column(db.Integer, primary_key=True)
    
    # نص السؤال
    question_text = db.Column(db.Text, nullable=False)

    # قيمة الخصم (عدد الأيام - مثال: 0.5، 1، 1.5...)
    deduction_value = db.Column(db.Float, nullable=False)

    # الحالة (تفعيل / تعطيل السؤال)
    is_active = db.Column(db.Boolean, default=True)

    # وقت الإنشاء / التحديث
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # العلاقة العكسية مع جدول الإجابات
    answers = db.relationship('AbsenceAnswer', back_populates='absence_question', lazy='dynamic')

    def __repr__(self):
        return f"<AbsenceQuestion {self.id}>"
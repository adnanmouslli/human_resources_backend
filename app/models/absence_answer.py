from app import db
from datetime import datetime

class AbsenceAnswer(db.Model):
    """
    جدول الإجابات الفعلية على الأسئلة لكل معاملة غياب
    """
    __tablename__ = 'absence_answers'

    id = db.Column(db.Integer, primary_key=True)

    # ربط بمعاملة الغياب
    absence_transaction_id = db.Column(
        db.Integer,
        db.ForeignKey('absence_transactions.id'),
        nullable=False
    )

    # ربط بالسؤال
    absence_question_id = db.Column(
        db.Integer,
        db.ForeignKey('absence_questions.id'),
        nullable=False
    )

    # حالة الإجابة (نعم/لا)
    is_answered = db.Column(db.Boolean, nullable=False, default=False)

    # وقت الإنشاء / التحديث
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # العلاقات
    absence_transaction = db.relationship('AbsenceTransaction', back_populates='answers')
    absence_question = db.relationship('AbsenceQuestion', back_populates='answers')

    def __repr__(self):
        return f"<AbsenceAnswer {self.id}>"
from app import db

class Profession(db.Model):
    __tablename__ = 'professions'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # ID تلقائي
    name = db.Column(db.String(100), nullable=False)  # اسم المهنة
    hourly_rate = db.Column(db.Numeric(10, 2), nullable=False)  # سعر الساعة
    daily_rate = db.Column(db.Numeric(10, 2), nullable=False)  # سعر اليوم
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())  # تاريخ الإضافة
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())  # تاريخ التحديث

    def __repr__(self):
        return f"<Profession {self.name}, Hourly: {self.hourly_rate}, Daily: {self.daily_rate}>"


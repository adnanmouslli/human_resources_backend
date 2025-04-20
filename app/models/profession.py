# profession.py

from app import db

class Profession(db.Model):
    __tablename__ = 'professions'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # ID تلقائي
    name = db.Column(db.String(100), nullable=False)  #
def __repr__(self):
    return f"<Profession {self.name}>"

class Config:
    SECRET_KEY = '6ad03e74cbec26ed98a94a45042409410a74aeaee427bbadb7ea64179d8e8262'
    SQLALCHEMY_DATABASE_URI = 'mssql+pyodbc://localhost\\SQLEXPRESS/hr_deploy?driver=ODBC+Driver+17+for+SQL+Server'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

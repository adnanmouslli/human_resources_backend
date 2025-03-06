class Config:
    SECRET_KEY = '6ad03e74cbec26ed98a94a45042409410a74aeaee427bbadb7ea64179d8e8262'
    SQLALCHEMY_DATABASE_URI = (
        'mssql+pyodbc:///?odbc_connect='
        'DRIVER={ODBC Driver 18 for SQL Server};'
        'SERVER=localhost;'
        'DATABASE=hr_production;'
        'UID=SA;'
        'PWD=sql@123456789;'
        'TrustServerCertificate=yes;'
        'Encrypt=yes;'
        'authentication=SqlPassword'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
FROM python:3.9-slim

# تثبيت ODBC Driver لـ Microsoft SQL Server
RUN apt-get update && apt-get install -y gnupg2 curl iputils-ping telnet
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
RUN curl https://packages.microsoft.com/config/debian/10/prod.list > /etc/apt/sources.list.d/mssql-release.list
RUN apt-get update && ACCEPT_EULA=Y apt-get install -y msodbcsql17 unixodbc-dev

# تثبيت المكتبات الضرورية
RUN apt-get install -y build-essential

# إنشاء دليل التطبيق
WORKDIR /app

# نسخ ملف المتطلبات أولاً للاستفادة من التخزين المؤقت في Docker
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# نسخ ملف الدخول وجعله قابلاً للتنفيذ
COPY entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh

# نسخ باقي ملفات التطبيق
COPY . /app/

# إنشاء مجلد للتحميلات
RUN mkdir -p /app/uploads

# تعيين المتغيرات البيئية
ENV FLASK_APP=run.py
ENV PYTHONUNBUFFERED=1

# استخدام ملف الدخول
ENTRYPOINT ["/app/entrypoint.sh"]

# تشغيل التطبيق
CMD ["python", "run.py"]
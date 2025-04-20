FROM ubuntu:22.04

# تعيين المتغيرات البيئية
ENV ACCEPT_EULA=Y
ENV MSSQL_SA_PASSWORD=sql@123456789
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive
ENV FLASK_APP=run.py
ENV FLASK_ENV=development

# تثبيت الأدوات الأساسية ومتطلبات SQL Server
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    apt-transport-https \
    software-properties-common \
    wget \
    python3 \
    python3-pip \
    python3-dev \
    build-essential \
    unixodbc-dev \
    redis-server

# إضافة PPA للحصول على إصدار أحدث من Python (اختياري)
RUN add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y python3.10 python3.10-dev python3.10-distutils

# إضافة مفتاح Microsoft GPG وإعداد مستودع SQL Server
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl https://packages.microsoft.com/config/ubuntu/22.04/mssql-server-2022.list > /etc/apt/sources.list.d/mssql-server-2022.list \
    && curl https://packages.microsoft.com/config/ubuntu/22.04/prod.list > /etc/apt/sources.list.d/mssql-release.list

# تثبيت SQL Server
RUN apt-get update && apt-get install -y mssql-server

# تثبيت أدوات SQL Server و ODBC Driver 17
RUN ACCEPT_EULA=Y apt-get install -y mssql-tools unixodbc-dev msodbcsql17

# إضافة SQL Server tools إلى PATH
ENV PATH="${PATH}:/opt/mssql-tools/bin"

# إنشاء دليل العمل
WORKDIR /app

# نسخ متطلبات بيثون وتثبيتها أولاً (للاستفادة من التخزين المؤقت للحاوية)
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# نسخ باقي الملفات إلى الحاوية
COPY . .

# كشف المنافذ
EXPOSE 1433 3000 6379

# إنشاء سكريبت بدء التشغيل
RUN chmod +x /app/entrypoint.sh

# تشغيل السكريبت عند بدء الحاوية
CMD ["/app/entrypoint.sh"]
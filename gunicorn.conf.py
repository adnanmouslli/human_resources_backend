# إعدادات gunicorn لصورة الإنتاج (Dockerfile.prod) — يقرؤها gunicorn تلقائياً من مجلد العمل
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '3000')}"

# عملية واحدة فقط: create_app يعدّل بنية القاعدة عند الإقلاع، وتعدد العمليات يكرر ذلك بالتوازي
workers = 1
worker_class = 'gthread'
threads = int(os.environ.get('GUNICORN_THREADS', '8'))

# عمليات طويلة (تقارير، استيراد Excel، backup/restore)
timeout = 600
graceful_timeout = 30

accesslog = '-'
errorlog = '-'

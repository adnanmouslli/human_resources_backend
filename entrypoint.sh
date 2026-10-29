#!/bin/bash
set -e

# انتظار حتى تكون قاعدة البيانات جاهزة — بيانات الاتصال تُقرأ من app/config.py (لا كلمات سر هنا)
wait_for_db() {
python3 - <<'EOF'
import importlib.util
from sqlalchemy import create_engine
spec = importlib.util.spec_from_file_location("config", "app/config.py")
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)
create_engine(config.Config.SQLALCHEMY_DATABASE_URI).connect().close()
EOF
}

echo "انتظار جاهزية قاعدة البيانات..."
for i in {1..30}; do
    if wait_for_db 2>/dev/null; then
        echo "تم الاتصال بقاعدة البيانات بنجاح!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "فشل الاتصال بقاعدة البيانات بعد 30 محاولة. إنهاء."
        exit 1
    fi
    echo "محاولة الاتصال بقاعدة البيانات... محاولة $i من 30"
    sleep 2
done

# تشغيل الأمر المحدد في Dockerfile (CMD)، وإلا run.py
if [ $# -eq 0 ]; then
    set -- python3 run.py
fi
exec "$@"

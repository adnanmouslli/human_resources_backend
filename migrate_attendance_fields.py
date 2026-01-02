"""
Migration Script: إضافة حقول تتبع مصدر البصمات
Date: 2026-01-03
Description: سكريبت آمن لتحديث جدول attendances بدون فقدان البيانات
"""

import sys
from datetime import datetime
from sqlalchemy import text
from app import create_app, db

def create_backup_table():
    """إنشاء نسخة احتياطية من جدول attendances"""
    backup_table_name = f"attendances_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    print(f"\n📦 إنشاء نسخة احتياطية: {backup_table_name}")

    backup_query = text(f"""
        SELECT *
        INTO {backup_table_name}
        FROM attendances;
    """)

    try:
        db.session.execute(backup_query)
        db.session.commit()
        print(f"✅ تم إنشاء نسخة احتياطية بنجاح: {backup_table_name}")
        return backup_table_name
    except Exception as e:
        print(f"❌ فشل إنشاء النسخة الاحتياطية: {e}")
        return None


def check_columns_exist():
    """التحقق من وجود الحقول الجديدة"""
    print("\n🔍 التحقق من الحقول الموجودة...")

    check_query = text("""
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'attendances'
        AND COLUMN_NAME IN ('source', 'created_by', 'created_by_user_id')
    """)

    result = db.session.execute(check_query)
    existing_columns = [row[0] for row in result]

    return {
        'source': 'source' in existing_columns,
        'created_by': 'created_by' in existing_columns,
        'created_by_user_id': 'created_by_user_id' in existing_columns
    }


def add_source_column():
    """إضافة حقل source"""
    print("\n➕ إضافة حقل 'source'...")

    try:
        query = text("""
            ALTER TABLE attendances
            ADD source VARCHAR(20) NULL DEFAULT 'fingerprint';
        """)
        db.session.execute(query)
        db.session.commit()
        print("✅ تم إضافة حقل 'source' بنجاح")
        return True
    except Exception as e:
        db.session.rollback()
        print(f"❌ خطأ في إضافة حقل 'source': {e}")
        return False


def add_created_by_column():
    """إضافة حقل created_by"""
    print("\n➕ إضافة حقل 'created_by'...")

    try:
        query = text("""
            ALTER TABLE attendances
            ADD created_by VARCHAR(100) NULL;
        """)
        db.session.execute(query)
        db.session.commit()
        print("✅ تم إضافة حقل 'created_by' بنجاح")
        return True
    except Exception as e:
        db.session.rollback()
        print(f"❌ خطأ في إضافة حقل 'created_by': {e}")
        return False


def add_created_by_user_id_column():
    """إضافة حقل created_by_user_id مع Foreign Key"""
    print("\n➕ إضافة حقل 'created_by_user_id'...")

    try:
        # إضافة الحقل
        query1 = text("""
            ALTER TABLE attendances
            ADD created_by_user_id INTEGER NULL;
        """)
        db.session.execute(query1)

        # إضافة Foreign Key Constraint
        query2 = text("""
            ALTER TABLE attendances
            ADD CONSTRAINT fk_attendance_created_by_user
                FOREIGN KEY (created_by_user_id)
                REFERENCES users(id)
                ON DELETE SET NULL;
        """)
        db.session.execute(query2)

        db.session.commit()
        print("✅ تم إضافة حقل 'created_by_user_id' و Foreign Key بنجاح")
        return True
    except Exception as e:
        db.session.rollback()
        print(f"❌ خطأ في إضافة حقل 'created_by_user_id': {e}")
        return False


def update_existing_records():
    """تحديث السجلات الموجودة لتعيين source='fingerprint'"""
    print("\n🔄 تحديث السجلات الموجودة...")

    try:
        query = text("""
            UPDATE attendances
            SET source = 'fingerprint'
            WHERE source IS NULL;
        """)
        result = db.session.execute(query)
        db.session.commit()
        print(f"✅ تم تحديث {result.rowcount} سجل بنجاح (source='fingerprint')")
        return True
    except Exception as e:
        db.session.rollback()
        print(f"❌ خطأ في تحديث السجلات: {e}")
        return False


def create_indexes():
    """إنشاء فهارس لتحسين الأداء"""
    print("\n📇 إنشاء الفهارس...")

    try:
        # فهرس source
        query1 = text("""
            CREATE INDEX idx_attendance_source
            ON attendances(source);
        """)
        db.session.execute(query1)
        print("✅ تم إنشاء فهرس 'idx_attendance_source'")

        # فهرس created_by_user_id
        query2 = text("""
            CREATE INDEX idx_attendance_created_by_user
            ON attendances(created_by_user_id);
        """)
        db.session.execute(query2)
        print("✅ تم إنشاء فهرس 'idx_attendance_created_by_user'")

        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        print(f"⚠️  تحذير: قد تكون الفهارس موجودة مسبقاً - {e}")
        return True  # نستمر حتى لو فشل إنشاء الفهارس


def verify_migration():
    """التحقق من نجاح الترحيل"""
    print("\n✔️  التحقق من نجاح الترحيل...")

    try:
        # التحقق من الحقول
        check_query = text("""
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'attendances'
            AND COLUMN_NAME IN ('source', 'created_by', 'created_by_user_id')
            ORDER BY COLUMN_NAME;
        """)
        result = db.session.execute(check_query)
        columns = result.fetchall()

        print("\nالحقول المضافة:")
        for col in columns:
            print(f"  - {col[0]}: {col[1]} (Nullable: {col[2]})")

        # عد السجلات
        count_query = text("""
            SELECT
                source,
                COUNT(*) as count
            FROM attendances
            GROUP BY source;
        """)
        result = db.session.execute(count_query)
        counts = result.fetchall()

        print("\nإحصائيات السجلات:")
        for row in counts:
            source = row[0] if row[0] else 'NULL'
            print(f"  - {source}: {row[1]} سجل")

        return True
    except Exception as e:
        print(f"❌ خطأ في التحقق: {e}")
        return False


def main():
    """الدالة الرئيسية للترحيل"""
    print("=" * 70)
    print("🚀 بدء ترحيل قاعدة البيانات - إضافة حقول تتبع مصدر البصمات")
    print("=" * 70)

    app = create_app()

    with app.app_context():
        try:
            # 1. التحقق من الحقول الموجودة
            existing = check_columns_exist()

            if all(existing.values()):
                print("\n⚠️  جميع الحقول موجودة مسبقاً!")
                response = input("هل تريد المتابعة على أي حال؟ (yes/no): ")
                if response.lower() != 'yes':
                    print("تم إلغاء الترحيل.")
                    return

            # 2. إنشاء نسخة احتياطية
            print("\n" + "=" * 70)
            response = input("هل تريد إنشاء نسخة احتياطية؟ (موصى به - yes/no): ")
            if response.lower() == 'yes':
                backup_name = create_backup_table()
                if not backup_name:
                    print("\n❌ فشل إنشاء النسخة الاحتياطية!")
                    response = input("هل تريد المتابعة بدون نسخة احتياطية؟ (yes/no): ")
                    if response.lower() != 'yes':
                        print("تم إلغاء الترحيل.")
                        return

            # 3. إضافة الحقول
            print("\n" + "=" * 70)
            print("🔧 بدء إضافة الحقول الجديدة...")
            print("=" * 70)

            success = True

            if not existing['source']:
                success = success and add_source_column()
            else:
                print("\n⏭️  حقل 'source' موجود مسبقاً، تخطي...")

            if not existing['created_by']:
                success = success and add_created_by_column()
            else:
                print("\n⏭️  حقل 'created_by' موجود مسبقاً، تخطي...")

            if not existing['created_by_user_id']:
                success = success and add_created_by_user_id_column()
            else:
                print("\n⏭️  حقل 'created_by_user_id' موجود مسبقاً، تخطي...")

            if not success:
                print("\n❌ فشل في إضافة بعض الحقول!")
                return

            # 4. تحديث السجلات الموجودة
            update_existing_records()

            # 5. إنشاء الفهارس
            create_indexes()

            # 6. التحقق
            verify_migration()

            print("\n" + "=" * 70)
            print("🎉 اكتمل الترحيل بنجاح!")
            print("=" * 70)
            print("\n📝 الخطوات التالية:")
            print("  1. راجع UPDATE_DATABASE_INSTRUCTIONS.md للمزيد من التفاصيل")
            print("  2. اختبر النظام للتأكد من عمل الميزات الجديدة")
            print("  3. راقب السجلات الجديدة للتأكد من تسجيل المصدر بشكل صحيح")

        except Exception as e:
            print(f"\n❌ خطأ عام في الترحيل: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == '__main__':
    main()

"""
Migration Script: توسيع أعمدة hours_per_day و salary في جدول خبرات المتقدمين
Date: 2026-09-19
Description: عمود hours_per_day كان VARCHAR(20) وعمود salary كان VARCHAR(50)،
             وأي نص حر أطول من ذلك (مثال: "من 9 صباحاً حتى 5 مساءً") كان يفشل
             بخطأ SQL Server truncation ويُسقط طلب التوظيف بالكامل بخطأ 500.
             هذا السكريبت يوسّع العمودين إلى VARCHAR(100) بدون فقدان بيانات.
"""

import sys
from sqlalchemy import text
from app import create_app, db

TABLE = 'recruitment_application_experiences'


def check_columns():
    print("\n🔍 التحقق من طول الأعمدة الحالية...")
    result = db.session.execute(text("""
        SELECT COLUMN_NAME, CHARACTER_MAXIMUM_LENGTH
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = :table
        AND COLUMN_NAME IN ('hours_per_day', 'salary')
    """), {'table': TABLE})
    lengths = {row[0]: row[1] for row in result}
    for col, length in lengths.items():
        print(f"  - {col}: {length}")
    return lengths


def widen_column(column_name):
    print(f"\n📏 توسيع العمود '{column_name}' إلى VARCHAR(100)...")
    try:
        db.session.execute(text(f"""
            ALTER TABLE {TABLE}
            ALTER COLUMN {column_name} VARCHAR(100) NULL;
        """))
        db.session.commit()
        print(f"✅ تم توسيع '{column_name}' بنجاح")
        return True
    except Exception as e:
        db.session.rollback()
        print(f"❌ فشل توسيع '{column_name}': {e}")
        return False


def main():
    print("=" * 70)
    print("🚀 بدء ترحيل: توسيع أعمدة الخبرات (hours_per_day, salary)")
    print("=" * 70)

    app = create_app()
    with app.app_context():
        lengths = check_columns()

        success = True
        if lengths.get('hours_per_day') != 100:
            success = widen_column('hours_per_day') and success
        else:
            print("\n⏭️  'hours_per_day' موسّع مسبقاً، تخطي...")

        if lengths.get('salary') != 100:
            success = widen_column('salary') and success
        else:
            print("\n⏭️  'salary' موسّع مسبقاً، تخطي...")

        if not success:
            print("\n❌ فشل الترحيل!")
            sys.exit(1)

        print("\n" + "=" * 70)
        print("🎉 اكتمل الترحيل بنجاح!")
        print("=" * 70)


if __name__ == '__main__':
    main()

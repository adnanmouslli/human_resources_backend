import click
import os
import shutil
from flask.cli import with_appcontext
from app import db
from sqlalchemy import text


@click.command()
@click.option('--yes', is_flag=True, help='تخطي رسالة التأكيد')
@with_appcontext
def reset_db(yes):
    """إعادة تعيين قاعدة البيانات - حذف كل الجداول والبيانات وإعادة إنشائها"""
    if not yes:
        if not click.confirm('⚠️  سيتم حذف جميع البيانات والجداول. هل أنت متأكد؟'):
            click.echo('❌ تم إلغاء العملية')
            return
    
    click.echo('🔧 بدء إعادة تعيين قاعدة البيانات...')
    
    try:
        # حذف مجلد migrations
        if os.path.exists('migrations'):
            shutil.rmtree('migrations')
            click.echo('✅ تم حذف مجلد migrations')
        
        # حذف جدول alembic_version أولاً إذا كان موجوداً
        try:
            with db.engine.connect() as conn:
                conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
                conn.commit()
            click.echo('✅ تم حذف جدول alembic_version')
        except Exception as e:
            click.echo(f'⚠️  تحذير عند حذف alembic_version: {str(e)}')
        
        # حذف جميع الجداول
        click.echo('🗑️  حذف جميع الجداول...')
        db.drop_all()
        click.echo('✅ تم حذف جميع الجداول')
        
        # إنشاء جداول جديدة
        click.echo('🏗️  إنشاء جداول جديدة...')
        db.create_all()
        click.echo('✅ تم إنشاء الجداول')
        
        # إعادة تهيئة Flask-Migrate
        click.echo('🔄 إعادة تهيئة Flask-Migrate...')
        os.system('flask db init')
        os.system('flask db migrate -m "Initial migration after reset"')
        os.system('flask db upgrade')
        
        click.echo('\n✅ تمت إعادة تعيين قاعدة البيانات بنجاح!')
        
    except Exception as e:
        click.echo(f'❌ حدث خطأ: {str(e)}', err=True)
        return


@click.command()
@with_appcontext
def fix_migrations():
    """إصلاح مشاكل migrations عن طريق إعادة تزامن قاعدة البيانات"""
    click.echo('🔧 إصلاح مشاكل migrations...')
    
    try:
        # حذف جدول alembic_version
        with db.engine.connect() as conn:
            conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
            conn.commit()
        click.echo('✅ تم حذف جدول alembic_version')
        
        # حذف مجلد versions فقط
        versions_path = 'migrations/versions'
        if os.path.exists(versions_path):
            shutil.rmtree(versions_path)
            os.makedirs(versions_path)
            click.echo('✅ تم تنظيف مجلد versions')
        
        # إنشاء migration جديد
        os.system('flask db migrate -m "Fix migrations"')
        os.system('flask db upgrade')
        
        click.echo('✅ تم إصلاح migrations بنجاح!')
        
    except Exception as e:
        click.echo(f'❌ حدث خطأ: {str(e)}', err=True)
        return


@click.command()
@with_appcontext
def clean_migrations():
    """تنظيف migrations القديمة والبدء من جديد"""
    if not click.confirm('⚠️  سيتم حذف جميع ملفات migrations. هل أنت متأكد؟'):
        click.echo('❌ تم إلغاء العملية')
        return
    
    try:
        # حذف جدول alembic_version
        with db.engine.connect() as conn:
            conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
            conn.commit()
        click.echo('✅ تم حذف جدول alembic_version')
        
        # حذف مجلد migrations بالكامل
        if os.path.exists('migrations'):
            shutil.rmtree('migrations')
            click.echo('✅ تم حذف مجلد migrations')
        
        # إعادة تهيئة migrations
        os.system('flask db init')
        click.echo('✅ تم إعادة تهيئة migrations')
        
        # إنشاء migration أول
        os.system('flask db migrate -m "Initial migration"')
        os.system('flask db upgrade')
        
        click.echo('\n✅ تم تنظيف وإعادة إنشاء migrations بنجاح!')
        
    except Exception as e:
        click.echo(f'❌ حدث خطأ: {str(e)}', err=True)
        return


@click.command()
@with_appcontext
def init_db():
    """تهيئة قاعدة البيانات بدون حذف البيانات الموجودة"""
    click.echo('🏗️  تهيئة قاعدة البيانات...')
    
    try:
        # إنشاء الجداول فقط إذا لم تكن موجودة
        db.create_all()
        click.echo('✅ تم إنشاء الجداول بنجاح')
        
        # تهيئة migrations إذا لم تكن موجودة
        if not os.path.exists('migrations'):
            os.system('flask db init')
            click.echo('✅ تم تهيئة Flask-Migrate')
        
        click.echo('\n✅ تمت تهيئة قاعدة البيانات بنجاح!')
        
    except Exception as e:
        click.echo(f'❌ حدث خطأ: {str(e)}', err=True)
        return


@click.command()
@click.option('--message', '-m', default='Update migration', help='رسالة وصف التحديث')
@with_appcontext
def fresh_migrate(message):
    """إنشاء migration جديد بعد حذف القديم"""
    click.echo('🔄 إنشاء migration جديد...')
    
    try:
        # حذف ملفات migration القديمة
        versions_path = 'migrations/versions'
        if os.path.exists(versions_path):
            files_deleted = 0
            for filename in os.listdir(versions_path):
                if filename.endswith('.py') and not filename.startswith('__'):
                    file_path = os.path.join(versions_path, filename)
                    os.remove(file_path)
                    files_deleted += 1
            
            if files_deleted > 0:
                click.echo(f'✅ تم حذف {files_deleted} ملفات migration قديمة')
        
        # إنشاء migration جديد
        os.system(f'flask db migrate -m "{message}"')
        click.echo('✅ تم إنشاء migration جديد')
        
        # تطبيق migration
        os.system('flask db upgrade')
        click.echo('✅ تم تطبيق migration')
        
        click.echo('\n✅ تم إنشاء وتطبيق migration بنجاح!')
        
    except Exception as e:
        click.echo(f'❌ حدث خطأ: {str(e)}', err=True)
        return


@click.command()
@with_appcontext
def show_tables():
    """عرض قائمة بجميع الجداول في قاعدة البيانات"""
    click.echo('📋 الجداول الموجودة في قاعدة البيانات:')
    
    try:
        # الحصول على أسماء الجداول من SQL Server
        result = db.session.execute(text("""
            SELECT TABLE_NAME 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_TYPE = 'BASE TABLE' 
            AND TABLE_CATALOG = DB_NAME()
            ORDER BY TABLE_NAME
        """))
        
        tables = [row[0] for row in result]
        
        if tables:
            for i, table in enumerate(tables, 1):
                click.echo(f'  {i}. {table}')
            click.echo(f'\n📊 المجموع: {len(tables)} جدول')
        else:
            click.echo('❌ لا توجد جداول في قاعدة البيانات')
            
    except Exception as e:
        click.echo(f'❌ حدث خطأ: {str(e)}', err=True)
        return


@click.command()
@click.option('--table', '-t', help='اسم الجدول المحدد')
@with_appcontext
def clear_table(table):
    """حذف جميع البيانات من جدول محدد أو جميع الجداول"""
    
    if table:
        # حذف بيانات جدول محدد
        if not click.confirm(f'⚠️  سيتم حذف جميع البيانات من جدول {table}. هل أنت متأكد؟'):
            click.echo('❌ تم إلغاء العملية')
            return
            
        try:
            # استخدام TRUNCATE للأداء الأفضل
            db.session.execute(text(f'TRUNCATE TABLE {table}'))
            db.session.commit()
            click.echo(f'✅ تم حذف جميع البيانات من جدول {table}')
        except Exception as e:
            # في حالة فشل TRUNCATE، استخدم DELETE
            try:
                db.session.execute(text(f'DELETE FROM {table}'))
                db.session.commit()
                click.echo(f'✅ تم حذف جميع البيانات من جدول {table}')
            except Exception as ex:
                click.echo(f'❌ حدث خطأ: {str(ex)}', err=True)
                db.session.rollback()
    else:
        # حذف بيانات جميع الجداول
        if not click.confirm('⚠️  سيتم حذف جميع البيانات من جميع الجداول. هل أنت متأكد؟'):
            click.echo('❌ تم إلغاء العملية')
            return
            
        try:
            # الحصول على أسماء الجداول
            result = db.session.execute(text("""
                SELECT TABLE_NAME 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_TYPE = 'BASE TABLE' 
                AND TABLE_CATALOG = DB_NAME()
                ORDER BY TABLE_NAME
            """))
            
            tables = [row[0] for row in result]
            
            for table in tables:
                if table != 'alembic_version':  # لا نحذف جدول migrations
                    try:
                        db.session.execute(text(f'DELETE FROM {table}'))
                        click.echo(f'✅ تم حذف البيانات من جدول {table}')
                    except Exception as e:
                        click.echo(f'⚠️  تحذير عند حذف {table}: {str(e)}')
            
            db.session.commit()
            click.echo('\n✅ تم حذف جميع البيانات بنجاح!')
            
        except Exception as e:
            click.echo(f'❌ حدث خطأ: {str(e)}', err=True)
            db.session.rollback()


@click.command()
@with_appcontext
def seed_db():
    """ملء قاعدة البيانات ببيانات تجريبية"""
    click.echo('🌱 إضافة بيانات تجريبية...')
    
    try:
        from app.models.user import User
        from app.models.employee import Employee
        from app.models.department import Department
        from app.models.branch import Branch
        
        # إضافة مستخدم super admin
        admin = User(
            username='admin',
            user_type='super_admin',
            is_active=True
        )
        admin.set_password('admin123')
        db.session.add(admin)
        
        # إضافة فرع تجريبي
        branch = Branch(
            name='الفرع الرئيسي',
            address='القاهرة',
            phone='0123456789'
        )
        db.session.add(branch)
        
        # إضافة قسم تجريبي
        department = Department(
            name='قسم الموارد البشرية',
            description='قسم إدارة شؤون الموظفين'
        )
        db.session.add(department)
        
        db.session.commit()
        click.echo('✅ تمت إضافة البيانات التجريبية بنجاح!')
        
    except Exception as e:
        click.echo(f'❌ حدث خطأ: {str(e)}', err=True)
        db.session.rollback()



@click.command()
@with_appcontext
def check_connection():
    """التحقق من اتصال قاعدة البيانات وعرض معلومات الاتصال"""
    click.echo('🔍 فحص اتصال قاعدة البيانات...')
    
    try:
        # الحصول على معلومات قاعدة البيانات
        result = db.session.execute(text("""
            SELECT 
                DB_NAME() as database_name,
                SUSER_SNAME() as login_user,
                @@SERVERNAME as server_name,
                @@VERSION as server_version
        """))
        
        info = result.fetchone()
        
        click.echo(f'\n✅ الاتصال ناجح!')
        click.echo(f'📊 قاعدة البيانات الحالية: {info[0]}')
        click.echo(f'👤 المستخدم الحالي: {info[1]}')
        click.echo(f'🖥️  اسم السيرفر: {info[2]}')
        click.echo(f'📋 إصدار SQL Server: {info[3][:50]}...')
        
        # عرض الجداول الموجودة
        tables_result = db.session.execute(text("""
            SELECT TABLE_NAME 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_NAME
        """))
        
        tables = [row[0] for row in tables_result]
        
        click.echo(f'\n📋 الجداول الموجودة ({len(tables)}):')
        for table in tables:
            click.echo(f'  - {table}')
            
    except Exception as e:
        click.echo(f'❌ خطأ في الاتصال: {str(e)}', err=True)
        return

@click.command()
@with_appcontext
def test_users():
    """اختبار جدول المستخدمين"""
    click.echo('🧪 اختبار جدول المستخدمين...')
    
    try:
        from app.models.user import User
        
        # عرض جميع المستخدمين
        users = User.query.all()
        
        if users:
            click.echo(f'\n👥 المستخدمون ({len(users)}):')
            for user in users:
                click.echo(f'  - {user.username} ({user.user_type})')
        else:
            click.echo('❌ لا يوجد مستخدمون في قاعدة البيانات')
            
            # إنشاء مستخدم admin
            if click.confirm('هل تريد إنشاء مستخدم admin؟'):
                admin = User(
                    username='admin',
                    user_type='super_admin',
                    is_active=True
                )
                admin.set_password('admin123')
                db.session.add(admin)
                db.session.commit()
                click.echo('✅ تم إنشاء مستخدم admin بنجاح')
                
    except Exception as e:
        click.echo(f'❌ خطأ: {str(e)}', err=True)
        return
    
    """اختبار جدول المستخدمين"""
    click.echo('🧪 اختبار جدول المستخدمين...')
    
    try:
        from app.models.user import User
        
        # عرض جميع المستخدمين
        users = User.query.all()
        
        if users:
            click.echo(f'\n👥 المستخدمون ({len(users)}):')
            for user in users:
                click.echo(f'  - {user.username} ({user.user_type})')
        else:
            click.echo('❌ لا يوجد مستخدمون في قاعدة البيانات')
            
            # إنشاء مستخدم admin
            if click.confirm('هل تريد إنشاء مستخدم admin؟'):
                admin = User(
                    username='admin',
                    user_type='super_admin',
                    is_active=True
                )
                admin.set_password('admin123')
                db.session.add(admin)
                db.session.commit()
                click.echo('✅ تم إنشاء مستخدم admin بنجاح')
                
    except Exception as e:
        click.echo(f'❌ خطأ: {str(e)}', err=True)
        return
from datetime import datetime, timedelta
import random
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


@click.command()
@with_appcontext
def seed_db():
    """ملء قاعدة البيانات ببيانات تجريبية كاملة للفروع والأقسام والموظفين والمستخدمين"""
    click.echo('🌱 إضافة بيانات تجريبية كاملة للنظام...')
    
    try:
        from app.models.user import User
        from app.models.employee import Employee
        from app.models.department import Department
        from app.models.branch import Branch
        from app.models.job_title import JobTitle
        
        # تنظيف البيانات الموجودة إذا كان المستخدم يريد ذلك
        if click.confirm('⚠️ هل تريد حذف كل البيانات الموجودة قبل إضافة البيانات التجريبية؟'):
            # حذف المستخدمين والموظفين والأقسام والفروع
            User.query.delete()
            Employee.query.delete()
            # حذف العلاقة بين الفروع والأقسام
            db.session.execute(text('DELETE FROM branch_departments'))
            Department.query.delete()
            Branch.query.delete()
            # حذف المسميات الوظيفية
            JobTitle.query.delete()
            db.session.commit()
            click.echo('✅ تم حذف البيانات الموجودة بنجاح')
        
        # ======= إضافة المسميات الوظيفية =======
        job_titles_data = [
            {'title_name': 'مدير عام', 'allowed_break_time': '01:00', 'overtime_hour_value': 15.00, 'delay_minute_value': 1.00, 'production_system': False, 'shift_system': False, 'month_system': True},
            {'title_name': 'مدير فرع', 'allowed_break_time': '01:00', 'overtime_hour_value': 12.00, 'delay_minute_value': 1.00, 'production_system': False, 'shift_system': False, 'month_system': True},
            {'title_name': 'رئيس قسم', 'allowed_break_time': '00:45', 'overtime_hour_value': 10.00, 'delay_minute_value': 0.75, 'production_system': False, 'shift_system': False, 'month_system': True},
            {'title_name': 'نائب مدير فرع', 'allowed_break_time': '00:45', 'overtime_hour_value': 10.00, 'delay_minute_value': 0.75, 'production_system': False, 'shift_system': False, 'month_system': True},
            {'title_name': 'نائب رئيس قسم', 'allowed_break_time': '00:45', 'overtime_hour_value': 8.00, 'delay_minute_value': 0.50, 'production_system': False, 'shift_system': False, 'month_system': True},
            {'title_name': 'محاسب', 'allowed_break_time': '00:30', 'overtime_hour_value': 7.00, 'delay_minute_value': 0.50, 'production_system': False, 'shift_system': False, 'month_system': True},
            {'title_name': 'مطور برامج', 'allowed_break_time': '00:30', 'overtime_hour_value': 8.00, 'delay_minute_value': 0.50, 'production_system': False, 'shift_system': False, 'month_system': True},
            {'title_name': 'فني صيانة', 'allowed_break_time': '00:30', 'overtime_hour_value': 6.00, 'delay_minute_value': 0.40, 'production_system': False, 'shift_system': True, 'month_system': False},
            {'title_name': 'موظف استقبال', 'allowed_break_time': '00:30', 'overtime_hour_value': 5.00, 'delay_minute_value': 0.30, 'production_system': False, 'shift_system': True, 'month_system': False},
            {'title_name': 'مندوب مبيعات', 'allowed_break_time': '00:30', 'overtime_hour_value': 6.00, 'delay_minute_value': 0.40, 'production_system': True, 'shift_system': False, 'month_system': False, 'production_piece_value': 5.00},
            {'title_name': 'مسؤول مشتريات', 'allowed_break_time': '00:30', 'overtime_hour_value': 7.00, 'delay_minute_value': 0.50, 'production_system': False, 'shift_system': False, 'month_system': True}
        ]
        
        job_titles = {}
        for job_data in job_titles_data:
            job = JobTitle(**job_data)
            db.session.add(job)
            db.session.flush()  # للحصول على معرف الوظيفة بعد الإضافة
            job_titles[job_data['title_name']] = job.id
        
        click.echo('✅ تم إضافة المسميات الوظيفية')
        
        # ======= إضافة فروع الشركة =======
        branches_data = [
            {'name': 'الفرع الرئيسي', 'address': 'طرابلس - شارع الاستقلال', 'phone': '0911234567', 'email': 'main@company.ly'},
            {'name': 'فرع بنغازي', 'address': 'بنغازي - وسط المدينة', 'phone': '0921234567', 'email': 'benghazi@company.ly'},
            {'name': 'فرع مصراتة', 'address': 'مصراتة - شارع الصناعة', 'phone': '0941234567', 'email': 'misrata@company.ly'},
            {'name': 'فرع الزاوية', 'address': 'الزاوية - طريق الساحل', 'phone': '0951234567', 'email': 'zawiya@company.ly'}
        ]
        
        branches = {}
        for branch_data in branches_data:
            branch = Branch(**branch_data)
            db.session.add(branch)
            db.session.flush()
            branches[branch_data['name']] = branch
        
        click.echo('✅ تم إضافة الفروع')
        
        # ======= إضافة أقسام الشركة =======
        departments_data = [
            {'name': 'الإدارة العليا', 'description': 'قسم الإدارة العليا للشركة'},
            {'name': 'الموارد البشرية', 'description': 'إدارة شؤون الموظفين والتوظيف'},
            {'name': 'المالية والمحاسبة', 'description': 'إدارة الشؤون المالية والحسابية'},
            {'name': 'تقنية المعلومات', 'description': 'قسم البرمجيات والدعم الفني'},
            {'name': 'المبيعات والتسويق', 'description': 'قسم المبيعات وخدمة العملاء'},
            {'name': 'العمليات والصيانة', 'description': 'إدارة عمليات الشركة والصيانة'},
            {'name': 'المستودعات', 'description': 'إدارة المخازن والمستودعات'}
        ]
        
        departments = {}
        for dept_data in departments_data:
            department = Department(**dept_data)
            db.session.add(department)
            db.session.flush()
            departments[dept_data['name']] = department
            
            # ربط الأقسام بالفروع المناسبة
            for branch in branches.values():
                # قسم الإدارة العليا فقط في الفرع الرئيسي
                if dept_data['name'] == 'الإدارة العليا' and branch.name != 'الفرع الرئيسي':
                    continue
                    
                # كل الفروع يحتوي على جميع الأقسام الأخرى
                department.branches.append(branch)
        
        click.echo('✅ تم إضافة الأقسام وربطها بالفروع')
        
        # ======= إضافة مستخدم super admin =======
        admin = User(
            username='admin',
            user_type='super_admin',
            is_active=True
        )
        admin.set_password('admin123')
        db.session.add(admin)
        click.echo('✅ تم إضافة مستخدم super admin')
        
        # ======= إضافة موظفين ومستخدمين رؤساء الأقسام ونوابهم =======
        # قائمة بالأسماء التجريبية للموظفين - زيادة عدد الأسماء
        names = [
            'محمد علي', 'أحمد سليمان', 'خالد عبدالله', 'عمر مبارك', 'يوسف سالم',
            'علي حسين', 'إبراهيم محمد', 'سعيد عمران', 'زياد كريم', 'ياسر جمال',
            'حسن صلاح', 'مصطفى رشيد', 'سليم جمعة', 'عبدالرحمن عادل', 'طارق سمير',
            'آدم حسام', 'فادي وائل', 'رامي صبري', 'نادر أنور', 'كريم حاتم',
            'أنس محمود', 'عماد سامي', 'وليد ناصر', 'باسم طارق', 'فارس عثمان',
            'أحمد هاني', 'محمد نبيل', 'عمر ياسين', 'سامر جلال', 'علاء الدين محمد',
            'خالد سامي', 'أشرف عبدالله', 'نبيل فوزي', 'ماجد صبري', 'مراد فتحي',
            'مؤيد كامل', 'عاصم حامد', 'شريف منير', 'فؤاد زكريا', 'مجدي عادل',
            'يحيى سليم', 'رأفت جمال', 'نبيل صادق', 'ماهر سعيد', 'جابر أحمد',
            'هشام أمين', 'صفوت مجدي', 'هاني وائل', 'إيهاب نبيل', 'أسامة فريد',
            'عادل حمدي', 'معتز محمود', 'أدهم كامل', 'حسام عبدالرحمن', 'فهد سالم',
            'وائل رفعت', 'رضا محمد', 'لؤي أحمد', 'باسل فريد', 'تامر نبيل',
            'رشاد حسن', 'كمال فاروق', 'ناجي مصطفى', 'نزار جميل', 'فارس عماد'
        ]
        
        # قائمة بأرقام البطاقات وزيادة عددها
        id_cards = ['ID' + str(x).zfill(8) for x in range(1, 200)]
        # قائمة بالأرقام الوطنية وزيادة عددها
        national_ids = ['N' + str(x).zfill(10) for x in range(1, 200)]
        
        # خلط الأسماء وأرقام البطاقات للتنوع
        random.shuffle(names)
        random.shuffle(id_cards)
        random.shuffle(national_ids)
        
        # تاريخ اليوم للاستخدام في التواريخ
        today = datetime.now().date()
        
        employees = []
        
        # مؤشرات للأسماء والبطاقات
        name_index = 0
        id_index = 0
        
        # التأكد من عدم تجاوز حدود القوائم
        max_employees = min(len(names), len(id_cards), len(national_ids))
        
        # ضبط عدد الموظفين لكل قسم وفرع
        max_dept_employees = 3  # تقليل عدد الموظفين في القسم الواحد
        
        # ======= إضافة رؤساء الفروع ونوابهم =======
        click.echo('🏢 إضافة رؤساء الفروع ونوابهم...')
        
        for branch_name, branch in branches.items():
            # تحقق من عدم تجاوز حدود القوائم
            if name_index >= max_employees or id_index >= max_employees:
                click.echo('⚠️ تم الوصول إلى الحد الأقصى للموظفين المتاحين')
                break
                
            # إضافة رئيس الفرع
            branch_head = Employee(
                fingerprint_id=f'BH{branch.id}',
                full_name=names[name_index],
                employee_type='permanent',
                branch_id=branch.id,
                department_id=departments['الإدارة العليا'].id if branch_name == 'الفرع الرئيسي' else None,
                position=job_titles['مدير فرع'],
                salary=random.randint(4000, 5000),
                date_of_birth=today - timedelta(days=365*random.randint(35, 50)),
                id_card_number=id_cards[id_index],
                national_id=national_ids[id_index],
                mobile_1=f'091{random.randint(1000000, 9999999)}',
                date_of_joining=today - timedelta(days=random.randint(365, 1825)),
                work_system='دوام كامل'
            )
            db.session.add(branch_head)
            db.session.flush()
            employees.append(branch_head)
            name_index += 1
            id_index += 1
            
            # إضافة مستخدم لرئيس الفرع
            branch_head_user = User(
                username=f'branch_head_{branch.id}',
                user_type='branch_head',
                employee_id=branch_head.id,
                branch_id=branch.id,
                is_active=True
            )
            branch_head_user.set_password('password123')
            db.session.add(branch_head_user)
            
            # تحقق من عدم تجاوز حدود القوائم
            if name_index >= max_employees or id_index >= max_employees:
                click.echo('⚠️ تم الوصول إلى الحد الأقصى للموظفين المتاحين')
                continue
                
            # إضافة نائب رئيس الفرع
            branch_deputy = Employee(
                fingerprint_id=f'BD{branch.id}',
                full_name=names[name_index],
                employee_type='permanent',
                branch_id=branch.id,
                department_id=departments['الإدارة العليا'].id if branch_name == 'الفرع الرئيسي' else None,
                position=job_titles['نائب مدير فرع'],
                salary=random.randint(3000, 3800),
                date_of_birth=today - timedelta(days=365*random.randint(30, 45)),
                id_card_number=id_cards[id_index],
                national_id=national_ids[id_index],
                mobile_1=f'091{random.randint(1000000, 9999999)}',
                date_of_joining=today - timedelta(days=random.randint(365, 1095)),
                work_system='دوام كامل'
            )
            db.session.add(branch_deputy)
            db.session.flush()
            employees.append(branch_deputy)
            name_index += 1
            id_index += 1
            
            # إضافة مستخدم لنائب رئيس الفرع
            branch_deputy_user = User(
                username=f'branch_deputy_{branch.id}',
                user_type='branch_deputy',
                employee_id=branch_deputy.id,
                branch_id=branch.id,
                is_active=True
            )
            branch_deputy_user.set_password('password123')
            db.session.add(branch_deputy_user)
        
        # ======= إضافة رؤساء الأقسام ونوابهم =======
        click.echo('🏢 إضافة رؤساء الأقسام ونوابهم...')
        
        for dept_name, department in departments.items():
            # نحصل على الفروع المرتبطة بهذا القسم
            dept_branches = list(branch for branch in department.branches)
            
            # إذا لم يكن هناك فروع مرتبطة بالقسم، نتخطى
            if not dept_branches:
                continue
                
            # نختار فرع واحد ليكون مقر القسم الرئيسي (أول فرع مرتبط)
            main_branch = dept_branches[0]
            
            # تحقق من عدم تجاوز حدود القوائم
            if name_index >= max_employees or id_index >= max_employees:
                click.echo('⚠️ تم الوصول إلى الحد الأقصى للموظفين المتاحين')
                break
                
            # إضافة رئيس القسم
            dept_head = Employee(
                fingerprint_id=f'DH{department.id}',
                full_name=names[name_index],
                employee_type='permanent',
                branch_id=main_branch.id,
                department_id=department.id,
                position=job_titles['رئيس قسم'],
                salary=random.randint(3500, 4200),
                date_of_birth=today - timedelta(days=365*random.randint(30, 45)),
                id_card_number=id_cards[id_index],
                national_id=national_ids[id_index],
                mobile_1=f'092{random.randint(1000000, 9999999)}',
                date_of_joining=today - timedelta(days=random.randint(365, 1095)),
                work_system='دوام كامل'
            )
            db.session.add(dept_head)
            db.session.flush()
            employees.append(dept_head)
            name_index += 1
            id_index += 1
            
            # إضافة مستخدم لرئيس القسم
            dept_head_user = User(
                username=f'dept_head_{department.id}',
                user_type='department_head',
                employee_id=dept_head.id,
                department_id=department.id,
                branch_id=main_branch.id,
                is_active=True
            )
            dept_head_user.set_password('password123')
            db.session.add(dept_head_user)
            
            # تحقق من عدم تجاوز حدود القوائم
            if name_index >= max_employees or id_index >= max_employees:
                click.echo('⚠️ تم الوصول إلى الحد الأقصى للموظفين المتاحين')
                continue
                
            # إضافة نائب رئيس القسم
            dept_deputy = Employee(
                fingerprint_id=f'DD{department.id}',
                full_name=names[name_index],
                employee_type='permanent',
                branch_id=main_branch.id,
                department_id=department.id,
                position=job_titles['نائب رئيس قسم'],
                salary=random.randint(2800, 3400),
                date_of_birth=today - timedelta(days=365*random.randint(28, 40)),
                id_card_number=id_cards[id_index],
                national_id=national_ids[id_index],
                mobile_1=f'092{random.randint(1000000, 9999999)}',
                date_of_joining=today - timedelta(days=random.randint(180, 730)),
                work_system='دوام كامل'
            )
            db.session.add(dept_deputy)
            db.session.flush()
            employees.append(dept_deputy)
            name_index += 1
            id_index += 1
            
            # إضافة مستخدم لنائب رئيس القسم
            dept_deputy_user = User(
                username=f'dept_deputy_{department.id}',
                user_type='department_deputy',
                employee_id=dept_deputy.id,
                department_id=department.id,
                branch_id=main_branch.id,
                is_active=True
            )
            dept_deputy_user.set_password('password123')
            db.session.add(dept_deputy_user)
            
            # ======= إضافة موظفين عاديين للقسم في الفروع المختلفة =======
            # توزيع الموظفين على الفروع المختلفة للقسم
            positions = [pos for pos_name, pos in job_titles.items() 
                        if pos_name not in ['مدير عام', 'مدير فرع', 'رئيس قسم', 'نائب مدير فرع', 'نائب رئيس قسم']]
            
            for branch in dept_branches:
                # عدد الموظفين حسب القسم والفرع (تقليل العدد)
                if dept_name == 'الإدارة العليا':
                    num_employees = 1  # عدد قليل للإدارة العليا
                elif dept_name in ['الموارد البشرية', 'المالية والمحاسبة']:
                    num_employees = min(2, max_dept_employees)
                else:
                    num_employees = min(3, max_dept_employees)
                
                for _ in range(num_employees):
                    # تحقق من عدم تجاوز حدود القوائم
                    if name_index >= max_employees or id_index >= max_employees:
                        click.echo('⚠️ تم الوصول إلى الحد الأقصى للموظفين المتاحين')
                        break
                    
                    # اختيار مسمى وظيفي مناسب للقسم
                    if dept_name == 'المالية والمحاسبة':
                        position = job_titles['محاسب']
                    elif dept_name == 'تقنية المعلومات':
                        position = job_titles['مطور برامج']
                    elif dept_name == 'العمليات والصيانة':
                        position = job_titles['فني صيانة']
                    elif dept_name == 'المبيعات والتسويق':
                        position = job_titles['مندوب مبيعات']
                    else:
                        position = random.choice(positions)
                    
                    # إنشاء موظف عادي
                    employee = Employee(
                        fingerprint_id=f'E{department.id}{branch.id}{random.randint(100, 999)}',
                        full_name=names[name_index],
                        employee_type='permanent',
                        branch_id=branch.id,
                        department_id=department.id,
                        position=position,
                        salary=random.randint(1500, 2800),
                        date_of_birth=today - timedelta(days=365*random.randint(25, 45)),
                        id_card_number=id_cards[id_index],
                        national_id=national_ids[id_index],
                        mobile_1=f'09{random.randint(10000000, 99999999)}',
                        date_of_joining=today - timedelta(days=random.randint(30, 730)),
                        work_system=random.choice(['دوام كامل', 'دوام جزئي'])
                    )
                    db.session.add(employee)
                    db.session.flush()
                    employees.append(employee)
                    name_index += 1
                    id_index += 1
                    
                    # إنشاء حساب مستخدم لبعض الموظفين (تقليل النسبة: 1:5)
                    if random.randint(1, 5) == 1:
                        employee_user = User(
                            username=f'employee_{employee.id}',
                            user_type='employee',
                            employee_id=employee.id,
                            branch_id=branch.id,
                            department_id=department.id,
                            is_active=True
                        )
                        employee_user.set_password('password123')
                        db.session.add(employee_user)
        
        # ======= حفظ جميع التغييرات في قاعدة البيانات =======
        db.session.commit()
        
        # ======= عرض ملخص البيانات المضافة =======
        click.echo('\n✅ تمت إضافة البيانات التجريبية بنجاح!')
        click.echo(f'📊 الإحصائيات:')
        click.echo(f'  - الفروع: {len(branches)} فرع')
        click.echo(f'  - الأقسام: {len(departments)} قسم')
        click.echo(f'  - الموظفين: {len(employees)} موظف')
        click.echo(f'  - المستخدمين: {User.query.count()} مستخدم')
        click.echo(f'    - مدير النظام: 1 مستخدم')
        click.echo(f'    - رؤساء الفروع: {User.query.filter_by(user_type="branch_head").count()} مستخدم')
        click.echo(f'    - نواب رؤساء الفروع: {User.query.filter_by(user_type="branch_deputy").count()} مستخدم')
        click.echo(f'    - رؤساء الأقسام: {User.query.filter_by(user_type="department_head").count()} مستخدم')
        click.echo(f'    - نواب رؤساء الأقسام: {User.query.filter_by(user_type="department_deputy").count()} مستخدم')
        click.echo(f'    - موظفون عاديون: {User.query.filter_by(user_type="employee").count()} مستخدم')
        
        click.echo('\n🔑 معلومات تسجيل الدخول:')
        click.echo('  - مدير النظام: ')
        click.echo('      اسم المستخدم: admin')
        click.echo('      كلمة المرور: admin123')
        click.echo('  - رؤساء الفروع: ')
        click.echo('      اسم المستخدم: branch_head_[معرف الفرع]')
        click.echo('      كلمة المرور: password123')
        click.echo('  - رؤساء الأقسام: ')
        click.echo('      اسم المستخدم: dept_head_[معرف القسم]')
        click.echo('      كلمة المرور: password123')
        
    except Exception as e:
        db.session.rollback()
        click.echo(f'❌ حدث خطأ أثناء إضافة البيانات التجريبية: {str(e)}', err=True)
        return
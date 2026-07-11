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
    """ملء قاعدة البيانات ببيانات تجريبية كاملة للفروع والأقسام والموظفين والمستخدمين ومعاملات الغياب"""
    import random
    from datetime import datetime, timedelta
    from sqlalchemy import text
    
    click.echo('🌱 إضافة بيانات تجريبية كاملة للنظام...')
    try:
        from app.models.user import User
        from app.models.employee import Employee
        from app.models.department import Department
        from app.models.branch import Branch
        from app.models.job_title import JobTitle
        from app.models.reward import Reward
        from app.models.penalty import Penalty
        from app.models.advance import Advance
        from app.models.attendance import Attendance
        from app.models.attendance_type import AttendanceTypeEnum, AttendanceType
        from app.models.absence_transaction import AbsenceTransaction
        from app.models.absence_question import AbsenceQuestion
        from app.models.absence_answer import AbsenceAnswer
        from app.models.transaction_history import TransactionHistory

        # تنظيف البيانات الموجودة إذا كان المستخدم يريد ذلك
        if click.confirm('⚠️ هل تريد حذف كل البيانات الموجودة قبل إضافة البيانات التجريبية؟'):
            # حذف البيانات بالترتيب الصحيح لتجنب مشاكل Foreign Key
            TransactionHistory.query.delete()
            AbsenceAnswer.query.delete()
            AbsenceTransaction.query.delete()
            AbsenceQuestion.query.delete()
            User.query.delete()
            Employee.query.delete()
            Penalty.query.delete()
            Reward.query.delete()
            Advance.query.delete()
            Attendance.query.delete()
            db.session.execute(text('DELETE FROM branch_departments'))
            Department.query.delete()
            Branch.query.delete()
            JobTitle.query.delete()
            db.session.commit()
            click.echo('✅ تم حذف البيانات الموجودة بنجاح')

        # ======= إضافة أنواع المعاملات =======
        click.echo('📋 إضافة أنواع المعاملات...')
        transaction_types_data = [
            {
                'name': 'معاملة غياب',
                'code': 'ABSENCE',
                'description': 'معاملة تنشأ تلقائياً عند غياب الموظف',
                'auto_create': True
            },
            {
                'name': 'طلب إجازة',
                'code': 'LEAVE',
                'description': 'طلب إجازة من الموظف',
                'auto_create': False
            },
            {
                'name': 'طلب انتداب',
                'code': 'DELEGATION',
                'description': 'طلب انتداب خارجي',
                'auto_create': False
            }
        ]
        
        # transaction_types = {}
        # for type_data in transaction_types_data:
        #     trans_type = TransactionType(**type_data)
        #     db.session.add(trans_type)
        #     db.session.flush()
        #     transaction_types[type_data['code']] = trans_type
        # click.echo('✅ تم إضافة أنواع المعاملات')

        # ======= إضافة أسئلة الغياب =======
        click.echo('❓ إضافة أسئلة الغياب...')
        absence_questions_data = [
            {
                'question_text': 'هل تم الإبلاغ عن الغياب مسبقاً؟',
                'deduction_value': 0.5,
                'is_active': True
            },
            {
                'question_text': 'هل يوجد عذر طبي أو شرعي للغياب؟',
                'deduction_value': 0.5,
                'is_active': True
            },
            {
                'question_text': 'هل تم تعويض ساعات العمل المفقودة؟',
                'deduction_value': 0.25,
                'is_active': True
            },
            {
                'question_text': 'هل هذا الغياب متكرر خلال الشهر؟',
                'deduction_value': 1.0,
                'is_active': True
            },
            {
                'question_text': 'هل تم إنجاز المهام المطلوبة قبل الغياب؟',
                'deduction_value': 0.25,
                'is_active': True
            }
        ]
        
        absence_questions = []
        for question_data in absence_questions_data:
            question = AbsenceQuestion(**question_data)
            db.session.add(question)
            db.session.flush()
            absence_questions.append(question)
        click.echo('✅ تم إضافة أسئلة الغياب')

        # ======= إضافة المسميات الوظيفية =======
        job_titles_data = [
            {'title_name': 'مدير عام', 'allowed_break_time': '01:00', 'overtime_hour_value': 15.00,
             'delay_minute_value': 1.00, 'production_system': False, 'shift_system': False, 'month_system': True},
            {'title_name': 'مدير فرع', 'allowed_break_time': '01:00', 'overtime_hour_value': 12.00,
             'delay_minute_value': 1.00, 'production_system': False, 'shift_system': False, 'month_system': True},
            {'title_name': 'رئيس قسم', 'allowed_break_time': '00:45', 'overtime_hour_value': 10.00,
             'delay_minute_value': 0.75, 'production_system': False, 'shift_system': False, 'month_system': True},
            {'title_name': 'نائب مدير فرع', 'allowed_break_time': '00:45', 'overtime_hour_value': 10.00,
             'delay_minute_value': 0.75, 'production_system': False, 'shift_system': False, 'month_system': True},
            {'title_name': 'نائب رئيس قسم', 'allowed_break_time': '00:45', 'overtime_hour_value': 8.00,
             'delay_minute_value': 0.50, 'production_system': False, 'shift_system': False, 'month_system': True},
            {'title_name': 'محاسب', 'allowed_break_time': '00:30', 'overtime_hour_value': 7.00,
             'delay_minute_value': 0.50, 'production_system': False, 'shift_system': False, 'month_system': True},
            {'title_name': 'مطور برامج', 'allowed_break_time': '00:30', 'overtime_hour_value': 8.00,
             'delay_minute_value': 0.50, 'production_system': False, 'shift_system': False, 'month_system': True},
            {'title_name': 'فني صيانة', 'allowed_break_time': '00:30', 'overtime_hour_value': 6.00,
             'delay_minute_value': 0.40, 'production_system': False, 'shift_system': True, 'month_system': False},
            {'title_name': 'موظف استقبال', 'allowed_break_time': '00:30', 'overtime_hour_value': 5.00,
             'delay_minute_value': 0.30, 'production_system': False, 'shift_system': True, 'month_system': False},
            {'title_name': 'مندوب مبيعات', 'allowed_break_time': '00:30', 'overtime_hour_value': 6.00,
             'delay_minute_value': 0.40, 'production_system': True, 'shift_system': False, 'month_system': False,
             'production_piece_value': 5.00},
            {'title_name': 'مسؤول مشتريات', 'allowed_break_time': '00:30', 'overtime_hour_value': 7.00,
             'delay_minute_value': 0.50, 'production_system': False, 'shift_system': False, 'month_system': True}
        ]
        job_titles = {}
        for job_data in job_titles_data:
            job = JobTitle(**job_data)
            db.session.add(job)
            db.session.flush()
            job_titles[job_data['title_name']] = job.id
        click.echo('✅ تم إضافة المسميات الوظيفية')

        # ======= إضافة فروع الشركة =======
        branches_data = [
            {'name': 'الفرع الرئيسي', 'address': 'طرابلس - شارع الاستقلال', 'phone': '0911234567',
             'email': 'main@company.ly'},
            {'name': 'فرع بنغازي', 'address': 'بنغازي - وسط المدينة', 'phone': '0921234567',
             'email': 'benghazi@company.ly'},
            {'name': 'فرع مصراتة', 'address': 'مصراتة - شارع الصناعة', 'phone': '0941234567',
             'email': 'misrata@company.ly'},
            {'name': 'فرع الزاوية', 'address': 'الزاوية - طريق الساحل', 'phone': '0951234567',
             'email': 'zawiya@company.ly'}
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
        id_cards = ['ID' + str(x).zfill(8) for x in range(1, 200)]
        national_ids = ['N' + str(x).zfill(10) for x in range(1, 200)]
        random.shuffle(names)
        random.shuffle(id_cards)
        random.shuffle(national_ids)

        today = datetime.now().date()
        employees = []
        users = []  # قائمة المستخدمين للاستخدام في معاملات الغياب
        name_index = 0
        id_index = 0
        max_employees = min(len(names), len(id_cards), len(national_ids))

        click.echo('🏢 إضافة رؤساء الفروع ونوابهم...')
        branch_list = list(branches.values())

        # إنشاء رئيس فرع عادي لكل فرع
        for i, (branch_name, branch) in enumerate(branches.items()):
            if name_index >= max_employees or id_index >= max_employees:
                break
                
            branch_head = Employee(
                fingerprint_id=f'BH{branch.id}',
                full_name=names[name_index],
                employee_type='permanent',
                branch_id=branch.id,
                department_id=departments['الإدارة العليا'].id if branch_name == 'الفرع الرئيسي' else None,
                position=job_titles['مدير فرع'],
                salary=random.randint(4000, 5000),
                date_of_birth=today - timedelta(days=365 * random.randint(35, 50)),
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

            branch_head_user = User(
                username=f'branch_head_{branch.id}',
                user_type='branch_head',
                employee_id=branch_head.id,
                branch_id=branch.id,  # للتوافق مع النظام القديم
                is_active=True
            )
            branch_head_user.set_password('password123')
            db.session.add(branch_head_user)
            db.session.flush()
            
            # إضافة إدارة الفرع في النظام الجديد
            branch_head_user.add_branch_management(branch.id, 'head')
            users.append(branch_head_user)

            # إضافة نائب رئيس فرع عادي
            if name_index < max_employees and id_index < max_employees:
                branch_deputy = Employee(
                    fingerprint_id=f'BD{branch.id}',
                    full_name=names[name_index],
                    employee_type='permanent',
                    branch_id=branch.id,
                    department_id=departments['الإدارة العليا'].id if branch_name == 'الفرع الرئيسي' else None,
                    position=job_titles['نائب مدير فرع'],
                    salary=random.randint(3000, 3800),
                    date_of_birth=today - timedelta(days=365 * random.randint(30, 45)),
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

                branch_deputy_user = User(
                    username=f'branch_deputy_{branch.id}',
                    user_type='branch_deputy',
                    employee_id=branch_deputy.id,
                    branch_id=branch.id,
                    is_active=True
                )
                branch_deputy_user.set_password('password123')
                db.session.add(branch_deputy_user)
                db.session.flush()
                
                # إضافة إدارة الفرع في النظام الجديد
                branch_deputy_user.add_branch_management(branch.id, 'deputy')
                users.append(branch_deputy_user)

        # ======= إضافة رئيس يدير فرعين (حالة خاصة) =======
        if len(branch_list) >= 2 and name_index < max_employees and id_index < max_employees:
            click.echo('👨‍💼 إضافة رئيس يدير فرعين...')
            
            # اختيار فرعين مختلفين
            managed_branches = random.sample(branch_list, 2)
            
            multi_branch_head = Employee(
                fingerprint_id=f'MBH{random.randint(100, 999)}',
                full_name=names[name_index],
                employee_type='permanent',
                branch_id=managed_branches[0].id,  # مكان العمل الأساسي
                department_id=departments['الإدارة العليا'].id,
                position=job_titles['مدير عام'],  # منصب أعلى لأنه يدير فرعين
                salary=random.randint(5500, 6500),
                date_of_birth=today - timedelta(days=365 * random.randint(40, 55)),
                id_card_number=id_cards[id_index],
                national_id=national_ids[id_index],
                mobile_1=f'091{random.randint(1000000, 9999999)}',
                date_of_joining=today - timedelta(days=random.randint(730, 2555)),
                work_system='دوام كامل'
            )
            db.session.add(multi_branch_head)
            db.session.flush()
            employees.append(multi_branch_head)
            name_index += 1
            id_index += 1

            multi_branch_head_user = User(
                username=f'multi_branch_head_{multi_branch_head.id}',
                user_type='branch_head',
                employee_id=multi_branch_head.id,
                branch_id=managed_branches[0].id,  # للتوافق مع النظام القديم
                is_active=True
            )
            multi_branch_head_user.set_password('password123')
            db.session.add(multi_branch_head_user)
            db.session.flush()
            
            # إضافة إدارة الفرعين في النظام الجديد
            for branch in managed_branches:
                multi_branch_head_user.add_branch_management(branch.id, 'head')
            
            users.append(multi_branch_head_user)
            
            click.echo(f'✅ تم إنشاء رئيس يدير الفرعين: {managed_branches[0].name} و {managed_branches[1].name}')

            # ======= إضافة رؤساء الأقسام ونوابهم (محدث للنظام الجديد) =======
            click.echo('🏢 إضافة رؤساء الأقسام ونوابهم...')
            department_list = list(departments.values())

            # إنشاء رئيس قسم عادي لكل قسم
            for dept_name, department in departments.items():
                dept_branches = list(branch for branch in department.branches)
                if not dept_branches:
                    continue
                main_branch = dept_branches[0]
                
                if name_index >= max_employees or id_index >= max_employees:
                    break
                    
                dept_head = Employee(
                    fingerprint_id=f'DH{department.id}',
                    full_name=names[name_index],
                    employee_type='permanent',
                    branch_id=main_branch.id,
                    department_id=department.id,
                    position=job_titles['رئيس قسم'],
                    salary=random.randint(3500, 4200),
                    date_of_birth=today - timedelta(days=365 * random.randint(30, 45)),
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

                dept_head_user = User(
                    username=f'dept_head_{department.id}',
                    user_type='department_head',
                    employee_id=dept_head.id,
                    department_id=department.id,  # للتوافق مع النظام القديم
                    branch_id=main_branch.id,
                    is_active=True
                )
                dept_head_user.set_password('password123')
                db.session.add(dept_head_user)
                db.session.flush()
                
                # إضافة إدارة القسم في النظام الجديد
                dept_head_user.add_department_management(department.id, 'head')
                users.append(dept_head_user)

                # إضافة نائب رئيس قسم عادي
                if name_index < max_employees and id_index < max_employees:
                    dept_deputy = Employee(
                        fingerprint_id=f'DD{department.id}',
                        full_name=names[name_index],
                        employee_type='permanent',
                        branch_id=main_branch.id,
                        department_id=department.id,
                        position=job_titles['نائب رئيس قسم'],
                        salary=random.randint(2800, 3400),
                        date_of_birth=today - timedelta(days=365 * random.randint(28, 40)),
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
                    db.session.flush()
                    
                    # إضافة إدارة القسم في النظام الجديد
                    dept_deputy_user.add_department_management(department.id, 'deputy')
                    users.append(dept_deputy_user)

        # إضافة الموظفين العاديين في القسم...
        # [نفس الكود الموجود سابقاً لإضافة الموظفين العاديين]

        # ======= إضافة رئيس يدير قسمين (حالة خاصة) =======
        if len(department_list) >= 2 and name_index < max_employees and id_index < max_employees:
            click.echo('👨‍💼 إضافة رئيس يدير قسمين...')
            
            # اختيار قسمين مختلفين (تجنب الإدارة العليا)
            available_depts = [dept for dept in department_list if dept.name != 'الإدارة العليا']
            if len(available_depts) >= 2:
                managed_departments = random.sample(available_depts, 2)
                
                # اختيار فرع للعمل (من الفروع المتاحة للقسم الأول)
                main_dept = managed_departments[0]
                dept_branches = list(branch for branch in main_dept.branches)
                work_branch = dept_branches[0] if dept_branches else branch_list[0]
                
                multi_dept_head = Employee(
                    fingerprint_id=f'MDH{random.randint(100, 999)}',
                    full_name=names[name_index],
                    employee_type='permanent',
                    branch_id=work_branch.id,  # مكان العمل الأساسي
                    department_id=managed_departments[0].id,  # القسم الأساسي
                    position=job_titles['مدير عام'],  # منصب أعلى لأنه يدير قسمين
                    salary=random.randint(4800, 5800),
                    date_of_birth=today - timedelta(days=365 * random.randint(35, 50)),
                    id_card_number=id_cards[id_index],
                    national_id=national_ids[id_index],
                    mobile_1=f'092{random.randint(1000000, 9999999)}',
                    date_of_joining=today - timedelta(days=random.randint(730, 2190)),
                    work_system='دوام كامل'
                )
                db.session.add(multi_dept_head)
                db.session.flush()
                employees.append(multi_dept_head)
                name_index += 1
                id_index += 1

                multi_dept_head_user = User(
                    username=f'multi_dept_head_{multi_dept_head.id}',
                    user_type='department_head',
                    employee_id=multi_dept_head.id,
                    department_id=managed_departments[0].id,  # للتوافق مع النظام القديم
                    branch_id=work_branch.id,
                    is_active=True
                )
                multi_dept_head_user.set_password('password123')
                db.session.add(multi_dept_head_user)
                db.session.flush()
                
                # إضافة إدارة القسمين في النظام الجديد
                for dept in managed_departments:
                    multi_dept_head_user.add_department_management(dept.id, 'head')
                
                users.append(multi_dept_head_user)
                
                click.echo(f'✅ تم إنشاء رئيس يدير القسمين: {managed_departments[0].name} و {managed_departments[1].name}')


        # إضافة المستخدم الأدمن إلى قائمة المستخدمين
        users.append(admin)

        # ======= إضافة بيانات تجريبية للمكافآت =======
        click.echo('🏆 إضافة مكافآت تجريبية للموظفين...')
        for employee in employees:
            if random.random() < 0.7:
                reward = Reward(
                    date=today - timedelta(days=random.randint(1, 30)),
                    employee_id=employee.id,
                    amount=round(random.uniform(50, 500), 2),
                    document_number=f'REW-{random.randint(1000, 9999)}',
                    notes='مكافأة شهرية'
                )
                db.session.add(reward)
        click.echo('✅ تم إضافة المكافآت')

        # ======= إضافة بيانات تجريبية للجزاءات =======
        click.echo('⚖️ إضافة جزاءات تجريبية للموظفين...')
        for employee in employees:
            if random.random() < 0.5:
                penalty = Penalty(
                    date=today - timedelta(days=random.randint(1, 30)),
                    employee_id=employee.id,
                    amount=round(random.uniform(20, 200), 2),
                    document_number=f'PEN-{random.randint(1000, 9999)}',
                    notes='تأخر بدون عذر'
                )
                db.session.add(penalty)
        click.echo('✅ تم إضافة الجزاءات')

        # ======= إضافة بيانات تجريبية للسلف =======
        click.echo('💵 إضافة سلف تجريبية للموظفين...')
        for employee in employees:
            if random.random() < 0.6:
                advance = Advance(
                    date=today - timedelta(days=random.randint(1, 30)),
                    employee_id=employee.id,
                    amount=round(random.uniform(500, 2000), 2),
                    document_number=f'ADV-{random.randint(1000, 9999)}',
                    notes='سلفة شخصية'
                )
                db.session.add(advance)
        click.echo('✅ تم إضافة السلف')

        # ======= إضافة بيانات تجريبية للحضور والانصراف =======
        click.echo('📅 إضافة تسجيلات الحضور والانصراف...')
        from datetime import time
        attendance_types = list(AttendanceTypeEnum)
        for employee in employees:
            for day_offset in range(0, 30, random.choice([1, 2])):
                attendance_date = today - timedelta(days=day_offset)
                attendance_type = random.choice(attendance_types)
                check_in_time = None
                check_out_time = None
                if attendance_type == AttendanceTypeEnum.PRESENT:
                    check_in_time = time(random.randint(7, 9), random.randint(0, 59))
                    check_out_time = time(random.randint(14, 17), random.randint(0, 59))
                attendance = Attendance(
                    empId=employee.id,
                    createdAt=attendance_date,
                    checkInTime=check_in_time,
                    checkOutTime=check_out_time,
                    checkInReason="حضور طبيعي" if attendance_type == AttendanceTypeEnum.PRESENT else "غائب",
                    checkOutReason="انصراف طبيعي" if attendance_type == AttendanceTypeEnum.PRESENT else "غير متاح",
                    productionQuantity=random.uniform(0, 10) if random.random() > 0.5 else None
                )
                db.session.add(attendance)
        click.echo('✅ تم إضافة تسجيلات الحضور والانصراف')

        # ======= إضافة معاملات الغياب =======
        click.echo('📋 إضافة معاملات الغياب...')
        absence_transactions = []
        transaction_counter = 1  # عداد لأرقام المعاملات
        
        # إنشاء معاملات غياب للموظفين الذين لديهم حالات غياب
        for employee in employees:
            # إنشاء معاملات غياب متنوعة لكل موظف
            num_absences = random.randint(0, 5)  # عدد مختلف من معاملات الغياب
            
            for i in range(num_absences):
                absence_date = today - timedelta(days=random.randint(1, 60))
                
                # توليد رقم المعاملة
                date_str = absence_date.strftime('%Y%m%d')
                transaction_number = f'ABS-{date_str}-{transaction_counter:04d}'
                transaction_counter += 1
                
                # إنشاء معاملة الغياب
                transaction = AbsenceTransaction(
                    transaction_number=transaction_number,
                    employee_id=employee.id,
                    absence_date=absence_date,
                    status=random.choice(['pending', 'approved', 'rejected']),
                    absence_reason=random.choice([
                        'مرض مفاجئ',
                        'ظروف عائلية طارئة',
                        'مشكلة في وسائل النقل',
                        'حالة طقس سيئة',
                        'إنقطاع في الكهرباء',
                        'غياب بدون عذر',
                        None  # بعض الحالات بدون سبب محدد
                    ]),
                    employee_notes=random.choice([
                        'آسف للغياب، كان هناك ظرف طارئ',
                        'لم أتمكن من الحضور بسبب المرض',
                        'كانت هناك مشكلة في وسائل النقل',
                        'ظروف عائلية مهمة',
                        None
                    ]),
                    created_by=random.choice(users).id if random.random() > 0.3 else admin.id,  # استخدام admin.id كافتراضي
                    created_at=datetime.combine(absence_date, datetime.min.time()) + timedelta(hours=random.randint(8, 10))
                )
                
                # إذا كانت المعاملة موافق عليها أو مرفوضة، إضافة معلومات الموافقة
                if transaction.status in ['approved', 'rejected']:
                    # اختيار مستخدم مناسب للموافقة
                    potential_approvers = [
                        user for user in users 
                        if hasattr(user, 'user_type') and user.user_type in ['super_admin', 'branch_head', 'branch_deputy', 'department_head', 'department_deputy']
                    ]
                    if potential_approvers:
                        approver = random.choice(potential_approvers)
                        transaction.approved_by = approver.id
                        transaction.approved_at = transaction.created_at + timedelta(hours=random.randint(1, 48))
                        
                        if transaction.status == 'approved':
                            transaction.manager_notes = random.choice([
                                'معذور، ظروف خارجة عن إرادته',
                                'موافق على العذر المقدم',
                                'حالة طارئة مبررة',
                                'تم قبول العذر'
                            ])
                        else:  # rejected
                            transaction.manager_notes = random.choice([
                                'غياب غير مبرر',
                                'لم يتم تقديم عذر مقنع',
                                'تكرار في الغياب بدون مبرر',
                                'عدم الالتزام بالحضور'
                            ])
                    else:
                        # إذا لم يجد موافقين مناسبين، استخدم الأدمن
                        transaction.approved_by = admin.id
                        transaction.approved_at = transaction.created_at + timedelta(hours=random.randint(1, 48))
                
                db.session.add(transaction)
                absence_transactions.append(transaction)
                
        # حفظ المعاملات أولاً للحصول على معرفاتها
        db.session.flush()
        
        # الآن إضافة الإجابات والتاريخ لكل معاملة
        for transaction in absence_transactions:
            
            # ======= إضافة الإجابات على الأسئلة =======
            for question in absence_questions:
                # احتمالية الإجابة بنعم أو لا (متوازنة)
                is_answered = random.choice([True, False])
                
                # في بعض الحالات، جعل الإجابات منطقية أكثر
                if transaction.status == 'approved':
                    # إذا كانت المعاملة موافق عليها، زيادة احتمالية الإجابات الإيجابية
                    if 'عذر' in question.question_text or 'الإبلاغ' in question.question_text:
                        is_answered = random.choices([True, False], weights=[0.8, 0.2])[0]
                    elif 'متكرر' in question.question_text:
                        is_answered = random.choices([True, False], weights=[0.2, 0.8])[0]
                elif transaction.status == 'rejected':
                    # إذا كانت المعاملة مرفوضة، زيادة احتمالية الإجابات السلبية
                    if 'عذر' in question.question_text or 'الإبلاغ' in question.question_text:
                        is_answered = random.choices([True, False], weights=[0.3, 0.7])[0]
                    elif 'متكرر' in question.question_text:
                        is_answered = random.choices([True, False], weights=[0.7, 0.3])[0]
                
                answer = AbsenceAnswer(
                    absence_transaction_id=transaction.id,
                    absence_question_id=question.id,
                    is_answered=is_answered
                )
                db.session.add(answer)
            
            # ======= إضافة تاريخ المعاملة =======
            # إضافة سجل إنشاء المعاملة
            history_create = TransactionHistory(
                transaction_id=transaction.id,
                action='created',
                old_status=None,
                new_status='pending',
                notes='تم إنشاء المعاملة تلقائياً بسبب الغياب',
                user_id=transaction.created_by if transaction.created_by else admin.id,
                created_at=transaction.created_at
            )
            db.session.add(history_create)
            
            # إذا تم تحديث حالة المعاملة
            if transaction.status != 'pending' and transaction.approved_by:
                history_update = TransactionHistory(
                    transaction_id=transaction.id,
                    action='status_updated',
                    old_status='pending',
                    new_status=transaction.status,
                    notes=transaction.manager_notes,
                    user_id=transaction.approved_by,
                    created_at=transaction.approved_at
                )
                db.session.add(history_update)
        
        click.echo('✅ تم إضافة معاملات الغياب والإجابات')

        # حفظ جميع التغييرات
        db.session.commit()

        # ======= عرض ملخص البيانات المضافة =======
        click.echo('\n✅ تمت إضافة البيانات التجريبية بنجاح!')
        click.echo(f'📊 الإحصائيات:')
        # click.echo(f'  - أنواع المعاملات: {TransactionType.query.count()} نوع')
        click.echo(f'  - أسئلة الغياب: {AbsenceQuestion.query.count()} سؤال')
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
        
        # إحصائيات معاملات الغياب
        total_transactions = AbsenceTransaction.query.count()
        pending_transactions = AbsenceTransaction.query.filter_by(status='pending').count()
        approved_transactions = AbsenceTransaction.query.filter_by(status='approved').count()
        rejected_transactions = AbsenceTransaction.query.filter_by(status='rejected').count()
        
        click.echo(f'  - معاملات الغياب: {total_transactions} معاملة')
        click.echo(f'    - معلقة: {pending_transactions} معاملة')
        click.echo(f'    - موافق عليها: {approved_transactions} معاملة')
        click.echo(f'    - مرفوضة: {rejected_transactions} معاملة')
        click.echo(f'  - إجابات الأسئلة: {AbsenceAnswer.query.count()} إجابة')
        click.echo(f'  - سجلات تاريخ المعاملات: {TransactionHistory.query.count()} سجل')
        
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
        
        click.echo('\n📋 أمثلة على أرقام المعاملات المضافة:')
        sample_transactions = AbsenceTransaction.query.limit(5).all()
        for trans in sample_transactions:
            click.echo(f'  - {trans.transaction_number} ({trans.status}) - {trans.employee.full_name}')

    except Exception as e:
        db.session.rollback()
        click.echo(f'❌ حدث خطأ أثناء إضافة البيانات التجريبية: {str(e)}', err=True)
        import traceback
        click.echo(f'التفاصيل: {traceback.format_exc()}', err=True)
        return


@click.command()
@click.option('--yes', is_flag=True, help='تنفيذ الحذف فعلياً (بدونها: عرض فقط dry-run)')
@with_appcontext
def cleanup_dev_approvals(yes):
    """
    تنظيف سجلات الموافقة العالقة (pending) المرتبطة بحسابات dev على المعاملات القديمة
    التي أُنشئت قبل إضافة نوع المستخدم dev (يوم كان الحساب مسجّل كـ super_admin).
    بدون --yes: يعرض فقط ما سيتم حذفه/إنهاؤه دون أي تعديل فعلي على قاعدة البيانات.
    """
    from app.models.user import User
    from app.models.transaction import Transaction, TransactionApproval

    dev_user_ids = [u.id for u in User.query.filter_by(user_type='dev').all()]
    if not dev_user_ids:
        click.echo('لا يوجد أي حساب من نوع dev حالياً.')
        return

    stale_approvals = TransactionApproval.query.filter(
        TransactionApproval.approver_id.in_(dev_user_ids),
        TransactionApproval.status == 'pending'
    ).join(Transaction).filter(Transaction.status == 'pending').all()

    if not stale_approvals:
        click.echo('لا يوجد أي سجل موافقة عالق مرتبط بحسابات dev. لا شيء للتنظيف.')
        return

    click.echo(f'{"[DRY-RUN] " if not yes else ""}تم العثور على {len(stale_approvals)} سجل موافقة عالق:')

    affected_transaction_ids = set()
    for approval in stale_approvals:
        transaction = approval.transaction
        click.echo(f'  - معاملة {transaction.transaction_number} (#{transaction.id}) - الموافق العالق: {approval.approver.username}')
        affected_transaction_ids.add(transaction.id)

    if not yes:
        click.echo('\nلتنفيذ الحذف الفعلي، أعد التشغيل مع --yes')
        return

    removed = 0
    for approval in stale_approvals:
        db.session.delete(approval)
        removed += 1
    db.session.commit()
    click.echo(f'✅ تم حذف {removed} سجل موافقة عالق.')

    finalized = 0
    for transaction_id in affected_transaction_ids:
        transaction = Transaction.query.get(transaction_id)
        if transaction.status == 'pending' and transaction.is_fully_approved():
            click.echo(f'  - إنهاء المعاملة {transaction.transaction_number} (اكتملت جميع الموافقات الفعلية فعلياً)')
            if transaction.create_final_record():
                finalized += 1
            else:
                click.echo(f'    ⚠️  فشل إنهاء المعاملة {transaction.transaction_number}، تحقق يدوياً.')

    click.echo(f'✅ تم إنهاء {finalized} معاملة كانت مكتملة الموافقات فعلياً.')
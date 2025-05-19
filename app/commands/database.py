import click
from flask.cli import with_appcontext
from datetime import date, time, datetime
import random
from app import db
from app.models import (
    Branch, Department, JobTitle, Shift,
    Employee, User, Attendance, Advance, Penalty,
    Reward, ProductionPiece, ProductionMonitoring
)
from werkzeug.security import generate_password_hash


@click.command()
@with_appcontext
def seed_db():
    """Seed the database with sample data for all tables."""
    click.echo('🌱 بدء إضافة بيانات تجريبية...')

    # 1. الفروع
    branches = [
        Branch(name="الفرع الرئيسي", address="القاهرة", phone="0101010101"),
        Branch(name="فرع الإسكندرية", address="الإسكندرية", phone="0111111111")
    ]
    db.session.add_all(branches)
    db.session.commit()
    click.echo("✅ تم إضافة الفروع")

    # 2. الأقسام
    departments = [
        Department(name="الموارد البشرية", description="إدارة شؤون الموظفين"),
        Department(name="المبيعات", description="قسم المبيعات")
    ]
    db.session.add_all(departments)
    db.session.commit()
    click.echo("✅ تم إضافة الأقسام")

    # 3. المسميات الوظيفية
    job_titles = [
        JobTitle(title_name="مدير تنفيذي", overtime_hour_value=100, delay_minute_value=5),
        JobTitle(title_name="مندوب مبيعات", overtime_hour_value=80, delay_minute_value=3)
    ]
    db.session.add_all(job_titles)
    db.session.commit()
    click.echo("✅ تم إضافة المسميات الوظيفية")

    # 4. الورديات
    shifts = [
        Shift(name="صباحية", start_time=time(8, 0), end_time=time(16, 0)),
        Shift(name="مسائية", start_time=time(16, 0), end_time=time(24, 0))
    ]
    db.session.add_all(shifts)
    db.session.commit()
    click.echo("✅ تم إضافة الورديات")

    # 5. الموظفين
    employees = []
    for i in range(1, 11):
        branch_id = 1 if i <= 5 else 2
        department_id = 1 if i <= 5 else 2
        employee = Employee(
            fingerprint_id=f"FP{i:03d}",
            full_name=f"موظف {i}",
            branch_id=branch_id,
            department_id=department_id,
            position=random.choice([1, 2]),
            salary=10000 + i * 500,
            shift_id=random.choice([1, 2]),
            date_of_birth=date(1990 + i, 1, 1),
            mobile_1=f"010101000{i}"
        )
        employees.append(employee)
    db.session.add_all(employees)
    db.session.commit()
    click.echo("✅ تم إضافة الموظفين")

    # 6. المستخدمين
    users = []
    for emp in employees:
        user = User(
            username=f"user_{emp.id}",
            password=generate_password_hash("123456"),
            is_active=True,
            user_type="employee",
            employee_id=emp.id,
            branch_id=emp.branch_id,
            department_id=emp.department_id
        )
        users.append(user)
    db.session.add_all(users)
    db.session.commit()
    click.echo("✅ تم إضافة المستخدمين")

    # 7. الحضور
    attendances = []
    for emp in employees:
        att = Attendance(
            empId=emp.id,
            createdAt=date.today(),
            checkInTime=time(8, 30),
            checkOutTime=time(16, 15),
            checkInReason="حضور طبيعي",
            checkOutReason="انصراف طبيعي"
        )
        attendances.append(att)
    db.session.add_all(attendances)
    db.session.commit()
    click.echo("✅ تم إضافة بيانات الحضور")

    # 8. السلف
    advances = []
    for emp in employees:
        adv = Advance(
            employee_id=emp.id,
            amount=500 + emp.id * 100,
            document_number=f"ADV{emp.id:03d}",
            notes="سلفة شهرية"
        )
        advances.append(adv)
    db.session.add_all(advances)
    db.session.commit()
    click.echo("✅ تم إضافة السلف")

    # 9. الجزاءات
    penalties = []
    for emp in employees:
        penalty = Penalty(
            employee_id=emp.id,
            amount=100 + emp.id * 10,
            document_number=f"PEN{emp.id:03d}",
            notes="جزاء تأخير"
        )
        penalties.append(penalty)
    db.session.add_all(penalties)
    db.session.commit()
    click.echo("✅ تم إضافة الجزاءات")

    # 10. المكافآت
    rewards = []
    for emp in employees:
        reward = Reward(
            employee_id=emp.id,
            amount=200 + emp.id * 20,
            document_number=f"REW{emp.id:03d}",
            notes="مكافأة أداء"
        )
        rewards.append(reward)
    db.session.add_all(rewards)
    db.session.commit()
    click.echo("✅ تم إضافة المكافآت")

    # 11. المنتجات
    pieces = [
        ProductionPiece(piece_number="P001", piece_name="منتج A", price_levels={"A": 10, "B": 9}),
        ProductionPiece(piece_number="P002", piece_name="منتج B", price_levels={"A": 15, "B": 14})
    ]
    db.session.add_all(pieces)
    db.session.commit()

    # 12. مراقبة الإنتاج
    production_records = []
    for emp in employees:
        rec = ProductionMonitoring(
            employee_id=emp.id,
            piece_id=1 if emp.id % 2 == 0 else 2,
            quantity=50 + emp.id,
            quality_grade="A" if emp.id % 2 == 0 else "B"
        )
        production_records.append(rec)
    db.session.add_all(production_records)
    db.session.commit()
    click.echo("✅ تم إضافة بيانات الإنتاج")

    click.echo("🎉 تمت إضافة جميع البيانات التجريبية بنجاح!")


# يمكنك هنا إضافة الأوامر الأخرى مثل reset_db, init_db, fresh_migrate ... إذا كنت تحتاجها
# وإليك أمثلة مختصرة لأهمها:

@click.command()
@click.option('--yes', is_flag=True, help='تخطي رسالة التأكيد')
@with_appcontext
def reset_db(yes):
    if not yes and not click.confirm('⚠️ هل تريد حقًا حذف جميع البيانات؟'):
        return
    click.echo('🗑️ إعادة تعيين قاعدة البيانات...')
    db.drop_all()
    db.create_all()
    click.echo('✅ جاهز')


@click.command()
@with_appcontext
def init_db():
    click.echo('🏗️ إنشاء الجداول...')
    db.create_all()
    click.echo('✅ تم إنشاء الجداول')


# تسجيل الأوامر
def register_commands(app):
    app.cli.add_command(seed_db)
    app.cli.add_command(reset_db)
    app.cli.add_command(init_db)
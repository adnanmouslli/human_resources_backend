from datetime import date, datetime
from flask import Blueprint, request, jsonify
from app import db
from app.models import ProductionMonitoring, Employee, ProductionPiece
from app.utils import token_required
from sqlalchemy import func

production_monitoring_bp = Blueprint('production_monitoring', __name__)

# إضافة سجل مراقبة إنتاج جديد
@production_monitoring_bp.route('/api/production-monitoring', methods=['POST'])
@token_required
def create_monitoring(user_id):
    data = request.get_json()

    # التحقق من البيانات المطلوبة
    required_fields = ['employee_id', 'piece_id', 'quantity', 'quality_grade']
    missing_fields = [field for field in required_fields if field not in data or not data[field]]
    if missing_fields:
        return jsonify({'message': f'Missing fields: {", ".join(missing_fields)}'}), 400

    try:
        # التحقق من وجود الموظف
        employee = Employee.query.get(data['employee_id'])
        if not employee:
            return jsonify({'message': 'Employee not found'}), 404

        # التحقق من وجود القطعة
        piece = ProductionPiece.query.get(data['piece_id'])
        if not piece:
            return jsonify({'message': 'Production piece not found'}), 404

        # التحقق من صحة مستوى الجودة
        valid_grades = ['A', 'B', 'C', 'D', 'E']
        if data['quality_grade'] not in valid_grades:
            return jsonify({'message': 'Invalid quality grade. Must be one of: A, B, C, D, E'}), 400

        # التحقق من أن الكمية رقم موجب
        if not isinstance(data['quantity'], (int, float)) or data['quantity'] <= 0:
            return jsonify({'message': 'Quantity must be a positive number'}), 400

        monitoring = ProductionMonitoring(
            employee_id=data['employee_id'],
            piece_id=data['piece_id'],
            quantity=data['quantity'],
            quality_grade=data['quality_grade'],
            date=data.get('date', date.today()),
            notes=data.get('notes')
        )
        
        db.session.add(monitoring)
        db.session.commit()

        return jsonify({
            'message': 'Production monitoring record created',
            'data': {
                'id': monitoring.id,
                'employee_id': monitoring.employee_id,
                'employee_name': employee.full_name,
                'piece_id': monitoring.piece_id,
                'piece_name': piece.piece_name,
                'quantity': monitoring.quantity,
                'quality_grade': monitoring.quality_grade,
                'date': monitoring.date.isoformat(),
                'created_at': monitoring.created_at.isoformat()
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        error_message = str(e)
        if 'FOREIGN KEY constraint' in error_message:
            return jsonify({
                'message': 'Invalid data: Please check employee ID and piece ID',
                'error': 'Foreign key constraint violation'
            }), 400
        return jsonify({
            'message': 'Error creating monitoring record',
            'error': error_message
        }), 500


# إضافة سجل مراقبة إنتاج متعدد المستويات
@production_monitoring_bp.route('/api/production-monitoring/multi-quality', methods=['POST'])
@token_required
def create_monitoring_multi_quality(user_id):
    data = request.get_json()

    # التحقق من البيانات المطلوبة
    required_fields = ['employee_id', 'piece_id', 'quality_data', 'date']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return jsonify({'message': f'Missing fields: {", ".join(missing_fields)}'}), 400

    # التحقق من أن البيانات صحيحة
    if not isinstance(data['quality_data'], list) or len(data['quality_data']) == 0:
        return jsonify({'message': 'quality_data must be a non-empty list of quality grade objects'}), 400

    try:
        # التحقق من وجود الموظف
        employee = Employee.query.get(data['employee_id'])
        if not employee:
            return jsonify({'message': 'Employee not found'}), 404

        # التحقق من وجود القطعة
        piece = ProductionPiece.query.get(data['piece_id'])
        if not piece:
            return jsonify({'message': 'Production piece not found'}), 404
            
        # التحقق من أن القطعة مفعلة
        if not piece.is_active:
            return jsonify({'message': 'This production piece is inactive'}), 400

        # معالجة التاريخ
        try:
            monitoring_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        except ValueError:
            monitoring_date = date.today()

        created_records = []
        
        # إنشاء سجل منفصل لكل مستوى جودة له كمية أكبر من صفر
        for quality_item in data['quality_data']:
            # التحقق من صحة البيانات
            if 'grade' not in quality_item or 'quantity' not in quality_item:
                continue
                
            grade = quality_item['grade']
            quantity = quality_item['quantity']
            notes = quality_item.get('notes', '')
            
            # تجاهل المستويات بكمية صفر أو أقل
            if quantity <= 0:
                continue
                
            # التحقق من صحة مستوى الجودة
            valid_grades = ['A', 'B', 'C', 'D', 'E']
            if grade not in valid_grades:
                continue

            # إنشاء سجل لهذا المستوى
            monitoring = ProductionMonitoring(
                employee_id=data['employee_id'],
                piece_id=data['piece_id'],
                quantity=quantity,
                quality_grade=grade,
                date=monitoring_date,
                notes=notes
            )
            
            db.session.add(monitoring)
            
            # إضافة معلومات السجل إلى قائمة السجلات المنشأة
            created_records.append({
                'id': None,  # سيتم تحديثه بعد الحفظ
                'quality_grade': grade,
                'quantity': quantity,
                'notes': notes
            })
        
        # إذا لم يتم إنشاء أي سجلات (جميع الكميات كانت صفرًا)
        if not created_records:
            return jsonify({'message': 'No valid records to create. All quantities must be greater than zero'}), 400
            
        # حفظ جميع السجلات في قاعدة البيانات
        db.session.commit()
        
        # تحديث معرفات السجلات المنشأة
        new_records = ProductionMonitoring.query.filter_by(
            employee_id=data['employee_id'],
            piece_id=data['piece_id'],
            date=monitoring_date
        ).order_by(ProductionMonitoring.created_at.desc()).limit(len(created_records)).all()
        
        for i, record in enumerate(new_records):
            if i < len(created_records):
                created_records[i]['id'] = record.id

        return jsonify({
            'message': 'Production monitoring records created successfully',
            'data': {
                'employee_id': data['employee_id'],
                'employee_name': employee.full_name,
                'piece_id': data['piece_id'],
                'piece_name': piece.piece_name,
                'date': monitoring_date.isoformat(),
                'records': created_records,
                'total_quantity': sum(record['quantity'] for record in created_records)
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        error_message = str(e)
        return jsonify({
            'message': 'Error creating monitoring records',
            'error': error_message
        }), 500
    
# الحصول على جميع سجلات المراقبة
@production_monitoring_bp.route('/api/production-monitoring', methods=['GET'])
@token_required
def get_all_monitoring(user_id):
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        employee_id = request.args.get('employee_id')
        piece_id = request.args.get('piece_id')  # إضافة piece_id

        query = ProductionMonitoring.query

        if start_date:
            query = query.filter(ProductionMonitoring.date >= start_date)
        if end_date:
            query = query.filter(ProductionMonitoring.date <= end_date)
        if employee_id:
            query = query.filter(ProductionMonitoring.employee_id == employee_id)
        if piece_id:  # إضافة فلتر piece_id
            query = query.filter(ProductionMonitoring.piece_id == piece_id)

        records = query.all()

        return jsonify([{
            'id': record.id,
            'employee': {
                'id': record.employee.id,
                'name': record.employee.full_name
            },
            'piece': {
                'id': record.piece.id,
                'name': record.piece.piece_name
            },
            'quantity': record.quantity,
            'quality_grade': record.quality_grade,
            'date': record.date.isoformat(),
            'notes': record.notes,
            'created_at': record.created_at.isoformat()
        } for record in records]), 200

    except Exception as e:
        return jsonify({'message': 'Error fetching monitoring records', 'error': str(e)}), 500
    

# الحصول على سجل مراقبة محدد
@production_monitoring_bp.route('/api/production-monitoring/<int:id>', methods=['GET'])
@token_required
def get_monitoring(user_id, id):
    try:
        record = ProductionMonitoring.query.get(id)
        
        if not record:
            return jsonify({'message': 'Record not found'}), 404

        return jsonify({
            'id': record.id,
            'employee': {
                'id': record.employee.id,
                'name': record.employee.full_name
            },
            'piece': {
                'id': record.piece.id,
                'name': record.piece.piece_name
            },
            'quantity': record.quantity,
            'quality_grade': record.quality_grade,
            'date': record.date.isoformat(),
            'notes': record.notes,
            'created_at': record.created_at.isoformat()
        }), 200

    except Exception as e:
        return jsonify({'message': 'Error fetching monitoring record', 'error': str(e)}), 500

# تحديث سجل مراقبة
@production_monitoring_bp.route('/api/production-monitoring/<int:id>', methods=['PUT'])
@token_required
def update_monitoring(user_id, id):
    try:
        record = ProductionMonitoring.query.get(id)
        
        if not record:
            return jsonify({'message': 'Record not found'}), 404

        data = request.get_json()

        # تحديث البيانات القابلة للتعديل
        if 'employee_id' in data:
            record.employee_id = data['employee_id']
        if 'piece_id' in data:
            record.piece_id = data['piece_id']
        if 'quantity' in data:
            record.quantity = data['quantity']
        if 'quality_grade' in data:
            record.quality_grade = data['quality_grade']
        if 'notes' in data:
            record.notes = data['notes']
        if 'date' in data:
            record.date = datetime.strptime(data['date'], '%Y-%m-%d').date()

        db.session.commit()

        # تحسين الرد ليشمل كل البيانات المحدثة مع العلاقات
        return jsonify({
            'id': record.id,
            'employee': {
                'id': record.employee.id,
                'name': record.employee.full_name
            },
            'piece': {
                'id': record.piece.id,
                'name': record.piece.piece_name
            },
            'quantity': record.quantity,
            'quality_grade': record.quality_grade,
            'date': record.date.isoformat(),
            'notes': record.notes,
            'created_at': record.created_at.isoformat()
        }), 200

    except Exception as e:
        return jsonify({'message': 'Error updating monitoring record', 'error': str(e)}), 500   
# حذف سجل مراقبة
@production_monitoring_bp.route('/api/production-monitoring/<int:id>', methods=['DELETE'])
@token_required
def delete_monitoring(user_id, id):
    try:
        record = ProductionMonitoring.query.get(id)
        
        if not record:
            return jsonify({'message': 'Record not found'}), 404

        db.session.delete(record)
        db.session.commit()

        return jsonify({'message': 'Production monitoring record deleted'}), 200

    except Exception as e:
        return jsonify({'message': 'Error deleting monitoring record', 'error': str(e)}), 500

@production_monitoring_bp.route('/api/production-monitoring/statistics/daily', methods=['GET'])
@token_required
def get_daily_statistics(user_id):
    try:
        today = date.today()
        
        # إحصائيات عامة للإنتاج
        base_stats = db.session.query(
            func.sum(ProductionMonitoring.quantity).label('total_quantity'),
            func.count(func.distinct(ProductionMonitoring.employee_id)).label('total_employees'),
            func.avg(ProductionMonitoring.quantity).label('avg_quantity_per_record'),
            func.count(ProductionMonitoring.id).label('total_records')
        ).filter(ProductionMonitoring.date == today).first()

        # إحصائيات حسب مستوى الجودة
        quality_stats = db.session.query(
            ProductionMonitoring.quality_grade,
            func.sum(ProductionMonitoring.quantity).label('quantity'),
            func.count(ProductionMonitoring.id).label('records_count'),
            func.avg(ProductionMonitoring.quantity).label('avg_quantity')
        ).filter(
            ProductionMonitoring.date == today
        ).group_by(
            ProductionMonitoring.quality_grade
        ).all()

        # إحصائيات أفضل الموظفين
        top_employees = db.session.query(
            Employee.id,
            Employee.full_name,  # نحتاج لإضافة هذا العمود في GROUP BY
            func.sum(ProductionMonitoring.quantity).label('total_quantity'),
            func.avg(ProductionMonitoring.quantity).label('avg_quantity'),
            func.count(ProductionMonitoring.id).label('records_count')
        ).join(
            ProductionMonitoring, Employee.id == ProductionMonitoring.employee_id
        ).filter(
            ProductionMonitoring.date == today
        ).group_by(
            Employee.id,
            Employee.full_name  # إضافة full_name هنا لحل المشكلة
        ).order_by(
            func.sum(ProductionMonitoring.quantity).desc()
        ).limit(5).all()

        # إحصائيات القطع الأكثر إنتاجاً
        top_pieces = db.session.query(
            ProductionPiece.id,
            ProductionPiece.piece_name,
            func.sum(ProductionMonitoring.quantity).label('total_quantity'),
            func.avg(ProductionMonitoring.quantity).label('avg_quantity'),
            func.count(ProductionMonitoring.id).label('records_count')
        ).join(
            ProductionMonitoring, ProductionPiece.id == ProductionMonitoring.piece_id
        ).filter(
            ProductionMonitoring.date == today
        ).group_by(
            ProductionPiece.id,
            ProductionPiece.piece_name  # إضافة piece_name هنا
        ).order_by(
            func.sum(ProductionMonitoring.quantity).desc()
        ).limit(5).all()

        # إحصائيات ساعات الذروة
        hourly_stats = db.session.query(
            func.extract('hour', ProductionMonitoring.created_at).label('hour'),
            func.sum(ProductionMonitoring.quantity).label('quantity'),
            func.count(ProductionMonitoring.id).label('records_count')
        ).filter(
            ProductionMonitoring.date == today
        ).group_by(
            func.extract('hour', ProductionMonitoring.created_at)
        ).order_by('hour').all()

        # تحليل الجودة المتقدم
        quality_analysis = {
            grade: {
                'quantity': quantity,
                'records_count': records_count,
                'average_quantity': float(avg_quantity or 0),
                'percentage_of_total': (quantity / (base_stats.total_quantity or 1)) * 100
            }
            for grade, quantity, records_count, avg_quantity in quality_stats
        }

        return jsonify({
            'date': today.isoformat(),
            'general_statistics': {
                'total_quantity': base_stats.total_quantity or 0,
                'total_employees': base_stats.total_employees or 0,
                'total_records': base_stats.total_records or 0,
                'average_quantity_per_record': float(base_stats.avg_quantity_per_record or 0),
                'average_quantity_per_employee': float(base_stats.total_quantity or 0) / (base_stats.total_employees or 1)
            },
            'quality_distribution': quality_analysis,
            'top_performers': [{
                'employee_id': emp.id,
                'name': emp.full_name,
                'total_quantity': emp.total_quantity,
                'average_quantity': float(emp.avg_quantity or 0),
                'records_count': emp.records_count
            } for emp in top_employees],
            'top_pieces': [{
                'piece_id': piece.id,
                'name': piece.piece_name,
                'total_quantity': piece.total_quantity,
                'average_quantity': float(piece.avg_quantity or 0),
                'records_count': piece.records_count
            } for piece in top_pieces],
            'hourly_production': [{
                'hour': int(stat.hour),
                'quantity': stat.quantity,
                'records_count': stat.records_count
            } for stat in hourly_stats],
            'productivity_metrics': {
                'records_per_employee': (base_stats.total_records or 0) / (base_stats.total_employees or 1),
                'quality_rate': len([g for g in quality_analysis if g in ['A', 'B']]) / len(quality_analysis) if quality_analysis else 0,
                'efficiency_score': calculate_efficiency_score(base_stats, quality_analysis)
            }
        }), 200

    except Exception as e:
        return jsonify({'message': 'Error fetching daily statistics', 'error': str(e)}), 500

def calculate_efficiency_score(base_stats, quality_analysis):
    try:
        # حساب درجة الكفاءة بناءً على عدة عوامل
        quality_weights = {'A': 1.0, 'B': 0.8, 'C': 0.6, 'D': 0.4, 'E': 0.2}
        quality_score = sum(
            quality_analysis[grade]['quantity'] * quality_weights.get(grade, 0)
            for grade in quality_analysis
        ) / (base_stats.total_quantity or 1)

        productivity_score = (base_stats.avg_quantity_per_record or 0) / (
            db.session.query(func.avg(ProductionMonitoring.quantity)).scalar() or 1
        )

        return (quality_score + productivity_score) / 2
    except:
        return 0
# الحصول على إحصائيات الموظف
@production_monitoring_bp.route('/api/production-monitoring/statistics/employee/<int:employee_id>', methods=['GET'])
@token_required
def get_employee_statistics(user_id, employee_id):
    try:
        # تحقق من وجود الموظف
        employee = Employee.query.get(employee_id)
        if not employee:
            return jsonify({'message': 'Employee not found'}), 404

        # فترة الإحصائيات
        start_date = request.args.get('start_date', date.today().isoformat())
        end_date = request.args.get('end_date', date.today().isoformat())

        # إحصائيات الإنتاج
        stats = db.session.query(
            func.sum(ProductionMonitoring.quantity).label('total_quantity'),
            func.avg(ProductionMonitoring.quantity).label('avg_quantity')
        ).filter(
            ProductionMonitoring.employee_id == employee_id,
            ProductionMonitoring.date.between(start_date, end_date)
        ).first()

        # إحصائيات الجودة
        quality_stats = db.session.query(
            ProductionMonitoring.quality_grade,
            func.sum(ProductionMonitoring.quantity).label('quantity')
        ).filter(
            ProductionMonitoring.employee_id == employee_id,
            ProductionMonitoring.date.between(start_date, end_date)
        ).group_by(
            ProductionMonitoring.quality_grade
        ).all()

        return jsonify({
            'employee': {
                'id': employee.id,
                'name': employee.full_name
            },
            'period': {
                'start_date': start_date,
                'end_date': end_date
            },
            'statistics': {
                'total_quantity': stats.total_quantity or 0,
                'average_quantity': float(stats.avg_quantity or 0),
                'quality_distribution': {
                    grade: quantity
                    for grade, quantity in quality_stats
                }
            }
        }), 200

    except Exception as e:
        return jsonify({'message': 'Error fetching employee statistics', 'error': str(e)}), 500
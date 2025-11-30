from flask import jsonify, request
from app import db
from app.models import Reward, Employee
from app.models.user import User

class RewardController:
    @staticmethod
    def create_reward(data):
        # التحقق من الحقول المطلوبة
        required_fields = ['employee_id', 'amount', 'document_number']
        missing_fields = [field for field in required_fields if field not in data or not data[field]]
        if missing_fields:
            return {'message': f'Missing fields: {", ".join(missing_fields)}'}, 400

        # التحقق من وجود الموظف
        employee = Employee.query.get(data['employee_id'])
        if not employee:
            return {'message': 'Employee not found'}, 404

        try:
            reward = Reward(
                employee_id=data['employee_id'],
                amount=data['amount'],
                document_number=data['document_number'],
                notes=data.get('notes')  # ملاحظات اختيارية
            )
            db.session.add(reward)
            db.session.commit()
            return {
                'message': 'Reward created',
                'reward': {
                    'id': reward.id,
                    'employee_id': reward.employee_id,
                    'full_name': employee.full_name,  # إضافة اسم الموظف
                    'amount': str(reward.amount),
                    'document_number': reward.document_number,
                    'notes': reward.notes,
                    'date': str(reward.date)
                }
            }, 201
        except Exception as e:
            return {'message': 'Error creating reward', 'error': str(e)}, 500

    @staticmethod
    def get_all_rewards(user):
      try:
          user = User.query.get(user.id)
          if not user:
              return {'message': 'User not found'}, 404

        # احصل على الموظفين الذين يمكن للمستخدم الوصول إليهم
          accessible_employees = user.get_accessible_employees()
          accessible_employee_ids = [emp.id for emp in accessible_employees]

          rewards = Reward.query.join(Employee).filter(Reward.employee_id.in_(accessible_employee_ids)).all()

          return [
              {
                  'id': reward.id,
                  'employee': {
                      'id': reward.employee.id,
                      'name': reward.employee.full_name,
                  },
                  'amount': str(reward.amount),
                  'document_number': reward.document_number,
                  'notes': reward.notes,
                  'date': str(reward.date)
              } for reward in rewards
          ], 200

      except Exception as e:
          return {'message': 'Error fetching rewards', 'error': str(e)}, 500


    @staticmethod
    def get_reward_by_id(id):
        reward = Reward.query.get(id)
        if not reward:
            return {'message': 'Reward not found'}, 404
        return {
            'id': reward.id,
            'employee_id': reward.employee_id,
            'amount': str(reward.amount),
            'document_number': reward.document_number,
            'notes': reward.notes,
            'date': str(reward.date)
        }, 200

    @staticmethod
    def update_reward(id, data):
        reward = Reward.query.get(id)
        if not reward:
            return {'message': 'Reward not found'}, 404

        try:
            if 'amount' in data:
                reward.amount = data['amount']
            if 'document_number' in data:
                reward.document_number = data['document_number']
            if 'notes' in data:
                reward.notes = data['notes']

            db.session.commit()
            return {
                'message': 'Reward updated',
                'reward': {
                    'id': reward.id,
                    'employee_id': reward.employee_id,
                    'amount': str(reward.amount),
                    'document_number': reward.document_number,
                    'notes': reward.notes,
                    'date': str(reward.date)
                }
            }, 200
        except Exception as e:
            return {'message': 'Error updating reward', 'error': str(e)}, 500

    @staticmethod
    def delete_reward(id):
        reward = Reward.query.get(id)
        if not reward:
            return {'message': 'Reward not found'}, 404

        try:
            db.session.delete(reward)
            db.session.commit()
            return {'message': 'Reward deleted'}, 200
        except Exception as e:
            return {'message': 'Error deleting reward', 'error': str(e)}, 500

    @staticmethod
    def get_rewards_by_employee_id(emp_id):
        employee = Employee.query.get(emp_id)
        if not employee:
            return {'message': 'Employee not found'}, 404

        try:
            rewards = Reward.query.filter_by(employee_id=emp_id).all()
            return [
                {
                    'id': reward.id,
                    'employee': {
                        'id': employee.id,
                        'name': employee.full_name,
                    },
                    'amount': str(reward.amount),
                    'document_number': reward.document_number,
                    'notes': reward.notes,
                    'date': str(reward.date)
                } for reward in rewards
            ], 200
        except Exception as e:
            return {'message': 'Error fetching rewards by employee ID', 'error': str(e)}, 500

    @staticmethod
    def bulk_upload_rewards(user):
        """
        رفع مجموعة من المكافآت دفعة واحدة من ملف Excel
        """
        try:
            data = request.get_json()
            
            if 'rewards' not in data or not isinstance(data['rewards'], list):
                return {'message': 'Invalid data format. Expected "rewards" array'}, 400
            
            rewards_data = data['rewards']
            
            if len(rewards_data) == 0:
                return {'message': 'No rewards data provided'}, 400
            
            # الحصول على المستخدم
            user_obj = User.query.get(user.id)
            if not user_obj:
                return {'message': 'User not found'}, 404
            
            # جلب الموظفين المسموح له برؤيتهم
            accessible_employees = user_obj.get_accessible_employees()
            accessible_employee_ids = {emp.id for emp in accessible_employees}
            
            successful_rewards = []
            failed_rewards = []
            
            for index, reward_data in enumerate(rewards_data, start=2):  # نبدأ من 2 لأن 1 هو العنوان
                try:
                    # التحقق من الحقول المطلوبة
                    employee_id = reward_data.get('employee_id')
                    amount = reward_data.get('amount')
                    document_number = reward_data.get('document_number')
                    
                    if not employee_id or not amount or not document_number:
                        failed_rewards.append({
                            'row': index,
                            'employee_id': employee_id or 'N/A',
                            'employee_name': 'N/A',
                            'error': 'بيانات ناقصة: يجب توفير كود الموظف، القيمة، ورقم المستند'
                        })
                        continue
                    
                    # التحقق من أن الموظف موجود
                    employee = Employee.query.get(employee_id)
                    if not employee:
                        failed_rewards.append({
                            'row': index,
                            'employee_id': employee_id,
                            'employee_name': 'غير موجود',
                            'error': f'الموظف بالكود {employee_id} غير موجود'
                        })
                        continue
                    
                    # التحقق من صلاحية الوصول للموظف
                    if employee_id not in accessible_employee_ids:
                        failed_rewards.append({
                            'row': index,
                            'employee_id': employee_id,
                            'employee_name': employee.full_name,
                            'error': 'ليس لديك صلاحية للوصول إلى هذا الموظف'
                        })
                        continue
                    
                    # التحقق من صحة المبلغ
                    try:
                        amount = float(amount)
                        if amount <= 0:
                            raise ValueError("Amount must be positive")
                    except (ValueError, TypeError):
                        failed_rewards.append({
                            'row': index,
                            'employee_id': employee_id,
                            'employee_name': employee.full_name,
                            'error': 'قيمة المكافأة غير صحيحة'
                        })
                        continue
                    
                    # إنشاء المكافأة
                    reward = Reward(
                        employee_id=employee_id,
                        amount=amount,
                        document_number=str(document_number),
                        notes=reward_data.get('notes', '')
                    )
                    
                    db.session.add(reward)
                    successful_rewards.append({
                        'employee_id': employee_id,
                        'employee_name': employee.full_name,
                        'amount': amount,
                        'document_number': document_number
                    })
                    
                except Exception as e:
                    failed_rewards.append({
                        'row': index,
                        'employee_id': reward_data.get('employee_id', 'N/A'),
                        'employee_name': 'N/A',
                        'error': f'خطأ غير متوقع: {str(e)}'
                    })
            
            # حفظ جميع المكافآت الناجحة
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                return {
                    'success': False,
                    'message': f'فشل حفظ البيانات: {str(e)}',
                    'successful_count': 0,
                    'failed_count': len(rewards_data)
                }, 500
            
            return {
                'success': True,
                'message': f'تم رفع {len(successful_rewards)} مكافأة بنجاح من أصل {len(rewards_data)}',
                'successful_count': len(successful_rewards),
                'failed_count': len(failed_rewards),
                'errors': failed_rewards if failed_rewards else None
            }, 200
        
        except Exception as e:
            db.session.rollback()
            print(f"Error in bulk upload: {str(e)}")
            return {
                'success': False,
                'message': f'حدث خطأ أثناء رفع المكافآت: {str(e)}',
                'successful_count': 0,
                'failed_count': 0
            }, 500
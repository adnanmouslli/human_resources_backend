# دليل استخدام نظام الإشعارات

## نظرة عامة
نظام إشعارات متكامل يتيح إرسال إشعارات تلقائية لمديري الأقسام والفروع عندما يقوم الموظفون بأي إجراء.

## المميزات
- إشعارات فورية لمديري القسم والفرع
- نظام مقروء/غير مقروء
- إعدادات تخصيص للإشعارات لكل مستخدم
- دعم أنواع وأولويات مختلفة للإشعارات
- حذف تلقائي للإشعارات القديمة

## أنواع الإشعارات المتاحة
- `general` - إشعار عام
- `attendance` - إشعار حضور/غياب
- `leave` - إشعار إجازة
- `advance` - إشعار سلفة
- `reward` - إشعار مكافأة
- `penalty` - إشعار جزاء
- `transaction` - إشعار معاملة
- `absence` - إشعار غياب
- `production` - إشعار إنتاج
- `system` - إشعار نظام
- `kpi` - إشعار KPI

## أولويات الإشعارات
- `low` - منخفضة
- `medium` - متوسطة (افتراضي)
- `high` - عالية
- `urgent` - عاجلة

---

## طريقة الاستخدام في الكود

### 1. إشعار تلقائي عند إجراء موظف

```python
from app.services.notification_service import notify_employee_action, NotificationType, NotificationPriority

# عندما يطلب موظف إجازة مثلاً
notify_employee_action(
    employee_id=employee.id,
    action_title="طلب إجازة جديد",
    action_message=f"قام الموظف {employee.full_name} بطلب إجازة جديدة من {start_date} إلى {end_date}",
    notification_type=NotificationType.LEAVE.value,
    priority=NotificationPriority.MEDIUM.value,
    entity_type="leave",
    entity_id=new_leave.id,
    extra_data={
        "leave_type": "annual",
        "days_count": 5,
        "start_date": str(start_date),
        "end_date": str(end_date)
    }
)
```

### 2. إشعار لرؤساء قسم محدد

```python
from app.services.notification_service import notify_department_action

notify_department_action(
    department_id=department_id,
    action_title="تحديث في القسم",
    action_message="تم إضافة موظف جديد إلى القسم",
    notification_type=NotificationType.GENERAL.value,
    include_deputies=True  # سيتم إرسال الإشعار للنواب أيضاً
)
```

### 3. إشعار لرؤساء فرع محدد

```python
from app.services.notification_service import notify_branch_action

notify_branch_action(
    branch_id=branch_id,
    action_title="تقرير شهري جاهز",
    action_message="تم إعداد التقرير الشهري للفرع",
    notification_type=NotificationType.GENERAL.value
)
```

### 4. إرسال إشعار مخصص باستخدام NotificationService

```python
from app.services.notification_service import NotificationService

# إرسال لشخص محدد
NotificationService.send_notification(
    recipient_id=user_id,
    title="عنوان الإشعار",
    message="نص الإشعار",
    notification_type="general",
    priority="high",
    sender_id=admin_id,
    entity_type="transaction",
    entity_id=123,
    extra_data={"key": "value"}
)

# إرسال لعدة أشخاص
NotificationService.send_notification_to_multiple(
    recipient_ids=[1, 2, 3],
    title="عنوان الإشعار",
    message="نص الإشعار",
    notification_type="general"
)
```

---

## نقاط نهاية API

### للمستخدم العادي

#### الحصول على الإشعارات
```
GET /api/notifications
```

معاملات الاستعلام:
- `is_read` - فلترة حسب القراءة (true/false)
- `type` - نوع الإشعار
- `priority` - أولوية الإشعار
- `limit` - عدد النتائج (افتراضي: 50)
- `offset` - بداية النتائج

#### عدد الإشعارات غير المقروءة
```
GET /api/notifications/unread-count
```

#### تعليم إشعار كمقروء
```
PUT /api/notifications/{id}/read
```

#### تعليم إشعار كغير مقروء
```
PUT /api/notifications/{id}/unread
```

#### تعليم جميع الإشعارات كمقروءة
```
PUT /api/notifications/mark-all-read
```

#### حذف إشعار
```
DELETE /api/notifications/{id}
```

### إعدادات الإشعارات

#### الحصول على الإعدادات
```
GET /api/notifications/settings
```

#### تحديث الإعدادات
```
PUT /api/notifications/settings
```

Body:
```json
{
    "enable_all": true,
    "enable_attendance": true,
    "enable_leave": true,
    "enable_advance": true,
    "enable_reward": true,
    "enable_penalty": true,
    "notify_as_department_head": true,
    "notify_as_department_deputy": true,
    "notify_as_branch_head": true,
    "notify_as_branch_deputy": true
}
```

### للمسؤولين

#### إرسال إشعار لمستخدم محدد
```
POST /api/notifications/send
```

Body:
```json
{
    "recipient_id": 1,
    "title": "عنوان الإشعار",
    "message": "نص الإشعار",
    "type": "general",
    "priority": "medium",
    "entity_type": "transaction",
    "entity_id": 123
}
```

#### إرسال إشعار لرؤساء قسم
```
POST /api/notifications/send-to-department
```

Body:
```json
{
    "department_id": 1,
    "title": "عنوان الإشعار",
    "message": "نص الإشعار",
    "include_deputies": true
}
```

#### إرسال إشعار لرؤساء فرع
```
POST /api/notifications/send-to-branch
```

#### إرسال إشعار لجميع المسؤولين (super_admin فقط)
```
POST /api/notifications/send-to-admins
```

---

## أمثلة تكامل مع الموديلات المختلفة

### عند إضافة حضور جديد
```python
# في routes/attendance.py بعد إضافة سجل حضور
from app.services.notification_service import notify_employee_action, NotificationType

# إذا كان هناك تأخير، أرسل إشعار للمديرين
if attendance.is_late:
    employee = Employee.query.get(employee_id)
    notify_employee_action(
        employee_id=employee_id,
        action_title="تأخر موظف",
        action_message=f"تأخر الموظف {employee.full_name} اليوم {attendance.delay_minutes} دقيقة",
        notification_type=NotificationType.ATTENDANCE.value,
        entity_type="attendance",
        entity_id=attendance.id
    )
```

### عند إضافة مكافأة
```python
# في routes/reward.py بعد إضافة مكافأة
from app.services.notification_service import notify_employee_action, NotificationType

notify_employee_action(
    employee_id=reward.employee_id,
    action_title="مكافأة جديدة",
    action_message=f"تم إضافة مكافأة بقيمة {reward.amount} للموظف",
    notification_type=NotificationType.REWARD.value,
    entity_type="reward",
    entity_id=reward.id
)
```

### عند إضافة جزاء
```python
# في routes/penalty.py بعد إضافة جزاء
from app.services.notification_service import notify_employee_action, NotificationType, NotificationPriority

notify_employee_action(
    employee_id=penalty.employee_id,
    action_title="جزاء جديد",
    action_message=f"تم إضافة جزاء للموظف: {penalty.reason}",
    notification_type=NotificationType.PENALTY.value,
    priority=NotificationPriority.HIGH.value,
    entity_type="penalty",
    entity_id=penalty.id
)
```

### عند طلب سلفة
```python
# في routes/advance.py بعد طلب سلفة
from app.services.notification_service import notify_employee_action, NotificationType

notify_employee_action(
    employee_id=advance.employee_id,
    action_title="طلب سلفة جديد",
    action_message=f"قام الموظف بطلب سلفة بقيمة {advance.amount}",
    notification_type=NotificationType.ADVANCE.value,
    entity_type="advance",
    entity_id=advance.id
)
```

---

## ملاحظات هامة

1. **التفعيل التلقائي**: الإشعارات مفعلة افتراضياً لجميع المستخدمين
2. **التحكم**: كل مستخدم يمكنه تعطيل أنواع معينة من الإشعارات من إعداداته
3. **الأدوار**: يتم إرسال الإشعارات حسب الأدوار (رئيس قسم، نائب، رئيس فرع، إلخ)
4. **الحذف**: الإشعارات المقروءة القديمة (أكثر من 30 يوماً) يمكن حذفها تلقائياً
5. **الأداء**: استخدم `lazy='dynamic'` للعلاقات لتجنب تحميل كميات كبيرة من البيانات

---

## أوامر CLI

### حذف الإشعارات القديمة
```bash
flask notifications-cleanup --days=30
```

## إنشاء Migration
بعد إضافة النظام، نفذ:
```bash
flask db migrate -m "Add notifications system"
flask db upgrade
```

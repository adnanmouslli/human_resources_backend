# 🎯 برومبت احترافي لمطور Frontend - نظام الإشعارات

## 📋 نظرة عامة على المشروع

نظام HR متكامل للمؤسسات، والجزء المطلوب الآن هو **واجهة إشعارات احترافية** للمدراء فقط.

### الفئات المستهدفة (المستخدمون):
- `super_admin` - مدير النظام
- `branch_head` - رئيس فرع
- `branch_deputy` - نائب رئيس فرع  
- `department_head` - رئيس قسم
- `department_deputy` - نائب رئيس قسم

> **ملاحظة**: لا يوجد وصول للموظفين العاديين (`employee`) في هذه الواجهة.

---

## 🔔 متطلبات واجهة الإشعارات

### 1. شريط الإشعارات العلوي (Notification Bell Component)

في شريط التنقل العلوي (Navbar) يجب إضافة:

```
🔔 [أيقونة الجرس] 
   └─> Badge أحمر صغير يظهر عدد الإشعارات غير المقروءة
   └─> dropdown عند النقر يعرض:
       - أحدث 5-10 إشعارات
       - زر "عرض الكل" في الأسفل
       - زر "تعليم الكل كمقروء" 
       - تقسيم: إشعارات غير مقروءة / إشعارات مقروءة
```

**المتطلبات الوظيفية:**
- تحديث تلقائي للعداد كل 30-60 ثانية (Polling)
- إخفاء Badge عندما يكون العدد = 0
- تغيير لون الإشعار غير المقروء (خلفية مميزة)
- تاريخ الإشعار بالشكل النسبي ("منذ 5 دقائق")

---

## 🔌 نقاط النهاية (Endpoints) التفصيلية

### 🔶 1. الحصول على عدد الإشعارات غير المقروءة

```http
GET /api/notifications/unread-count
```

**الهيدرز المطلوبة:**
```
Authorization: Bearer <token>
```

**الاستجابة:**
```json
{
  "unread_count": 5
}
```

**الاستخدام:**
- لعرض الرقم على Badge أيقونة الجرس
- تحديث مستمر (Polling) كل 30 ثانية

---

### 🔶 2. الحصول على قائمة الإشعارات

```http
GET /api/notifications
```

**معاملات الاستعلام (Query Parameters):**
| المعامل | القيمة | الوصف |
|---------|--------|-------|
| `is_read` | `true` / `false` | فلترة حسب القراءة |
| `type` | `leave` / `advance` / `attendance` / ... | نوع الإشعار |
| `priority` | `low` / `medium` / `high` / `urgent` | الأولوية |
| `limit` | عدد (افتراضي: 50) | عدد النتائج |
| `offset` | عدد (افتراضي: 0) | للتصفح |

**الاستجابة:**
```json
{
  "notifications": [
    {
      "id": 1,
      "title": "طلب إجازة جديد",
      "message": "قام أحمد بطلب إجازة من 2025-01-20 إلى 2025-01-25",
      "notification_type": "leave",
      "priority": "medium",
      "is_read": false,
      "read_at": null,
      "entity_type": "leave",
      "entity_id": 123,
      "extra_data": {
        "leave_type": "annual",
        "days_count": 5
      },
      "created_at": "2025-01-15T10:30:00",
      "recipient": {
        "id": 5,
        "username": "manager1"
      }
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

**أنواع الإشعارات المتاحة (مع الألوان/الأيقونات المقترحة):**
| النوع | اللون | الأيقونة | الاستخدام |
|-------|-------|----------|-----------|
| `general` | رمادي | ⚙️ | إشعارات عامة |
| `leave` | أزرق | 🏖️ | إجازات |
| `advance` | أخضر | 💰 | سلف |
| `reward` | ذهبي | 🎁 | مكافآت |
| `penalty` | أحمر | ⚠️ | جزاءات |
| `attendance` | برتقالي | 🕐 | حضور/تأخر |
| `absence` | أحمر داكن | ❌ | غياب |
| `transaction` | بنفسجي | 📄 | معاملات |
| `production` | أزرق سماوي | 🏭 | إنتاج |
| `kpi` | وردي | 📊 | تقييمات |
| `system` | رمادي داكن | 🔧 | إشعارات النظام |

**أولويات الإشعارات (مع الألوان):**
| الأولوية | اللون | الاستخدام |
|----------|-------|-----------|
| `low` | رمادي | منخفضة |
| `medium` | أزرق | متوسطة |
| `high` | برتقالي | عالية |
| `urgent` | أحمر | عاجلة |

---

### 🔶 3. تعليم إشعار كمقروء

```http
PUT /api/notifications/{id}/read
```

**الهيدرز:**
```
Authorization: Bearer <token>
```

**الاستجابة:**
```json
{
  "message": "تم تعليم الإشعار كمقروء",
  "notification_id": 1
}
```

**الاستخدام:**
- عند النقر على إشعار في القائمة
- تقليل العداد مباشرة في الواجهة (Optimistic Update)

---

### 🔶 4. تعليم جميع الإشعارات كمقروءة

```http
PUT /api/notifications/mark-all-read
```

**معاملات الاستعلام:**
| المعامل | الوصف |
|---------|-------|
| `type` | (اختياري) تعليم نوع محدد فقط |

**الاستجابة:**
```json
{
  "message": "تم تعليم 5 إشعارات كمقروءة",
  "marked_count": 5
}
```

**الاستخدام:**
- زر "تعليم الكل كمقروء" في Dropdown
- إعادة تعيين العداد إلى 0

---

### 🔶 5. تعليم إشعار كغير مقروء

```http
PUT /api/notifications/{id}/unread
```

**الاستخدام:**
- في صفحة الإشعارات الكاملة للتراجع عن القراءة

---

### 🔶 6. حذف إشعار

```http
DELETE /api/notifications/{id}
```

**الاستجابة:**
```json
{
  "message": "تم حذف الإشعار بنجاح",
  "notification_id": 1
}
```

---

### 🔶 7. الحصول على إعدادات الإشعارات

```http
GET /api/notifications/settings
```

**الاستجابة:**
```json
{
  "settings": {
    "user_id": 5,
    "enable_all": true,
    "enable_attendance": true,
    "enable_leave": true,
    "enable_advance": true,
    "enable_reward": true,
    "enable_penalty": true,
    "enable_transaction": true,
    "enable_absence": true,
    "enable_production": true,
    "enable_system": true,
    "enable_kpi": true,
    "notify_as_department_head": true,
    "notify_as_department_deputy": true,
    "notify_as_branch_head": true,
    "notify_as_branch_deputy": true
  }
}
```

**الاستخدام:**
- صفحة الإعدادات الشخصية
- toggles لتفعيل/تعطيل كل نوع

---

### 🔶 8. تحديث إعدادات الإشعارات

```http
PUT /api/notifications/settings
```

**الهيدرز:**
```
Content-Type: application/json
Authorization: Bearer <token>
```

**الBody:**
```json
{
  "enable_all": true,
  "enable_attendance": true,
  "enable_leave": false,
  "notify_as_department_deputy": false
}
```

**ملاحظة:** أرسل فقط الحقول التي تريد تغييرها.

---

### 🔶 9. إرسال إشعار يدوي (للمسؤولين فقط)

```http
POST /api/notifications/send
```

**الBody:**
```json
{
  "recipient_id": 10,
  "title": "عنوان الإشعار",
  "message": "نص الإشعار التفصيلي",
  "type": "general",
  "priority": "high",
  "entity_type": "leave",
  "entity_id": 123
}
```

**الاستخدام:**
- نموذج إرسال إشعار لمستخدم محدد
- متاح فقط لـ super_admin والمدراء

---

### 🔶 10. إرسال إشعار لرؤساء قسم

```http
POST /api/notifications/send-to-department
```

**الBody:**
```json
{
  "department_id": 3,
  "title": "تنبيه هام",
  "message": "اجتماع غداً الساعة 10 صباحاً",
  "include_deputies": true
}
```

---

### 🔶 11. إرسال إشعار لرؤساء فرع

```http
POST /api/notifications/send-to-branch
```

**الBody:**
```json
{
  "branch_id": 2,
  "title": "تقرير شهري",
  "message": "تم إعداد التقرير الشهري",
  "include_deputies": true
}
```

---

## 🎨 تصميم الواجهات المطلوبة

### الواجهة 1: شريط الإشعارات (Navbar Notification Bell)

```
┌─────────────────────────────────────┐
│  Logo    Dashboard   [🔔 5]  👤 Admin│
└─────────────────────────────────────┘
            │
            ▼ (عند النقر)
┌──────────────────────────────────────┐
│ 📌 الإشعارات الجديدة           [الكل] │
├──────────────────────────────────────┤
│ 🏖️ طلب إجازة جديد          منذ 5 دق│
│    أحمد محمد - قسم المبيعات      [×]│
├──────────────────────────────────────┤
│ 💰 طلب سلفة               منذ ساعة  │
│    خالد علي - فرع دمشق          [×] │
├──────────────────────────────────────┤
│ 📊 تقرير شهري جاهز        أمس      │
│    تم إعداد تقرير شهر يناير       [×]│
├──────────────────────────────────────┤
│ [    تعليم الكل كمقروء    ]          │
│ [     عرض جميع الإشعارات   ]         │
└──────────────────────────────────────┘
```

**المكونات:**
- أيقونة جرس مع Badge أحمر (عداد)
- Dropdown قائمة منسدلة
- عناصر الإشعارات مع:
  - أيقونة حسب النوع
  - العنوان (غامق للغير مقروء)
  - النص (مختصر)
  - التاريخ النسبي
  - زر "×" لحذف سريع
- أزرار أسفل للإجراءات الجماعية

---

### الواجهة 2: صفحة الإشعارات الكاملة

**التخطيط:**
```
┌─────────────────────────────────────────────────────────────┐
│                     الإشعارات 🔔                            │
├─────────────────────────────────────────────────────────────┤
│ [ الكل ▼ ] [ 📅 الأسبوع ] [🔍 بحث... ] [✓ تعليم الكل مقروء] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 🏖️ طلب إجازة جديد                        15 يناير   │  │
│  │                                                      │  │
│  │ أحمد محمد من قسم المبيعات قدم طلب إجازة سنوية       │  │
│  │ من 20 يناير إلى 25 يناير (5 أيام)                   │  │
│  │                                                      │  │
│  │ [عرض الطلب] [تعليم مقروء] [حذف]          [جديد] 🔴  │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 💰 طلب سلفة                              14 يناير   │  │
│  │                                                      │  │
│  │ خالد علي طلب سلفة بقيمة 500,000 ل.س                 │  │
│  │ السبب: طوارئ صحية                                    │  │
│  │                                                      │  │
│  │ [عرض السلفة] [تعليم مقروء] [حذف]                   │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**عناصر التصفية:**
- Tabs: الكل | غير المقروءة | مقروءة
- فلتر حسب النوع (Dropdown)
- فلتر حسب الأولوية
- فلتر حسب التاريخ
- بحث نصي

**عناصر كل إشعار:**
- أيقونة النوع (كبيرة)
- العنوان
- الرسالة الكاملة
- الوقت الكامل (تاريخ + وقت)
- Badges: الأولوية + الجديد/مقروء
- أزرار الإجراءات

---

### الواجهة 3: صفحة إعدادات الإشعارات

```
┌──────────────────────────────────────────────────────┐
│                  إعدادات الإشعارات ⚙️                 │
├──────────────────────────────────────────────────────┤
│                                                      │
│  [✓] تفعيل جميع الإشعارات                           │
│                                                      │
│  ──── أنواع الإشعارات ────                          │
│                                                      │
│  [✓] إشعارات الحضور والغياب   [✓] إشعارات الإجازات │
│  [✓] إشعارات السلف            [✓] إشعارات المكافآت │
│  [✓] إشعارات الجزاءات         [✓] إشعارات المعاملات│
│  [✓] إشعارات الإنتاج          [✓] إشعارات KPI      │
│  [✓] إشعارات النظام                                 │
│                                                      │
│  ──── الإشعارات حسب الدور ────                      │
│                                                      │
│  [✓] استلام إشعارات كرئيس قسم                       │
│  [✓] استلام إشعارات كنائب رئيس قسم                  │
│  [✓] استلام إشعارات كرئيس فرع                       │
│  [✓] استلام إشعارات كنائب رئيس فرع                  │
│                                                      │
│              [ حفظ الإعدادات ]                      │
│                                                      │
└──────────────────────────────────────────────────────┘
```

---

## 🔧 منطق العميل (Client-side Logic)

### 1. جلب العداد الأولي
```javascript
// عند تحميل التطبيق
async function fetchUnreadCount() {
  const response = await fetch('/api/notifications/unread-count', {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  const data = await response.json();
  updateBadge(data.unread_count);
}
```

### 2. تحديث دوري (Polling)
```javascript
// كل 30 ثانية
setInterval(fetchUnreadCount, 30000);
```

### 3. تعليم مقروء عند النقر (Optimistic Update)
```javascript
async function markAsRead(notificationId) {
  // تحديث الواجهة فوراً
  hideBadge();
  removeUnreadStyle(notificationId);
  
  // إرسال الطلب للخادم
  await fetch(`/api/notifications/${notificationId}/read`, {
    method: 'PUT',
    headers: { 'Authorization': `Bearer ${token}` }
  });
}
```

### 4. تنسيق التاريخ النسبي
```javascript
function formatRelativeTime(dateString) {
  const date = new Date(dateString);
  const now = new Date();
  const diff = Math.floor((now - date) / 1000);
  
  if (diff < 60) return 'الآن';
  if (diff < 3600) return `منذ ${Math.floor(diff/60)} دقيقة`;
  if (diff < 86400) return `منذ ${Math.floor(diff/3600)} ساعة`;
  if (diff < 604800) return `منذ ${Math.floor(diff/86400)} يوم`;
  return date.toLocaleDateString('ar-SY');
}
```

---

## 🎨 الألوان والتصميم المقترح (Tailwind CSS)

```css
/* أنواع الإشعارات */
.notification-general { @apply bg-gray-100 text-gray-800; }
.notification-leave { @apply bg-blue-100 text-blue-800; }
.notification-advance { @apply bg-green-100 text-green-800; }
.notification-reward { @apply bg-yellow-100 text-yellow-800; }
.notification-penalty { @apply bg-red-100 text-red-800; }
.notification-attendance { @apply bg-orange-100 text-orange-800; }
.notification-absence { @apply bg-red-200 text-red-900; }
.notification-transaction { @apply bg-purple-100 text-purple-800; }
.notification-production { @apply bg-sky-100 text-sky-800; }
.notification-kpi { @apply bg-pink-100 text-pink-800; }
.notification-system { @apply bg-gray-200 text-gray-900; }

/* الأولويات */
.priority-low { @apply border-l-4 border-gray-400; }
.priority-medium { @apply border-l-4 border-blue-500; }
.priority-high { @apply border-l-4 border-orange-500; }
.priority-urgent { @apply border-l-4 border-red-600; }

/* حالة القراءة */
.notification-unread { @apply bg-blue-50 font-semibold; }
.notification-read { @apply bg-white text-gray-600; }
```

---

## 📱 التجاوب (Responsive)

### سطح المكتب (>1024px):
- Dropdown واسع (400px)
- صفحة الإشعارات: شريط جانبي + محتوى

### الجوال (<768px):
- Dropdown بعرض الشاشة
- Modal بدلاً من Dropdown
- تصميم بطاقات متراصة

---

## 🔐 معالجة الأخطاء

### انتهاء الجلسة (401):
```javascript
if (response.status === 401) {
  redirectToLogin();
}
```

### فقدان الاتصال:
- عرض "لا يوجد اتصال بالإنترنت"
- إعادة المحاولة تلقائياً

### الأخطاء العامة:
- Toast notification يظهر الخطأ
- تسجيل الخطأ في Console

---

## 📝 ملخص التقنيات المقترحة

| المكون | التقنية المقترحة |
|--------|-----------------|
| Framework | React / Vue / Angular |
| UI Library | Tailwind CSS + Headless UI |
| Icons | Lucide React / Heroicons |
| State Management | Context API / Redux / Pinia |
| HTTP Client | Axios / Fetch |
| Date Format | date-fns (Arabic locale) |
| Polling | setInterval / React Query |
| Notifications | react-hot-toast / vue-toastification |

---

## ✅ قائمة التحقق (Checklist)

- [ ] عرض Badge العداد في Navbar
- [ ] تحديث العداد كل 30 ثانية
- [ ] Dropdown الإشعارات يعمل بشكل صحيح
- [ ] صفحة الإشعارات الكاملة مع التصفية
- [ ] صفحة إعدادات الإشعارات
- [ ] تعليم مقروء فردي وجماعي
- [ ] حذف الإشعارات
- [ ] تنسيق التاريخ النسبي (منذ X دقيقة)
- [ ] ألوان مختلفة لكل نوع إشعار
- [ ] أيقونات مختلفة لكل نوع إشعار
- [ ] تجاوب كامل مع الجوال
- [ ] معالجة أخطاء الـ API
- [ ] رسائل "لا توجد إشعارات" فارغة
- [ ] Skeleton loading أثناء التحميل

---

**🚀 النظام جاهز للتكامل!**

# BioZone — تتبع تنفيذ ROADMAP.md

> **الغرض:** ملف واحد يوضح فين وصلنا بالظبط في كل مرحلة، عشان محدش (ولا حتى Claude في محادثة جديدة) يحتاج يتقال له الحالة من الأول كل مرة. حدّث الجدول ده مع كل تسليم فعلي (مش تخطيط).

**آخر تحديث:** 27 يوليو 2026

---

## نظرة سريعة

| المرحلة | الحالة | ملاحظة |
|---|---|---|
| 1 — تعميم الـ Pattern الموجود | ✅ **مكتملة** | breadcrumbs + tabs + عدادات على المنتجات والمخزون. لا يوجد app موردين في المشروع أصلًا. |
| 2 — بنية تحتية (Audit + Chatter + Relations) | 🟡 **جزئية** | البنية التحتية + منتجات + عملاء جاهزين. باقي: تطبيق migration على قاعدة بيانات حقيقية + مراجعة نهائية. |
| 3 — ترقية الجداول | ⬜ لم يبدأ | |
| 4 — Lifecycle + Action Bar | ⬜ لم يبدأ | تبني على مرحلة 2 |
| 5 — تحسينات واجهة المتجر | ⬜ لم يبدأ | تحتاج migration |
| 6 — الحد الأدنى للطلب لكل عميل | ⬜ لم يبدأ | تحتاج migration |
| 7 — أتمتة ومتابعة | ⬜ لم يبدأ | آخر أولوية |

---

## مرحلة 1 — تعميم الـ Pattern الموجود
**الحالة: ✅ مكتملة**

- تأكيد: `staff/templates/staff/products/form.html` و `staff/templates/staff/inventory/detail.html` فيهم نفس نمط breadcrumbs + notebook tabs + عدادات زي `clients/detail.html`.
- لا يوجد app/موديل للموردين في المشروع حاليًا، فبند "الموردين" في المرحلة غير منطبق (مفيش حاجة تتعمم عليها).
- معيار القبول محقق: كل صفحة تفاصيل موجودة (منتج، صنف مخزون) عندها نفس بنية التابات والعدادات.

---

## مرحلة 2 — بنية تحتية (Audit + Chatter + Relations)
**الحالة: 🟡 جزئية — البنية التحتية + منتجات + عملاء تمت، الباقي محدد تحت**

### ✅ اتعمل

**App جديد `activity/`** (Generic Audit Log + Chatter، ContentType-based):
- `activity/models.py` — موديل `ActivityLog` واحد يشتغل على أي كيان (CREATED / UPDATED / NOTE) بدل ما يفضل `OrderLog` مقفول على الطلبات.
- `activity/services.py` — `log_activity()`, `log_created()`, `log_note()`, `diff_summary()` (الواجهة الوحيدة المفروض أي view يستخدمها).
- `activity/views.py` + `activity/urls.py` — endpoint عام واحد `activity:add_note` لإضافة ملاحظة (Chatter) على أي سجل، بدل view منفصل لكل قسم.
- `activity/templatetags/activity_tags.py` + `activity/templates/activity/_panel.html` — تاج `{% activity_panel obj %}` قابل لإعادة الاستخدام (تايم لاين + فورم ملاحظة).
- `activity/admin.py` — سجل للمراجعة، read-only (الإدخال من الكود بس، مش يدوي من admin).
- Migration: `activity/migrations/0001_initial.py` (اتولّدت واتفحصت بـ `makemigrations --check` — **لسه محتاجة تتطبّق فعليًا بـ `migrate` على قاعدة بيانات المشروع الحقيقية**، الصلاحيات دي مش متاحة من بيئة التطوير الحالية).
- مسجّلة في `INSTALLED_APPS` (`config/settings.py`) و `config/urls.py` (`path('activity/', include('activity.urls'))`).

**تطبيق على المنتجات** (`staff/views/products/crud.py`, `staff/templates/staff/products/form.html`):
- `product_add`: يسجّل `CREATED`.
- `product_edit`: ياخد نسخة من القيم المتابَعة (`PRODUCT_TRACKED_FIELDS`) قبل الحفظ، ويسجّل `UPDATED` بملخص التغيير الفعلي (`diff_summary`) — بس لو فيه تغيير حقيقي.
- تاب "النشاط" جديد في `form.html` (وضع التعديل بس) بيعرض `{% activity_panel product %}`.
- **Related Documents:** قسم "مستندات ذات صلة" في تاب "بيانات المنتج" — رابط لسجل المخزون (`inventory_item`) وآخر 8 طلبات فيها صنف من المنتج (`related_orders`، عبر `OrderItem.product_unit__product`).

**تطبيق على العملاء** (`staff/views/clients.py`, `staff/templates/staff/clients/detail.html`):
- `client_approve` / `client_reject`: يسجّلوا `UPDATED` بملخص ("تفعيل الحساب" / "رفض الحساب").
- تاب "النشاط" جديد في `clients/detail.html` بيعرض `{% activity_panel profile %}`.
- ملاحظة تصميم: عمليات الدفع/التسوية المالية (`client_add_payment`/`client_add_adjustment`) **ماتسجلش** في `ActivityLog` عن قصد — عندها تايم لاين خاص بيها بالفعل في تاب "حسابي المالي" (`AccountTransaction`)، والتكرار هيبقى ضوضاء زيادة من غير فايدة.

### ⬜ باقي في مرحلة 2

1. **تطبيق الـ migration فعليًا** على بيئة فيها اتصال حقيقي بقاعدة البيانات (Postgres) — اتعملت وانفحصت هنا بس بـ sqlite مؤقت لعدم توفر بيانات اتصال.
2. **مراجعة يدوية/QA** على السيرفر الفعلي: افتح منتج/عميل، اتأكد إن التاب بيفتح، جرب إضافة ملاحظة، جرب تعديل بيانات وشوف الملخص بيتسجل صح.
3. لو حبيتوا تعمموا نفس النمط على كيانات تانية غير منتج/عميل (لو ظهرت لاحقًا)، الخطوات صارت مكرورة وسريعة:
   - `from activity.services import log_activity, diff_summary` في الـ view.
   - `{% load activity_tags %}{% activity_panel obj %}` في التمبلت.
   - إضافة `activity_count` للـ context لو عايز تاب فيه عداد.
4. معيار القبول **متحقق جزئيًا** الآن: فتح منتج أو عميل يوريك نشاطه (مين عدّل إيه وإمتى) وتقدر تسيب ملاحظة داخلية — باقي بس التأكيد بعد الـ migrate الفعلي على السيرفر.

### 🔍 ثغرات اتلقت واتصلحت بعد مراجعة إضافية (27 يوليو)

مراجعة شاملة على كل مسار ممكن يعدّل منتج أو عميل، مش بس اللي كان اتجرب الأول:

1. **الاستيراد الجماعي من Excel كان مايسجّلش نشاط خالص** — `products/services/import_export/commit.py` بيحفظ المنتج مباشرة (`Product.objects.create`) مش عن طريق `product_add`/`product_edit`، فمكنش بيمر على تسجيل النشاط. **اتصلح:** بيسجّل CREATED للصنف الجديد، UPDATED (بملاحظة عامة "تحديث من ملف Excel") للصنف الموجود.
2. **حذف وحدة (Unit) أثناء تعديل منتج كان بيحصل بصمت** — الفورمست بيسمح بحذف وحدة (`can_delete=True`) بس الكود الأول كان بيقارن بس الوحدات الموجودة بعد الحفظ. **اتصلح:** `_unit_prices_diff_summary` دلوقتي بيكتشف الوحدات المحذوفة ويسجّل "تم حذف وحدة (اسمها)".
3. **حذف منتج كامل كان بيسيب سجلات نشاط يتيمة** — الربط بـ `ActivityLog` عن طريق ContentType عام (object_id) مش FK حقيقي، فمفيش CASCADE تلقائي وقت حذف المنتج. **اتصلح:** أضيفت `activity.services.delete_activity_logs_for(instance)` وبتتنادى في `product_delete` قبل `product.delete()` — أي delete view جديد لازم يستخدمها بنفس الطريقة (اتوثقت في الدالة نفسها).

الثلاثة إصلاحات دي اتفحصت فعليًا (functional test عبر Django test client + سيناريوهات حقيقية) مش بس نظريًا — النتائج موثقة في نفس المحادثة.

### خارج نطاق مرحلة 2 عن قصد (مش ثغرات)
- الأقسام (`Category`) مش متتبّعة — معيار القبول في ROADMAP.md حدد "عميل/منتج" بس.
- مفيش view لتعديل بيانات العميل نفسه (اسم النشاط، نوع الحساب) في الكود أصلًا، فمفيش حاجة تتراقب هناك حاليًا.

### 🆕 إضافة صغيرة خارج المراحل — دعم الباركود في استيراد/تصدير Excel (27 يوليو)

طلب مباشر من صاحب المنتج (مش جزء من مرحلة معينة في ROADMAP.md، بس مربوط بنفس نقاش كود الصنف/الباركود):

- عمود `barcode` جديد جنب `code` في: التصدير (`export.py`)، القالب الفارغ (`build_import_template_workbook`)، والقراءة (`parsing.py`).
- عمود اختياري تمامًا (مش ضمن `REQUIRED_IMPORT_HEADERS`) — الملفات القديمة من غيره تفضل شغالة عادي.
- **عند التحديث:** لو الخلية فاضية، الباركود المسجّل يفضل زي ما هو (مش بيتمسح) — عكس `name_ar`/`category` اللي بيتكتبوا زي ما هما في الملف دايمًا.
- **حماية من التعارض:** لو الباركود متكرر في نفس الملف، أو مستخدم بالفعل لصنف تاني في القاعدة، الصف نفسه بيتحفظ عادي بس من غير الباركود ده + تحذير واضح في صفحة الأخطاء بعد الاستيراد (بدل ما `IntegrityError` توقف الدفعة *كلها* زي ما كانت هتعمل قبل الإصلاح ده).
- واجهة صفحة الاستيراد (`import.html`) اتحدثت بشرح العمود الجديد.
- اتفحص functional (round-trip كامل: تصدير قالب → استيراد → تعارض باركود موجود وتعارض داخل نفس الملف) — النتائج موثقة في المحادثة.

### ملفات اتلمست في مرحلة 2

```
activity/                              (جديد بالكامل)
├── models.py, services.py, views.py, urls.py, admin.py, apps.py
├── migrations/0001_initial.py
└── templatetags/activity_tags.py
    templates/activity/_panel.html
config/settings.py                     (+ 'activity' في INSTALLED_APPS)
config/urls.py                         (+ include('activity.urls'))
staff/views/products/crud.py           (+ log CREATED/UPDATED + related docs helpers)
staff/templates/staff/products/form.html   (+ تاب النشاط + قسم مستندات ذات صلة)
staff/views/clients.py                 (+ log UPDATED عند approve/reject + activity_count)
staff/templates/staff/clients/detail.html  (+ تاب النشاط)
```

---

## مرحلة 3 — ترقية الجداول
**الحالة: ⬜ لم يبدأ**
لا يوجد عمل بعد. راجع ROADMAP.md قسم "مرحلة 3" للتفاصيل الكاملة (sortable, sticky header, pagination, bulk actions, Quick Edit inline).

## مرحلة 4 — Lifecycle + Action Bar
**الحالة: ⬜ لم يبدأ**
تعتمد على موديل `ActivityLog` من مرحلة 2 (جاهز)، وعلى موديل `Tag` عام لسه مش موجود.

## مرحلة 5 — تحسينات واجهة المتجر
**الحالة: ⬜ لم يبدأ**
تحتاج migration جديد (`Product.similar_products`, `complementary_products`, `size`, `ProductVariantGroup`) وتصميم UI بالكامل. لسه معملش أي حاجة.

## مرحلة 6 — الحد الأدنى للطلب لكل عميل
**الحالة: ⬜ لم يبدأ**
تحتاج migration جديد (`ClientProfile.min_order_amount`) وتعديل `orders/views/cart.py` و`checkout.py`. لسه معملش أي حاجة.

## مرحلة 7 — أتمتة ومتابعة
**الحالة: ⬜ لم يبدأ**
آخر أولوية في الخطة الأصلية.

---

## ملاحظة لأي محادثة جديدة مع Claude

ابدأ بقراءة الجدول في أول الملف ده، وبعدين اقرا "باقي في مرحلة 2" فوق قبل ما تكمل أي حاجة فيها — بعد كده أول حاجة منطقية هي: تطبيق migration مرحلة 2 على السيرفر الفعلي، أو البدء في مرحلة 3 (مستقلة تمامًا وممكن تتوازى مع أي حد بيشتغل على مرحلة 5/6).

from decimal import Decimal, ROUND_HALF_UP

from django.db import models
from django.core.validators import FileExtensionValidator
from django.utils import timezone

from .matching import normalize_name
from .validators import validate_image_size


class Category(models.Model):
    name = models.CharField(max_length=255)
    image = models.ImageField(
        upload_to='categories/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp']), validate_image_size]
    )
    slug = models.SlugField(unique=True, allow_unicode=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'قسم'
        verbose_name_plural = 'الأقسام'
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='products',
    )
    # كود صنف فريد بيتولّد تلقائيًا لكل منتج (BZ-00001, BZ-00002, ...).
    # الهدف منه: identifier ثابت للصنف مستقل تمامًا عن اسمه — لو حبيت تصحّح
    # أو تغيّر اسم صنف موجود بالكامل (في التعديل اليدوي أو برفع شيت إكسل
    # فيه عمود code)، النظام لسه بيعرف إنه نفس الصنف وميعملوش نسخة جديدة.
    code = models.CharField(max_length=20, unique=True, editable=False, blank=True)
    # باركود فعلي (EAN/UPC أو أي كود مطبوع على عبوة المنتج) — مختلف تمامًا
    # عن code فوق (كود داخلي بيتولّد تلقائيًا للنظام نفسه). ده بيتسجّل يدويًا
    # (أو بالاسكانر وقت الإدخال) وبيُستخدم في البحث بالاسكانر في المخزون.
    # blank/null=True لأن مش كل الأصناف عندها باركود مسجّل، وunique بس لو
    # القيمة موجودة فعلاً (null مسموح يتكرر بدون تعارض).
    barcode = models.CharField(
        max_length=64, unique=True, null=True, blank=True, db_index=True,
        verbose_name='الباركود',
        help_text='باركود العبوة (اختياري) — يمكن مسحه بقارئ الباركود عند البحث في المخزون',
    )
    name_ar = models.CharField(max_length=255)
    # نسخة مُطبَّعة من name_ar (بدون فراغات زيادة/فروق أرقام وحروف شكلية)
    # بتتحسب تلقائيًا في save() وبتُستخدم في مطابقة الاستيراد من إكسل —
    # راجع products/matching.py و staff/views/products.py.
    name_key = models.CharField(max_length=255, editable=False, blank=True, db_index=True)
    name_en = models.CharField(max_length=255, blank=True)
    manufacturer = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(
        upload_to='products/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp']), validate_image_size]
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # آخر لحظة اعتُبر فيها المنتج "وارد جديد" — بتتحدّث لحظة الإنشاء لأول
    # مرة، ولحظة أي تزويد رصيد بعد كده (راجع inventory.models.StockMovement.save).
    # صفحة "الوارد" في المتجر (store app) بتعرض أي منتج تاريخه هنا في آخر
    # فترة معيّنة — مفيش جدول أو حالة منفصلة، مجرد فلتر بالتاريخ.
    new_arrival_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = 'منتج'
        verbose_name_plural = 'المنتجات'
        ordering = ['name_ar']

    @property
    def display_name(self):
        return self.name_en or self.name_ar

    def __str__(self):
        return self.display_name

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        self.name_key = normalize_name(self.name_ar)
        # نحوّل الباركود الفاضي لـ None (مش '') عشان قيد unique متعدد لا
        # يتعارض بين أصناف كتير مالهاش باركود مسجّل أصلاً.
        if self.barcode is not None:
            self.barcode = self.barcode.strip() or None
        if not self.code:
            self._assign_code()
        if is_new and self.new_arrival_at is None:
            self.new_arrival_at = timezone.now()
        super().save(*args, **kwargs)

    def _assign_code(self):
        """
        بيولّد أول كود فريد متاح بصيغة BZ-00001. بيحاول كذا مرة عند تعارض
        نادر (سباق بين طلبين بيحفظوا في نفس اللحظة) بدل ما يفشل الحفظ كله.
        """
        prefix = 'BZ-'
        for _ in range(5):
            last = (
                Product.objects.filter(code__startswith=prefix)
                .order_by('-code')
                .values_list('code', flat=True)
                .first()
            )
            next_num = 1
            if last:
                try:
                    next_num = int(last.replace(prefix, '')) + 1
                except ValueError:
                    next_num = Product.objects.filter(code__startswith=prefix).count() + 1
            self.code = f'{prefix}{next_num:05d}'
            if not Product.objects.filter(code=self.code).exists():
                return

    def units_for_client(self, client):
        """
        الوحدة (أو الوحدات) المفروض تظهر للعميل ده في المتجر/السلة، حسب
        الوحدة الافتراضية المحدّدة لنوع حسابه (AccountType.default_unit_size):
        - صغرى: أصغر وحدة متاحة (أو الوحدة الوحيدة لو المنتج بوحدة واحدة بس).
        - كبرى: أكبر وحدة متاحة، أو الصغرى لو المنتج مالوش وحدة كبرى أصلًا.
        عميل بدون profile (أو غير مسجل) بياخد الوحدة الصغرى افتراضيًا.
        بترجع list (ممكن تكون فاضية لو المنتج مالوش وحدات) عشان تسهّل استخدامها
        في templates بـ {% for %} أو {{ list.0 }}.
        """
        # ملحوظة أداء: بنستخدم self.units.all() (مش .order_by() جديد) عشان لو
        # الـ view عامل prefetch_related('units')، بنستفيد من الكاش الجاهز بدل
        # ما نضرب استعلام SQL إضافي لكل منتج في صفحة المتجر (N+1).
        units = sorted(self.units.all(), key=lambda u: u.qty_in_small)
        if not units:
            return []
        profile = getattr(client, 'client_profile', None)
        account_type = getattr(profile, 'account_type', None)
        wants_large = bool(account_type and account_type.default_unit_size == account_type.UnitSize.LARGE)
        return [units[-1]] if wants_large else [units[0]]

    @property
    def largest_unit(self):
        """
        أكبر وحدة بيع متاحة للمنتج (الوحدة الكبرى/الكرتونة لو موجودة، وإلا
        الوحدة الوحيدة المتاحة). None لو المنتج مالوش أي وحدة أصلًا.
        """
        units = sorted(self.units.all(), key=lambda u: u.qty_in_small)
        return units[-1] if units else None

    @property
    def smallest_unit(self):
        """أصغر وحدة بيع متاحة للمنتج (القطعة عادةً). None لو مفيش وحدات."""
        units = sorted(self.units.all(), key=lambda u: u.qty_in_small)
        return units[0] if units else None


class ProductUnit(models.Model):
    class Size(models.TextChoices):
        SMALL = 'S', 'صغرى'
        LARGE = 'L', 'كبرى'

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='units',
    )
    size = models.CharField(max_length=1, choices=Size.choices)
    name = models.CharField(max_length=100)
    qty_in_small = models.PositiveIntegerField(
        default=1,
        verbose_name='الكمية بالقطعة',
        help_text=(
            'كام قطعة (وحدة صغرى) داخل الوحدة دي؟ الوحدة الصغرى نفسها = 1 دايمًا. '
            'الوحدة الكبرى (الكرتونة) = عدد القطع فيها، مثلاً 50. هذا الرقم هو '
            'معامل التحويل المعتمد عليه في كل حساب مخزون (الرصيد الحقيقي محفوظ '
            'بالقطعة دايمًا، بغض النظر عن الوحدة اللي بيتم البيع بيها).'
        ),
    )
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    # سعر التكلفة (الشراء) لنفس هذه الوحدة بالظبط (نفس مستوى unit_price —
    # مش بالضرورة بالقطعة). اختياري (افتراضي صفر) عشان مايكسرش أي منتج قديم
    # مسجّل قبل إضافة الحقل ده؛ لو اتسيب صفر، تقارير الربح (reports app)
    # هتحسب ربح = 100% من الإيراد لهذا الصنف لحد ما يتسجّل سعر تكلفته الحقيقي.
    cost_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='سعر التكلفة',
        help_text='سعر شراء هذه الوحدة (يُستخدم في حساب الربح بتقارير المبيعات). اتركه صفرًا لو غير معروف حاليًا.',
    )

    class Meta:
        verbose_name = 'وحدة'

        verbose_name_plural = 'الوحدات'
        constraints = [
            models.UniqueConstraint(
                fields=('product', 'size'),
                deferrable=models.Deferrable.DEFERRED,
                name='products_productunit_product_size_uniq',
            ),
        ]
        ordering = ['qty_in_small']

    def __str__(self):
        return f"{self.product.display_name} — {self.name}"

    # ملحوظة: كان هنا clean() بيقارن الوحدة دي بـ"الوحدة الأخت" (الحجم التاني)
    # عن طريق قراءتها من قاعدة البيانات مباشرة. المشكلة إن ده بيبوظ بالظبط في
    # أكتر سيناريو شائع: لما تعدّل سعر وحدة موجودة وتضيف وحدة جديدة في نفس
    # مرة الحفظ (زي فورم "تعديل منتج" اللي فيه الوحدتين مع بعض). وقت ما
    # الوحدة الجديدة بتتفحص، الوحدة التانية لسه متسجّلاش في قاعدة البيانات
    # بالقيمة الجديدة (لسه بالقيمة القديمة)، فالمقارنة بتطلع غلط وترفض الحفظ
    # من غير أي سبب واضح للمستخدم — وده بالظبط اللي كان بيحصل.
    # نفس المقارنة (كبرى أغلى وأكبر من صغرى) دلوقتي بتتم على مستوى الـ
    # formset (BaseProductUnitFormSet في forms.py)، اللي بيشوف كل الوحدات
    # المُرسلة في نفس الطلب مع بعض بدل ما يرجع لقاعدة البيانات.

    def get_pricing_breakdown_for_account_type(self, account_type):
        """
        يرجع (سعر الجمهور، نسبة الخصم، سعر القطعة بعد الخصم) لنوع حساب معيّن.
        دي المصدر الوحيد لتفاصيل التسعير — بتتستخدم في السلة والطلب والفاتورة
        عشان الكل يعتمد على نفس الحساب بالظبط ومايختلفوش عن بعض.

        قاعدة الخصم: بيتحدد يدويًا على الوحدة الصغرى (قطعة) بس لو المنتج
        عنده وحدة صغرى. سعر الوحدة الكبرى (كرتونة) في الحالة دي بياخد **نفس
        نسبة الخصم** المحددة على القطعة، لكن مطبّقة على سعر جمهور الكرتونة
        نفسه (unit_price بتاعها) — مش عن طريق ضرب سعر القطعة بعد الخصم في
        qty_in_small، لأن سعر الكرتونة الأصلي غالبًا فيه خصم كمية مبني جواه
        أصلًا ومش بالضرورة يساوي سعر القطعة × العدد (مثلاً كرتونة فيها 50
        قطعة بسعر جمهور 480 مش 500). نقل النسبة بس هو اللي بيحافظ على تسعير
        الكرتونة الأصلي صحيح. لو المنتج مالوش وحدة صغرى أصلًا (كبرى بس)،
        الخصم بيتحدد عليها هي نفسها مباشرة زي أي وحدة عادية.
        """
        if not account_type:
            return self.unit_price, Decimal('0'), self.unit_price

        if self.size == self.Size.LARGE:
            sibling_small = next(
                (u for u in self.product.units.all() if u.size == self.Size.SMALL),
                None,
            )
            if sibling_small is not None:
                _, small_discount_percent, _ = sibling_small.get_pricing_breakdown_for_account_type(account_type)
                if not small_discount_percent:
                    return self.unit_price, Decimal('0'), self.unit_price
                derived_price = (
                    self.unit_price * (Decimal('1') - small_discount_percent / Decimal('100'))
                ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                return self.unit_price, small_discount_percent, derived_price

        discount = next(
            (d for d in self.discounts.all() if d.account_type_id == account_type.pk),
            None,
        )
        if not discount:
            return self.unit_price, Decimal('0'), self.unit_price
        return self.unit_price, discount.discount_percent, discount.price_after_discount

    def get_price_for_account_type(self, account_type):
        """
        سعر القطعة الفعلي (بعد الخصم) لنوع حساب معيّن: سعر الجمهور (unit_price)
        مطروح منه نسبة الخصم المحدّدة لهذا الصنف/الوحدة تحديدًا لهذا النوع
        (UnitDiscount)، أو سعر الجمهور كامل لو مفيش خصم متسجل لهذا الصنف.
        """
        _, _, final_price = self.get_pricing_breakdown_for_account_type(account_type)
        return final_price

    def get_pricing_breakdown_for_client(self, client):
        """نفس get_pricing_breakdown_for_account_type لكن بتاخد العميل مباشرة."""
        profile = getattr(client, 'client_profile', None)
        account_type = getattr(profile, 'account_type', None)
        return self.get_pricing_breakdown_for_account_type(account_type)

    def get_price_for_client(self, client):
        """
        السعر الفعلي للوحدة كاملة حسب نوع حساب العميل — بيرجع سعر الوحدة
        الواحدة (مش الإجمالي)، اضربه في الكمية للحصول على subtotal.
        العميل بدون profile (أو غير مسجل) بياخد سعر الجمهور (unit_price) كامل.
        """
        profile = getattr(client, 'client_profile', None)
        account_type = getattr(profile, 'account_type', None)
        return self.get_price_for_account_type(account_type)

    def get_price(self, qty, client=None):
        """
        إجمالي سعر الكمية المطلوبة (qty بوحدة هذا الـ ProductUnit نفسه —
        كرتونة أو قطعة، حسب الوحدة اللي العميل بيشتريها). بياخد خصم نوع
        حسابه لو منطبق على هذا الصنف، وإلا سعر الجمهور.
        """
        if client is not None:
            return self.get_price_for_client(client) * qty
        return self.unit_price * qty


class UnitDiscount(models.Model):
    """
    خصم صنف/وحدة معيّنة لنوع حساب معيّن — هو المصدر الوحيد للتسعير المخفّض:
    مفيش خصم عام على مستوى الحساب أو نوع الحساب، كل صنف له نسبة خصمه
    الخاصة (يحددها الأدمن من شاشة "أنواع الحسابات" في لوحة الموظفين).
    عدم وجود صف لصنف معيّن = بدون خصم (سعر الجمهور كامل) لهذا النوع.
    """
    unit = models.ForeignKey(
        ProductUnit,
        on_delete=models.CASCADE,
        related_name='discounts',
    )
    account_type = models.ForeignKey(
        'accounts.AccountType',
        on_delete=models.CASCADE,
        related_name='unit_discounts',
    )
    discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name='نسبة الخصم (%)',
        help_text='تُطرح من سعر الجمهور (unit_price) لهذا الصنف تحديدًا، لهذا النوع من الحسابات.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'خصم صنف لنوع حساب'
        verbose_name_plural = 'خصومات الأصناف لأنواع الحسابات'
        constraints = [
            models.UniqueConstraint(
                fields=('unit', 'account_type'),
                name='products_unitdiscount_unit_accounttype_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.unit} — {self.account_type} — {self.discount_percent}%'

    @property
    def price_after_discount(self):
        price = self.unit.unit_price * (Decimal('1') - self.discount_percent / Decimal('100'))
        return price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

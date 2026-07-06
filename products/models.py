from django.db import models
from django.core.validators import FileExtensionValidator


class Category(models.Model):
    name = models.CharField(max_length=255)
    image = models.ImageField(
        upload_to='categories/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp'])]
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
    name_ar = models.CharField(max_length=255)
    name_en = models.CharField(max_length=255, blank=True)
    manufacturer = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(
        upload_to='products/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp'])]
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'منتج'
        verbose_name_plural = 'المنتجات'
        ordering = ['name_ar']

    @property
    def display_name(self):
        return self.name_en or self.name_ar

    def __str__(self):
        return self.display_name

    def units_for_client(self, client):
        """
        الوحدة (أو الوحدات) المفروض تظهر للعميل ده في المتجر/السلة، حسب نوع حسابه:
        - قطاعي: أصغر وحدة متاحة (أو الوحدة الوحيدة لو المنتج بوحدة واحدة بس).
        - جملة: أكبر وحدة متاحة دايمًا.
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
        is_wholesale = bool(profile and profile.is_wholesale)
        return [units[-1]] if is_wholesale else [units[0]]


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

    def get_price_for_client(self, client):
        """
        السعر الفعلي للوحدة كاملة حسب نوع الحساب (جملة/قطاعي) — بيرجع سعر الوحدة
        الواحدة (مش الإجمالي)، اضربه في الكمية للحصول على subtotal.
        العميل بدون profile (أو غير مسجل) بياخد السعر الأساسي عادي.
        """
        from decimal import Decimal, ROUND_HALF_UP
        profile = getattr(client, 'client_profile', None)
        if not profile or not profile.is_wholesale:
            return self.unit_price
        discount = profile.effective_discount_percent
        price = self.unit_price * (Decimal('1') - discount / Decimal('100'))
        return price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def get_price(self, qty, client=None):
        """
        إجمالي سعر الكمية المطلوبة (qty بوحدة هذا الـ ProductUnit نفسه —
        كرتونة أو قطعة، حسب الوحدة اللي العميل بيشتريها). العميل الجملة بياخد
        خصمه لو منطبق، وإلا السعر الأساسي.
        """
        if client is not None:
            return self.get_price_for_client(client) * qty
        return self.unit_price * qty

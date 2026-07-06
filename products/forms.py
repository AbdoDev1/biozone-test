from django import forms
from django.forms import inlineformset_factory
from django.forms.models import BaseInlineFormSet
from .models import Product, ProductUnit, Category


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['category', 'name_ar', 'name_en', 'manufacturer', 'description', 'image', 'is_active']
        widgets = {
            'category': forms.Select(attrs={
                'class': 'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-400'
            }),
            'name_ar': forms.TextInput(attrs={
                'class': 'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-400',
                'placeholder': 'اسم المنتج بالعربي'
            }),
            'name_en': forms.TextInput(attrs={
                'class': 'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-400',
                'placeholder': 'Product name in English'
            }),
            'manufacturer': forms.TextInput(attrs={
                'class': 'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-400',
                'placeholder': 'الشركة المصنعة'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-400',
                'rows': 3,
                'placeholder': 'وصف المنتج (اختياري)'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'accent-blue-600'
            }),
        }
        labels = {
            'category': 'القسم',
            'name_ar': 'الاسم بالعربي',
            'name_en': 'الاسم بالإنجليزي',
            'manufacturer': 'الشركة المصنعة',
            'description': 'الوصف',
            'image': 'صورة المنتج',
            'is_active': 'نشط',
        }


class ProductUnitForm(forms.ModelForm):
    initial_stock = forms.IntegerField(
        min_value=0,
        initial=0,
        required=False,
        label='الكمية الابتدائية',
        widget=forms.NumberInput(attrs={
            'class': 'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-400',
            'placeholder': '0'
        })
    )

    class Meta:
        model = ProductUnit
        fields = ['size', 'name', 'qty_in_small', 'unit_price']
        widgets = {
            'size': forms.Select(attrs={
                'class': 'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-400'
            }),
            'name': forms.TextInput(attrs={
                'class': 'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-400',
                'placeholder': 'مثال: علبة، قطعة، كرتونة'
            }),
            'qty_in_small': forms.NumberInput(attrs={
                'class': 'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-400'
            }),
            'unit_price': forms.NumberInput(attrs={
                'class': 'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-400',
                'placeholder': 'اتركه فارغًا ليُحسب تلقائيًا من سعر الكرتونة'
            }),
        }
        labels = {
            'size': 'الحجم',
            'name': 'اسم الوحدة',
            'qty_in_small': 'الكمية في الوحدة الصغرى',
            'unit_price': 'سعر القطعة',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # مش required على مستوى الفورم عشان المتصفح ميرفضش إرسال الفورم لو
        # سعر القطعة سايبينه فاضي بقصد (هيتحسب تلقائي من سعر الكرتونة ÷
        # الكمية — شوف autofill_small_unit_price في products/pricing.py وكمان
        # BaseProductUnitFormSet.clean() تحت اللي بيرفض الحفظ برسالة واضحة لو
        # فضل السعر مجهول فعلًا (مفيش كرتونة نحسب منها).
        self.fields['unit_price'].required = False

    def validate_unique(self):
        # بنعطّل هنا التحقق التلقائي من unique_together (product, size) لأن
        # Django بيعمله بمقارنة instance الفورم ده بقاعدة البيانات مباشرة —
        # وده بالظبط اللي بيفشل في سيناريو "تعديل حجم وحدة موجودة (صغرى→كبرى)
        # + إضافة وحدة جديدة بنفس الحجم القديم (صغرى) في نفس مرة الحفظ":
        # وقت ما الوحدة الجديدة بتتفحص، الوحدة التانية لسه متسجّلاش في قاعدة
        # البيانات بالقيمة الجديدة (لسه بالقيمة القديمة "صغرى")، فبيرجع
        # تعارض وهمي ويطلب الحفظ على مرتين. البديل: BaseProductUnitFormSet
        # .clean() تحت بيتأكد من عدم تكرار نفس الحجم بين كل الوحدات المُرسلة
        # مع بعض (من غير رجوع لقاعدة البيانات) — بالظبط زي ما بيعمل مع مقارنة
        # السعر/الكمية بين الكبرى والصغرى.
        exclude = self._get_validation_exclusions()
        exclude.add('size')
        try:
            self.instance.validate_unique(exclude=exclude)
        except forms.ValidationError as e:
            self._update_errors(e)

    def validate_constraints(self):
        # نفس فكرة validate_unique() فوق بالضبط، بس هنا لـ Meta.constraints
        # (قيد الـ UniqueConstraint الجديد بتاع product+size). من ناحية
        # Django دول ميثودين منفصلين تمامًا يتم نداهم الاتنين من _post_clean():
        # validate_unique() بيغطي unique_together القديم، وvalidate_constraints()
        # بيغطي Meta.constraints — وكل واحد منهم بيعمل نفس نوع التحقق (رجوع
        # لقاعدة البيانات) لوحده بمعزل عن التاني. لازم نستبعد 'size' من الاتنين
        # مع بعض، وإلا هيفضل فيه false positive حتى بعد استبعادها من
        # validate_unique() لوحدها.
        exclude = self._get_validation_exclusions()
        exclude.add('size')
        try:
            self.instance.validate_constraints(exclude=exclude)
        except forms.ValidationError as e:
            self._update_errors(e)


class BaseProductUnitFormSet(BaseInlineFormSet):
    """
    بتتأكد إن الوحدة الكبرى (كرتونة) دايمًا أكبر عدد قطع وأغلى سعر من الوحدة
    الصغرى (قطعة) لنفس المنتج — عشان نمسك أخطاء إدخال زي تسجيل سعر الكرتونة
    = سعر القطعة بالغلط.

    الفرق عن الـ clean() القديمة اللي كانت على الموديل: هنا بنقارن كل
    الوحدات المُرسلة في نفس الطلب مع بعض (من self.forms مباشرة)، مش بنرجع
    لقاعدة البيانات. ده مهم لأن لو المستخدم بيعدّل سعر وحدة موجودة *و* بيضيف
    وحدة جديدة في نفس مرة الحفظ، قاعدة البيانات لسه فيها القيمة القديمة —
    فأي مقارنة بترجع لقاعدة البيانات هتقارن بقيمة قديمة غلط وترفض حفظ صحيح
    100% من غير ما يبان للمستخدم ليه.
    """

    def clean(self):
        super().clean()
        if any(self.errors):
            return

        # لو سعر أي وحدة (مش محذوفة) لسه فاضي في المرحلة دي، معناها
        # autofill_small_unit_price (في products/pricing.py) ملقتش وحدة
        # كبرى يحسب منها — يبقى لازم نطلب من المستخدم يدخل السعر يدويًا
        # برسالة واضحة، بدل ما يوصله خطأ "This field is required" الافتراضي.
        for form in self.forms:
            if not hasattr(form, 'cleaned_data') or not form.cleaned_data:
                continue
            if form.cleaned_data.get('DELETE'):
                continue
            if form.cleaned_data.get('unit_price') is None and form.cleaned_data.get('size'):
                form.add_error(
                    'unit_price',
                    'يجب إدخال سعر الوحدة يدويًا، أو تعبئة سعر وكمية الوحدة '
                    'الكبرى ليُحسب سعر القطعة تلقائيًا منها.'
                )

        if any(self.errors):
            return

        active = []  # (size, price, qty, form) لكل وحدة مش هتتحذف
        for form in self.forms:
            if not hasattr(form, 'cleaned_data'):
                continue
            data = form.cleaned_data
            if not data or data.get('DELETE'):
                continue
            size = data.get('size')
            price = data.get('unit_price')
            qty = data.get('qty_in_small')
            if size and price is not None and qty is not None:
                active.append((size, price, qty, form))

        # ملحوظة: التأكد من عدم تكرار نفس الحجم (صغرى+صغرى أو كبرى+كبرى) بين
        # الوحدات المُرسلة لسه بيحصل تلقائي — لكن دلوقتي عن طريق
        # BaseModelFormSet.validate_unique() الأساسي (اللي super().clean()
        # فوق بينده)، وهو أصلاً بيقارن الفورمات المُرسلة ببعض من غير رجوع
        # لقاعدة البيانات، فمش بيقع في نفس مشكلة instance.validate_unique()
        # اللي عطّلناها فوق في ProductUnitForm لحل المشكلة الأصلية.

        large = next((u for u in active if u[0] == ProductUnit.Size.LARGE), None)
        small = next((u for u in active if u[0] == ProductUnit.Size.SMALL), None)
        if not large or not small:
            return

        _, large_price, large_qty, large_form = large
        _, small_price, small_qty, small_form = small

        if large_qty <= small_qty:
            large_form.add_error(
                'qty_in_small',
                f'يجب أن يكون عدد القطع في الوحدة الكبرى ({large_qty}) أكبر من '
                f'عدد القطع في الوحدة الصغرى ({small_qty}).'
            )
        if large_price <= small_price:
            large_form.add_error(
                'unit_price',
                f'يجب أن يكون سعر الوحدة الكبرى ({large_price}) أكبر من سعر '
                f'الوحدة الصغرى ({small_price}). إذا كانت الكرتونة تحتوي على {large_qty} '
                f'قطعة، فالسعر المتوقع تقريبًا هو {small_price * large_qty} '
                f'(سعر القطعة × عدد القطع)، وليس سعر القطعة الواحدة.'
            )


# نفس آلية الـ inlines بتاعة Django admin — بتسمح بإضافة/تعديل/حذف أي عدد
# وحدات لنفس المنتج (قطعة + كرتونة مثلاً) من صفحة واحدة، بدل ما نضطر نروح
# للأدمن كل مرة عايزين نضيف وحدة تانية لصنف.
ProductUnitFormSet = inlineformset_factory(
    Product,
    ProductUnit,
    form=ProductUnitForm,
    formset=BaseProductUnitFormSet,
    fields=['size', 'name', 'qty_in_small', 'unit_price'],
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)

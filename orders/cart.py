from django.db.models import F
from products.models import ProductUnit
from .models import Cart as CartModel, CartItem


MAX_ITEM_QUANTITY = 10_000  # سقف منطقي لمنع كمية غير منطقية (مثلاً مليار قطعة) من العالق في السلة


class Cart:
    """
    غلاف (wrapper) حوالين السلة النشطة للعميل — بقت متخزنة في الداتابيز
    (orders.models.Cart/CartItem) مش في السيشن، عشان العميل يقدر يفتح أكتر
    من سلة (طلبية) في نفس الوقت ويرجع يكمل أي واحدة فيهم وقت ما يحب، بدل
    ما يبقى في سلة واحدة بس بتتفضى بمجرد إرسال الطلب.

    مهم: الكونستركتور (__init__) مبيعملش أي إنشاء في الداتابيز — بيقرا بس
    السلة النشطة الحالية لو موجودة. الإنشاء الفعلي (لو العميل مالوش أي سلة
    خالص) بيحصل جوه add()/set_quantity() بس، لحظة ما فعليًا بيضيف صنف —
    عشان صفحة السلة تقدر تعرض "مفيش طلبيات مفتوحة" بوضوح لو العميل مسحهم
    كلهم، بدل ما تلاقي سلة فاضية اتنشأت لوحدها من غير ما هو يطلب كده.

    الواجهة العامة (add/set_quantity/increase/decrease/remove/clear/
    get_items/get_total/__len__) فضلت زي ما هي عشان orders/views.py يفضل
    شغال من غير تعديل — الفرق كله مخفي جوه الكلاس ده.
    """

    def __init__(self, request):
        self.client = request.user if request.user.is_authenticated else None
        self._cart_obj = CartModel.get_active(self.client) if self.client else None

    @property
    def cart_obj(self):
        return self._cart_obj

    def _is_allowed_unit(self, unit):
        """
        بوابة الأمان الأولى: الوحدة اللي بتتضاف للسلة لازم تكون هي نفسها
        الوحدة المسموح بيها لنوع العميل ده (units_for_client) — بغض النظر عن
        أي unit_id جاي من فورم أو طلب HTTP يدوي.
        """
        allowed = unit.product.units_for_client(self.client)
        return any(u.pk == unit.pk for u in allowed)

    def _is_in_stock(self, unit):
        """
        بوابة الأمان التانية: الصنف لازم يكون متاح في المخزون (is_available)
        فعليًا وقت الإضافة — نفس الشرط اللي بيحدد ظهور "غير متوفر" في كارت
        المتجر. من غير الفحص ده، طلب POST مباشر لـ cart_add على صنف نفدت
        كميته (حتى لو زرار الإضافة مخفي/متعطل في الصفحة) كان بيضيفه للسلة
        عادي، وبيتكشف بس وقت الـ checkout (تجربة مستخدم سيئة ومربكة).
        """
        inv = getattr(unit.product, 'inventory', None)
        return bool(inv and inv.is_available)

    def add(self, unit_id, quantity=1):
        """يرجع True لو الصنف اتضاف فعلاً، False لو الوحدة غير مسموحة أو الصنف غير متوفر."""
        if self.client is None:
            return False
        try:
            unit = ProductUnit.objects.select_related("product", "product__inventory").get(pk=unit_id)
        except ProductUnit.DoesNotExist:
            return False
        if not self._is_allowed_unit(unit) or not self._is_in_stock(unit):
            return False

        # السلة بتتنشئ هنا بس — أول لحظة صنف فعلي بيتضاف بنجاح.
        if self._cart_obj is None:
            self._cart_obj = CartModel.get_or_create_active(self.client)

        item, _created = CartItem.objects.get_or_create(
            cart=self._cart_obj, product_unit=unit, defaults={"quantity": 0},
        )
        new_quantity = item.quantity + quantity
        item.quantity = max(1, min(new_quantity, MAX_ITEM_QUANTITY))
        item.save(update_fields=["quantity"])
        self._cart_obj.save(update_fields=["updated_at"])
        return True

    def set_quantity(self, unit_id, quantity):
        """يرجع True لو الكمية اتحدّثت فعلاً، False لو الوحدة غير مسموحة أو الصنف غير متوفر."""
        if self.client is None:
            return False

        if quantity <= 0:
            self.remove(unit_id)
            return True

        try:
            unit = ProductUnit.objects.select_related("product", "product__inventory").get(pk=unit_id)
        except ProductUnit.DoesNotExist:
            return False
        if not self._is_allowed_unit(unit) or not self._is_in_stock(unit):
            return False

        if self._cart_obj is None:
            self._cart_obj = CartModel.get_or_create_active(self.client)

        CartItem.objects.update_or_create(
            cart=self._cart_obj, product_unit=unit,
            defaults={"quantity": min(quantity, MAX_ITEM_QUANTITY)},
        )
        self._cart_obj.save(update_fields=["updated_at"])
        return True

    def get_quantity(self, unit_id):
        """كمية صنف معيّن في السلة النشطة الحالية، أو 0 لو مش موجود/مفيش سلة أصلًا."""
        if self._cart_obj is None:
            return 0
        item = CartItem.objects.filter(cart=self._cart_obj, product_unit_id=unit_id).first()
        return item.quantity if item else 0

    def increase(self, unit_id):
        if self._cart_obj is None:
            return
        updated = CartItem.objects.filter(cart=self._cart_obj, product_unit_id=unit_id).update(
            quantity=F("quantity") + 1,
        )
        if updated:
            self._cart_obj.save(update_fields=["updated_at"])

    def decrease(self, unit_id):
        if self._cart_obj is None:
            return
        try:
            item = CartItem.objects.get(cart=self._cart_obj, product_unit_id=unit_id)
        except CartItem.DoesNotExist:
            return
        item.quantity -= 1
        if item.quantity <= 0:
            item.delete()
        else:
            item.save(update_fields=["quantity"])
        self._cart_obj.save(update_fields=["updated_at"])

    def remove(self, unit_id):
        if self._cart_obj is None:
            return
        deleted, _ = CartItem.objects.filter(cart=self._cart_obj, product_unit_id=unit_id).delete()
        if deleted:
            self._cart_obj.save(update_fields=["updated_at"])

    def clear(self):
        if self._cart_obj is None:
            return
        self._cart_obj.items.all().delete()

    def __len__(self):
        if self._cart_obj is None:
            return 0
        return sum(item.quantity for item in self._cart_obj.items.all())

    def count_items(self):
        if self._cart_obj is None:
            return 0
        return self._cart_obj.items.count()

    def get_items(self):
        if self._cart_obj is None:
            return []

        items = []
        for cart_item in self._cart_obj.items.select_related("product_unit", "product_unit__product"):
            unit = cart_item.product_unit
            quantity = cart_item.quantity
            if quantity <= 0:
                continue

            # دفاع إضافي وقت القراءة كمان: لو حالة العميل اتغيّرت بعد ما
            # الصنف كان في السلة (مثلاً حسابه اتحوّل من قطاعي لجملة)، ما
            # نفضلش عالقين على وحدة مش مسموح بيها دلوقتي.
            if not self._is_allowed_unit(unit):
                continue

            if self.client:
                public_price, discount_percent, unit_price = unit.get_pricing_breakdown_for_client(self.client)
            else:
                public_price, discount_percent, unit_price = unit.unit_price, 0, unit.unit_price
            subtotal = unit_price * quantity

            items.append({
                "unit": unit,
                "quantity": quantity,
                "public_price": public_price,
                "discount_percent": discount_percent,
                "unit_price": unit_price,
                "subtotal": subtotal,
                # علم عام (مش مبني على نوع حساب معيّن) بيوضّح إن العميل بيشتري
                # بالوحدة الكبرى (كرتونة) — يُستخدم بس لعرض شارة توضيحية بالسلة.
                "is_large_unit": unit.size == ProductUnit.Size.LARGE,
            })

        return items

    def get_total(self):
        return sum(item["subtotal"] for item in self.get_items())

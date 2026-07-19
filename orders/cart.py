from products.models import ProductUnit


MAX_ITEM_QUANTITY = 10_000  # سقف منطقي لمنع كمية غير منطقية (مثلاً مليار قطعة) من العالق في السلة


class Cart:
    def __init__(self, request):
        self.session = request.session
        self.cart = self.session.setdefault("cart", {})
        # العميل الحالي — بيحدد السعر والوحدة المسموح بيها تلقائيًا (جملة=كرتونة
        # بس، قطاعي=قطعة بس)، مفيش اختيار وضع شراء يدوي خالص.
        self.client = request.user if request.user.is_authenticated else None

    def save(self):
        self.session.modified = True

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
        unit_id = str(unit_id)
        try:
            unit = ProductUnit.objects.select_related("product", "product__inventory").get(pk=unit_id)
        except ProductUnit.DoesNotExist:
            return False
        if not self._is_allowed_unit(unit) or not self._is_in_stock(unit):
            return False

        if unit_id not in self.cart:
            self.cart[unit_id] = {"quantity": 0}

        new_quantity = self.cart[unit_id]["quantity"] + quantity
        self.cart[unit_id]["quantity"] = max(1, min(new_quantity, MAX_ITEM_QUANTITY))
        self.save()
        return True

    def set_quantity(self, unit_id, quantity):
        """يرجع True لو الكمية اتحدّثت فعلاً، False لو الوحدة غير مسموحة أو الصنف غير متوفر."""
        unit_id = str(unit_id)

        if quantity <= 0:
            self.remove(unit_id)
            return True

        try:
            unit = ProductUnit.objects.select_related("product", "product__inventory").get(pk=unit_id)
        except ProductUnit.DoesNotExist:
            return False
        if not self._is_allowed_unit(unit) or not self._is_in_stock(unit):
            return False

        self.cart[unit_id] = {"quantity": min(quantity, MAX_ITEM_QUANTITY)}
        self.save()
        return True

    def increase(self, unit_id):
        unit_id = str(unit_id)

        if unit_id in self.cart:
            self.cart[unit_id]["quantity"] += 1
            self.save()

    def decrease(self, unit_id):
        unit_id = str(unit_id)

        if unit_id in self.cart:
            self.cart[unit_id]["quantity"] -= 1

            if self.cart[unit_id]["quantity"] <= 0:
                self.remove(unit_id)
            else:
                self.save()

    def remove(self, unit_id):
        unit_id = str(unit_id)

        if unit_id in self.cart:
            del self.cart[unit_id]
            self.save()

    def clear(self):
        self.cart = {}
        self.session["cart"] = {}
        self.save()

    def __len__(self):
        return sum(item["quantity"] for item in self.cart.values())

    def count_items(self):
        return len(self.cart)

    def get_items(self):
        unit_ids = self.cart.keys()

        units = (
            ProductUnit.objects
            .filter(pk__in=unit_ids)
            .select_related("product")
        )

        items = []

        for unit in units:
            uid = str(unit.pk)
            entry = self.cart[uid]
            quantity = entry.get("quantity", 0)
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

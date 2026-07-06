from products.models import ProductUnit


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
        بوابة الأمان الوحيدة: الوحدة اللي بتتضاف للسلة لازم تكون هي نفسها
        الوحدة المسموح بيها لنوع العميل ده (units_for_client) — بغض النظر عن
        أي unit_id جاي من فورم أو طلب HTTP يدوي.
        """
        allowed = unit.product.units_for_client(self.client)
        return any(u.pk == unit.pk for u in allowed)

    def add(self, unit_id, quantity=1):
        unit_id = str(unit_id)
        unit = ProductUnit.objects.select_related("product").get(pk=unit_id)
        if not self._is_allowed_unit(unit):
            return

        if unit_id not in self.cart:
            self.cart[unit_id] = {"quantity": 0}

        self.cart[unit_id]["quantity"] += quantity
        self.save()

    def set_quantity(self, unit_id, quantity):
        unit_id = str(unit_id)

        if quantity <= 0:
            self.remove(unit_id)
            return

        unit = ProductUnit.objects.select_related("product").get(pk=unit_id)
        if not self._is_allowed_unit(unit):
            return

        self.cart[unit_id] = {"quantity": quantity}
        self.save()

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

            unit_price = unit.get_price_for_client(self.client) if self.client else unit.unit_price
            subtotal = unit_price * quantity
            profile = getattr(self.client, 'client_profile', None)
            is_wholesale = bool(profile and profile.is_wholesale)

            items.append({
                "unit": unit,
                "quantity": quantity,
                "unit_price": unit_price,
                "subtotal": subtotal,
                "is_wholesale": is_wholesale,
            })

        return items

    def get_total(self):
        return sum(item["subtotal"] for item in self.get_items())

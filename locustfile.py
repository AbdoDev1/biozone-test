"""
اختبار ضغط لموقع Biozone باستخدام Locust.

التشغيل (بعد ما الموقع يشتغل محليًا عبر docker-compose على المنفذ 8080):
    pip install locust
    locust -f locustfile.py --host=http://localhost:8080

بعدها افتح المتصفح على http://localhost:8089 وحدد:
    - عدد المستخدمين (Number of users) — مثلاً ابدأ بـ 20 وزوّد تدريجيًا
    - معدل الزيادة (Spawn rate) — مثلاً 5 مستخدمين/ثانية

راقب: Requests/sec, Response time (p95), Failure rate.
لو الـ p95 بدأ ياخد أكتر من ثانية أو الأخطاء بدأت تظهر، يبقى وصلت لحد سعة
السيرفر بالمواصفات دي.
"""

import random
from locust import HttpUser, task, between


class GuestBrowsing(HttpUser):
    """زائر بيتصفح المتجر من غير تسجيل دخول — أكتر سيناريو هيحصل كتير."""
    weight = 3
    wait_time = between(1, 3)

    @task(3)
    def browse_home(self):
        self.client.get("/", name="/ (الرئيسية)")

    @task(2)
    def browse_store(self):
        self.client.get("/store/", name="/store/")

    @task(1)
    def view_product(self):
        # عدّل نطاق الـ IDs دي حسب عدد المنتجات الفعلي عندك في قاعدة الاختبار
        pk = random.randint(1, 20)
        self.client.get(f"/store/product/{pk}/", name="/store/product/[pk]/")

    @task(1)
    def view_login_page(self):
        self.client.get("/accounts/login/", name="/accounts/login/")


class LoggedInClient(HttpUser):
    """عميل مسجّل دخول بيتصفح ويضيف للسلة — سيناريو أتقل على قاعدة البيانات."""
    weight = 1
    wait_time = between(2, 5)

    def on_start(self):
        # عدّل بيانات الدخول دي لحساب عميل تجريبي حقيقي موجود في قاعدة اختبارك
        self.client.get("/accounts/login/")
        self.client.post("/accounts/login/", {
            "username": "test_client",
            "password": "test_password_123",
        })

    @task(2)
    def browse_store(self):
        self.client.get("/store/", name="/store/ (عميل)")

    @task(1)
    def view_cart(self):
        self.client.get("/cart/", name="/cart/")

    @task(1)
    def view_orders(self):
        self.client.get("/orders/", name="/orders/")

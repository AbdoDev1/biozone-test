from django.db import models


class ReportsAccess(models.Model):
    """
    موديل بدون جدول بيانات فعلي (default_permissions فاضية ومفيش أي Field
    غير id) — الهدف الوحيد منه إنه يوفر صلاحية Django حقيقية 'staff.view_reports'
    نربطها بقسم التقارير (staff/views/reports.py)، بنفس أسلوب باقي الأقسام في
    permissions.py (PERMISSION_SECTIONS) اللي كلها مبنية على صلاحيات موديلات حقيقية.
    """
    class Meta:
        managed = True
        default_permissions = ()
        permissions = [
            ('view_reports', 'عرض قسم التقارير والتحليلات'),
        ]

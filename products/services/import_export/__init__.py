"""
منطق استيراد/تصدير المنتجات من وإلى ملفات Excel.

كان ده ملف واحد (import_export.py، 425 سطر) فيه 3 مسؤوليات مختلفة —
اتقسم لباكدج بنفس الاسم فيه 3 ملفات حسب المرحلة:

1. parsing.py  — القراءة والتصنيف (بدون أي حفظ): read_import_workbook + classify_row
2. commit.py   — الحفظ الفعلي بعد موافقة الموظف: commit_import_batch
3. export.py   — بناء ملفات إكسل (تصدير الأصناف الحالية + قالب فارغ)
4. common.py   — ثوابت وتسمية أعمدة مشتركة بين المرحلتين

الملف ده بيعيد تصدير كل حاجة عشان أي كود موجود بيستورد بـ
`from products.services import import_export` أو
`products.services.import_export.<اسم الدالة>` يفضل شغّال زي ما هو
بالظبط من غير أي تعديل — التقسيم داخلي بس.
"""
from .commit import commit_import_batch, commit_product
from .common import (
    DISCOUNT_COL_PREFIX,
    FUZZY_MATCH_THRESHOLD,
    REQUIRED_IMPORT_HEADERS,
    discount_col_name,
    group_import_errors,
)
from .export import build_import_template_workbook, build_products_export_workbook
from .parsing import classify_row, group_unit_rows, parse_unit_row, read_import_workbook

__all__ = [
    'FUZZY_MATCH_THRESHOLD',
    'DISCOUNT_COL_PREFIX',
    'REQUIRED_IMPORT_HEADERS',
    'discount_col_name',
    'group_import_errors',
    'parse_unit_row',
    'group_unit_rows',
    'classify_row',
    'read_import_workbook',
    'commit_product',
    'commit_import_batch',
    'build_products_export_workbook',
    'build_import_template_workbook',
]

"""
شاشات المنتجات في لوحة تحكم الموظفين — كانت كلها في ملف واحد
(staff/views/products.py، ~800 سطر) خليط بين CRUD أساسي واستيراد/تصدير
إكسل (منطق معقد لوحده: تطبيع أسماء، مطابقة ضبابية، شاشة مراجعة على
مرحلتين). اتقسّمت لملفين حسب المسؤولية:

- crud.py: عرض/إضافة/تعديل/حذف منتج — الشاشات اليومية البسيطة.
- import_export.py: كل حاجة متعلقة برفع/تنزيل ملفات إكسل (استيراد بالجملة
  من ملف، تصدير الكل، تصدير مجموعة مختارة، تحميل القالب).

الملف ده بيعيد تصدير كل الدوال العامة من التنين، عشان أي كود بينادي
`products.product_list` أو `products.import_products` (زي staff/urls.py)
يفضل شغال من غير أي تعديل — التقسيم داخلي بس.
"""

from .crud import (
    STAFF_LIST_PAGE_SIZE,
    product_list,
    product_add,
    product_edit,
    product_delete,
)

from .import_export import (
    IMPORT_SESSION_KEY,
    IMPORT_MAX_FILE_SIZE_MB,
    IMPORT_MAX_ROWS,
    FUZZY_MATCH_THRESHOLD,
    DISCOUNT_COL_PREFIX,
    import_products,
    import_products_review,
    import_products_confirm,
    download_template,
    export_products,
    export_products_select,
    export_products_selected,
)

__all__ = [
    'STAFF_LIST_PAGE_SIZE',
    'product_list',
    'product_add',
    'product_edit',
    'product_delete',
    'IMPORT_SESSION_KEY',
    'IMPORT_MAX_FILE_SIZE_MB',
    'IMPORT_MAX_ROWS',
    'FUZZY_MATCH_THRESHOLD',
    'DISCOUNT_COL_PREFIX',
    'import_products',
    'import_products_review',
    'import_products_confirm',
    'download_template',
    'export_products',
    'export_products_select',
    'export_products_selected',
]

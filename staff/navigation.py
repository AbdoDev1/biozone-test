"""
تعريف مركزي لعناصر تنقل لوحة الموظف — مصدر واحد يستخدمه كل من السايدبار
(staff/base.html) وشبكة التطبيقات في الصفحة الرئيسية (staff/dashboard.html)
بدل ما كل واجهة تكرر نفس الروابط/الأيقونات/شروط الصلاحية بشكل منفصل.
التصفية الفعلية (حسب صلاحيات المستخدم) بتحصل في staff/context_processors.py.

كل عنصر:
    key: معرّف قصير (مش بيتعرض، بس مفيد للمراجعة)
    label: النص المعروض
    url_name: اسم الـ URL جوه namespace 'staff' (بيتعمله reverse في الـ context processor)
    icon_path: قيمة attribute "d" لأيقونة SVG (نفس أسلوب stat_card.html's icon_path)
    perm: صلاحية Django بصيغة "app_label.codename" أو None لو مفيش شرط صلاحية عادي
    admin_only: True لو العنصر مقصور على role == 'ADMIN' فقط (مش perm عادي)
    active_url_names: قائمة url_names اللي المفروض تعتبر العنصر ده "نشط" (highlighted) عندها
"""

NAV_ITEMS = [
    {
        'key': 'dashboard',
        'label': 'الرئيسية',
        'url_name': 'dashboard',
        'icon_path': 'M2.25 12l8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75M8.25 21h8.25',
        'perm': None,
        'admin_only': False,
        'active_url_names': ['dashboard'],
    },
    {
        'key': 'clients',
        'label': 'إدارة حسابات العملاء',
        'url_name': 'clients',
        'icon_path': 'M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z',
        'perm': 'accounts.view_clientprofile',
        'admin_only': False,
        'active_url_names': ['clients', 'client_detail', 'client_approve', 'client_reject', 'client_add_payment', 'client_add_adjustment'],
    },
    {
        'key': 'employees',
        'label': 'صلاحيات الموظفين',
        'url_name': 'employees',
        'icon_path': 'M20.25 14.15v4.25c0 1.094-.787 2.036-1.872 2.18-2.087.277-4.216.42-6.378.42s-4.291-.143-6.378-.42c-1.085-.144-1.872-1.086-1.872-2.18v-4.25m16.5 0a2.18 2.18 0 00.75-1.661V8.706c0-1.081-.768-2.015-1.837-2.175a48.114 48.114 0 00-3.413-.387m4.5 8.006c-.194.165-.42.295-.673.38A23.978 23.978 0 0112 15.75c-2.648 0-5.195-.429-7.577-1.22a2.016 2.016 0 01-.673-.38m0 0A2.18 2.18 0 013 12.489V8.706c0-1.081.768-2.015 1.837-2.175a48.111 48.111 0 013.413-.387m7.5 0V5.25A2.25 2.25 0 0013.5 3h-3a2.25 2.25 0 00-2.25 2.25v.894m7.5 0a48.667 48.667 0 00-7.5 0',
        'perm': None,
        'admin_only': True,
        'active_url_names': ['employees', 'employee_add', 'employee_edit'],
    },
    {
        'key': 'account_types',
        'label': 'أنواع الحسابات والخصومات',
        'url_name': 'account_types',
        'icon_path': 'M9.568 3H5.25A2.25 2.25 0 003 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 005.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 009.568 3z|M6 6h.008v.008H6V6z',
        'perm': None,
        'admin_only': True,
        'active_url_names': ['account_types', 'account_type_add', 'account_type_edit', 'account_type_discounts'],
    },
    {
        'key': 'inventory',
        'label': 'المخزون',
        'url_name': 'inventory',
        'icon_path': 'M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z',
        'perm': 'inventory.view_inventory',
        'admin_only': False,
        'active_url_names': ['inventory', 'inventory_detail', 'add_movement'],
    },
    {
        'key': 'orders',
        'label': 'الطلبات',
        'url_name': 'order_list',
        'icon_path': 'M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25zM6.75 12h.008v.008H6.75V12zm0 3h.008v.008H6.75V15zm0 3h.008v.008H6.75V18z',
        'perm': 'orders.view_order',
        'admin_only': False,
        'active_url_names': ['order_list', 'order_detail', 'order_print'],
    },
    {
        'key': 'products',
        'label': 'المنتجات',
        'url_name': 'product_list',
        'icon_path': 'M15.75 10.5V6a3.75 3.75 0 10-7.5 0v4.5m11.356-1.993l1.263 12c.07.665-.45 1.243-1.119 1.243H4.25a1.125 1.125 0 01-1.12-1.243l1.264-12A1.125 1.125 0 015.513 7.5h12.974c.576 0 1.059.435 1.119 1.007z',
        'perm': 'products.view_product',
        'admin_only': False,
        'active_url_names': ['product_list', 'product_add', 'product_edit', 'product_delete', 'import_products', 'import_products_review', 'import_products_errors', 'export_products_select'],
    },
    {
        'key': 'categories',
        'label': 'الأقسام',
        'url_name': 'category_list',
        'icon_path': 'M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z',
        'perm': 'products.view_category',
        'admin_only': False,
        'active_url_names': ['category_list', 'category_add', 'category_edit', 'category_delete'],
    },
    {
        'key': 'reports',
        'label': 'التقارير',
        'url_name': 'reports_dashboard',
        'icon_path': 'M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z',
        'perm': 'staff.view_reports',
        'admin_only': False,
        'active_url_names': ['reports_dashboard', 'reports_sales', 'reports_products', 'reports_customers', 'reports_profit', 'reports_stagnant'],
    },
    {
        'key': 'accounting',
        'label': 'الحسابات',
        'url_name': 'accounting_overview',
        'icon_path': 'M12 7.5h1.5m-1.5 3h1.5m-7.5 3h7.5m-7.5 3h7.5m3-9h3.375c.621 0 1.125.504 1.125 1.125V18a2.25 2.25 0 01-2.25 2.25M16.5 7.5V18a2.25 2.25 0 002.25 2.25M16.5 7.5V4.875c0-.621-.504-1.125-1.125-1.125H4.125C3.504 3.75 3 4.254 3 4.875V18a2.25 2.25 0 002.25 2.25h13.5M6 7.5h3v3H6v-3z',
        'perm': 'accounting.view_accounttransaction',
        'admin_only': False,
        'active_url_names': ['accounting_overview', 'accounting_quick_entry'],
    },
    {
        'key': 'tags',
        'label': 'الوسوم',
        'url_name': 'tag_list',
        'icon_path': 'M9.568 3H5.25A2.25 2.25 0 003 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 005.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 009.568 3z|M6 6h.008v.008H6V6z',
        'perm': 'tags.view_tag',
        'admin_only': False,
        'active_url_names': ['tag_list'],
    },
    {
        'key': 'activity',
        'label': 'سجل الأنشطة',
        'url_name': 'activity_list',
        'icon_path': 'M8.25 6.75h12M8.25 12h12m-12 5.25h12M3.75 6.75h.007v.008H3.75V6.75zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zM3.75 12h.007v.008H3.75V12zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm-.375 5.25h.007v.008H3.75v-.008zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z',
        'perm': 'activity.view_activitylog',
        'admin_only': False,
        'active_url_names': ['activity_list'],
    },
]

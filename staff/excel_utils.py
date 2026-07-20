"""
أدوات تصدير Excel المشتركة بين أقسام لوحة الموظف (المنتجات، الحسابات،
التقارير). كانت كل شاشة بتبني الـ HttpResponse بتاعها يدويًا بنفس الكود
بالظبط (نوع المحتوى، Content-Disposition، عرض الأعمدة) — اتلم هنا في
مكان واحد بدل ما يتكرر في كل ملف export على حدة.
"""
import io

import openpyxl
from django.http import HttpResponse

XLSX_CONTENT_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


def workbook_response(wb, filename):
    """
    بتحوّل Workbook جاهز (بعد ما تكون ضفت فيه كل الـ sheets والصفوف) لملف
    قابل للتحميل مباشرة كاستجابة HTTP. مفيش أي منطق أعمدة/صفوف هنا عمدًا —
    ده بيفضل مسؤولية كل شاشة على حدة لأن كل تقرير له أعمدته الخاصة.
    """
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type=XLSX_CONTENT_TYPE)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def build_simple_workbook(sheet_title, headers, rows, column_width=22):
    """
    اختصار للحالة الشائعة: شيت واحد بعنوان + صف رؤوس أعمدة + صفوف بيانات،
    وكل الأعمدة بنفس العرض. مناسب لمعظم تقارير قسم reports وتصدير الحسابات.
    لو التقرير محتاج تنسيق أكثر تعقيدًا (زي تصدير المنتجات اللي بيفرّق بين
    وحدة صغرى وكبرى)، يُفضّل بناء الـ Workbook يدويًا زي
    products._build_products_export_workbook بدل استخدام الاختصار ده.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_title
    ws.append(list(headers))
    for row in rows:
        ws.append(list(row))
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = column_width
    return wb

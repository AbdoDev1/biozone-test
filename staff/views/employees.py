from django import forms
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.shortcuts import render, redirect, get_object_or_404

from accounts.models import User
from staff.permissions import admin_required, grouped_permission_fields, permissions_queryset_from_codenames


_TEXT_INPUT_CLASS = 'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-400'
_CHECKBOX_CLASS = 'accent-blue-600'


class EmployeeForm(forms.ModelForm):
    """
    فورم بيانات الموظف الأساسية (بدون كلمة المرور — دي ليها فورم منفصل).
    الصلاحيات الدقيقة (عرض/إضافة/تعديل/حذف لكل قسم) بتتعرض وتتحفظ بشكل
    منفصل في الـ view عن طريق كتالوج staff.permissions — شوف grouped_permission_fields
    و permissions_queryset_from_codenames.
    """
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'role', 'is_active']
        widgets = {
            'username': forms.TextInput(attrs={'class': _TEXT_INPUT_CLASS}),
            'email': forms.EmailInput(attrs={'class': _TEXT_INPUT_CLASS}),
            'first_name': forms.TextInput(attrs={'class': _TEXT_INPUT_CLASS}),
            'last_name': forms.TextInput(attrs={'class': _TEXT_INPUT_CLASS}),
            'role': forms.Select(
                choices=[
                    (User.Role.ADMIN, 'مدير'),
                    (User.Role.WAREHOUSE, 'مخزن'),
                ],
                attrs={'class': _TEXT_INPUT_CLASS},
            ),
            'is_active': forms.CheckboxInput(attrs={'class': _CHECKBOX_CLASS}),
        }


class EmployeeCreateForm(EmployeeForm):
    password1 = forms.CharField(label='كلمة المرور', widget=forms.PasswordInput(attrs={'class': _TEXT_INPUT_CLASS}))
    password2 = forms.CharField(label='تأكيد كلمة المرور', widget=forms.PasswordInput(attrs={'class': _TEXT_INPUT_CLASS}))

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get('password1'), cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', 'كلمتا المرور غير متطابقتين.')
        return cleaned


@admin_required
def employee_list(request):
    employees = User.objects.filter(
        role__in=[User.Role.ADMIN, User.Role.WAREHOUSE]
    ).order_by('-date_joined')
    return render(request, 'staff/employees/list.html', {'employees': employees})


def _save_employee_permissions(request, employee):
    """بتحفظ الصلاحيات الدقيقة المختارة (من كتالوج staff.permissions) للموظف."""
    if employee.role == User.Role.ADMIN:
        # الأدمن Superuser تلقائيًا وعنده كل الصلاحيات دايمًا — مفيش داعي
        # نخزّن له صلاحيات فردية (ولو كان عنده صلاحيات قديمة من دور سابق، بنشيلها).
        employee.user_permissions.clear()
        return
    selected_codenames = request.POST.getlist('perm_codenames')
    employee.user_permissions.set(permissions_queryset_from_codenames(selected_codenames))


@admin_required
def employee_add(request):
    if request.method == 'POST':
        form = EmployeeCreateForm(request.POST)
        if form.is_valid():
            employee = form.save(commit=False)
            employee.password = make_password(form.cleaned_data['password1'])
            employee.status = User.Status.ACTIVE
            employee.save()
            _save_employee_permissions(request, employee)
            messages.success(request, f'تم إضافة الموظف {employee.username} بنجاح.')
            return redirect('staff:employees')
    else:
        form = EmployeeCreateForm(initial={'role': User.Role.WAREHOUSE, 'is_active': True})

    return render(request, 'staff/employees/form.html', {
        'form': form, 'is_new': True, 'permission_groups': grouped_permission_fields(),
    })


@admin_required
def employee_edit(request, pk):
    employee = get_object_or_404(User, pk=pk, role__in=[User.Role.ADMIN, User.Role.WAREHOUSE])

    if request.method == 'POST':
        form = EmployeeForm(request.POST, instance=employee)
        if form.is_valid():
            if employee.pk == request.user.pk and not form.cleaned_data['is_active']:
                messages.error(request, 'لا يمكنك إيقاف حسابك الخاص.')
            elif employee.pk == request.user.pk and form.cleaned_data['role'] != User.Role.ADMIN:
                messages.error(request, 'لا يمكنك تغيير دورك الخاص كمدير.')
            else:
                employee = form.save()
                _save_employee_permissions(request, employee)
                messages.success(request, f'تم تحديث بيانات وصلاحيات {employee.username}.')
                return redirect('staff:employees')
    else:
        form = EmployeeForm(instance=employee)

    return render(request, 'staff/employees/form.html', {
        'form': form, 'employee': employee, 'is_new': False,
        'permission_groups': grouped_permission_fields(employee),
    })


@admin_required
def employee_toggle_active(request, pk):
    employee = get_object_or_404(User, pk=pk, role__in=[User.Role.ADMIN, User.Role.WAREHOUSE])

    if employee.pk == request.user.pk:
        messages.error(request, 'لا يمكنك إيقاف حسابك الخاص.')
        return redirect('staff:employees')

    employee.is_active = not employee.is_active
    employee.save(update_fields=['is_active'])
    if employee.is_active:
        messages.success(request, f'تم تفعيل حساب {employee.username}.')
    else:
        messages.warning(request, f'تم إيقاف حساب {employee.username}.')

    return redirect('staff:employees')

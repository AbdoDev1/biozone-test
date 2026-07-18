from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, ClientProfile, AccountType


class RegisterForm(UserCreationForm):
    business_name = forms.CharField(max_length=255, label='اسم النشاط التجاري')
    account_type = forms.ModelChoiceField(
        queryset=AccountType.objects.filter(is_active=True),
        label='نوع الحساب',
        empty_label=None,
    )
    address = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), label='العنوان')
    phone = forms.CharField(max_length=20, label='رقم الهاتف')

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.CLIENT
        user.status = User.Status.PENDING
        if commit:
            user.save()
            ClientProfile.objects.create(
                user=user,
                business_name=self.cleaned_data['business_name'],
                account_type=self.cleaned_data['account_type'],
                address=self.cleaned_data['address'],
                phone=self.cleaned_data['phone'],
            )
        return user


class LoginForm(forms.Form):
    username = forms.CharField(label='اسم المستخدم')
    password = forms.CharField(widget=forms.PasswordInput, label='كلمة المرور')

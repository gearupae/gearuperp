"""
Settings app forms.
"""
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Role, CompanySettings


class UserForm(UserCreationForm):
    """Form for creating/editing users."""
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2', 'is_active']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make password fields optional for editing
        if self.instance and self.instance.pk:
            self.fields['password1'].required = False
            self.fields['password2'].required = False
            self.fields['password1'].help_text = 'Leave blank to keep current password'
        
        # Add Bootstrap classes
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
            if field_name == 'is_active':
                field.widget.attrs['class'] = 'form-check-input'
    
    def save(self, commit=True):
        user = super().save(commit=False)
        if self.instance.pk and not self.cleaned_data.get('password1'):
            # Don't update password if not provided
            user.password = User.objects.get(pk=self.instance.pk).password
        if commit:
            user.save()
        return user


class RoleForm(forms.ModelForm):
    """Form for creating/editing roles."""
    
    class Meta:
        model = Role
        fields = ['name', 'code', 'description', 'is_system_role', 'is_active']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name in ['is_system_role', 'is_active']:
                field.widget.attrs['class'] = 'form-check-input'
            else:
                field.widget.attrs['class'] = 'form-control'


class CompanySettingsForm(forms.ModelForm):
    """Form for company settings."""
    
    class Meta:
        model = CompanySettings
        fields = [
            'company_name', 'logo', 'address', 'phone', 'email',
            'tax_id', 'fiscal_year_start', 'currency', 'date_format', 'timezone'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name == 'logo':
                field.widget.attrs['class'] = 'form-control'
            elif field_name == 'address':
                field.widget.attrs['class'] = 'form-control'
                field.widget.attrs['rows'] = 3
            else:
                field.widget.attrs['class'] = 'form-control'



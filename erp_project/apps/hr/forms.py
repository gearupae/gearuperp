from django import forms
from django.db.models import Q, Sum, F, IntegerField
from django.db import models
from datetime import datetime, date
from .models import Department, Designation, Employee, LeaveType, LeaveRequest, Payroll
from apps.settings_app.models import Role


class MonthInput(forms.DateInput):
    """Custom widget for month input that converts YYYY-MM to first day of month."""
    input_type = 'month'
    
    def value_from_datadict(self, data, files, name):
        value = data.get(name)
        if value:
            # Convert YYYY-MM format to YYYY-MM-01 (first day of month)
            try:
                # Parse the month value (YYYY-MM)
                if isinstance(value, str) and len(value) == 7 and value.count('-') == 1:
                    year, month = value.split('-')
                    # Validate year and month
                    year_int = int(year)
                    month_int = int(month)
                    if 1 <= month_int <= 12:
                        # Return first day of the month in YYYY-MM-DD format
                        return f"{year}-{month:0>2}-01"
            except (ValueError, AttributeError, TypeError):
                pass
        return value
    
    def format_value(self, value):
        """Format date value to YYYY-MM for month input."""
        if value:
            if isinstance(value, str):
                # If already in YYYY-MM-DD format, extract YYYY-MM
                if len(value) >= 7:
                    return value[:7]
            elif hasattr(value, 'strftime'):
                # If it's a date object, format as YYYY-MM
                return value.strftime('%Y-%m')
        return value

class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'code', 'manager']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-select' if name == 'manager' else 'form-control'

class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ['first_name', 'last_name', 'email', 'phone', 'gender', 'department', 'designation', 'date_of_birth', 'date_of_joining', 'probation_period_days', 'status', 'basic_salary', 'emirates_id', 'visa_number', 'visa_expiry']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'date_of_joining': forms.DateInput(attrs={'type': 'date'}),
            'visa_expiry': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter to only show active departments
        department_queryset = Department.objects.filter(is_active=True)
        
        # If editing, include the current department even if inactive
        if self.instance and self.instance.pk:
            if self.instance.department_id:
                department_queryset = Department.objects.filter(
                    Q(is_active=True) | Q(pk=self.instance.department_id)
                )
        
        self.fields['department'].queryset = department_queryset.order_by('name')
        self.fields['department'].empty_label = '-- Select Department --'
        
        # Sync Roles from settings_app to Designations
        # Fetch all active roles and create corresponding designations if they don't exist
        roles = Role.objects.filter(is_active=True).order_by('name')
        for role in roles:
            # Create designation if it doesn't exist (using a default department or None)
            # We'll use the first active department or create without department
            default_dept = Department.objects.filter(is_active=True).first()
            if default_dept:
                Designation.objects.get_or_create(
                    name=role.name,
                    defaults={'department': default_dept}
                )
        
        # Now fetch designations (which should include synced roles)
        designation_queryset = Designation.objects.filter(is_active=True)
        
        # If editing, include the current designation even if inactive
        if self.instance and self.instance.pk:
            if self.instance.designation_id:
                designation_queryset = Designation.objects.filter(
                    Q(is_active=True) | Q(pk=self.instance.designation_id)
                )
        
        self.fields['designation'].queryset = designation_queryset.order_by('name')
        self.fields['designation'].empty_label = '-- Select Designation --'
        
        for name, field in self.fields.items():
            if name in ['department', 'designation', 'status', 'gender']:
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'

class LeaveRequestForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ['employee', 'leave_type', 'start_date', 'end_date', 'reason']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'reason': forms.Textarea(attrs={'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.is_admin = kwargs.pop('is_admin', False)
        super().__init__(*args, **kwargs)
        
        # Get employee (either from instance or from user)
        employee = None
        if self.instance and self.instance.pk:
            employee = self.instance.employee
        elif self.user and not self.is_admin:
            try:
                employee = Employee.objects.get(user=self.user, is_active=True)
            except Employee.DoesNotExist:
                pass
        
        # Filter leave types based on employee status
        leave_type_queryset = LeaveType.objects.filter(is_active=True)
        
        if employee:
            # Filter by probation status
            if employee.is_in_probation:
                # Show only probation-specific leave types
                leave_type_queryset = leave_type_queryset.filter(is_probation_only=True)
            else:
                # Hide probation-only leave types
                leave_type_queryset = leave_type_queryset.exclude(is_probation_only=True)
            
            # Filter by gender for gender-specific leaves
            if employee.gender:
                # Show gender-specific leaves matching employee gender
                gender_specific = leave_type_queryset.filter(
                    Q(is_gender_specific=False) | Q(gender_required=employee.gender)
                )
                leave_type_queryset = gender_specific
            else:
                # If gender not set, exclude gender-specific leaves
                leave_type_queryset = leave_type_queryset.exclude(is_gender_specific=True)
        
        self.fields['leave_type'].queryset = leave_type_queryset.order_by('name')
        self.fields['leave_type'].empty_label = '-- Select Leave Type --'
        
        # Filter employees to active only
        self.fields['employee'].queryset = Employee.objects.filter(is_active=True).order_by('first_name', 'last_name')
        self.fields['employee'].empty_label = '-- Select Employee --'
        
        # If user is not admin, auto-select their employee profile
        if self.user and not self.is_admin:
            try:
                employee = Employee.objects.get(user=self.user, is_active=True)
                self.fields['employee'].initial = employee.pk
                # Use hidden field for employee when auto-selected
                self.fields['employee'].widget = forms.HiddenInput()
            except Employee.DoesNotExist:
                pass
        
        for name, field in self.fields.items():
            if name in ['employee', 'leave_type']:
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        leave_type = cleaned_data.get('leave_type')
        employee = cleaned_data.get('employee')
        
        if start_date and end_date:
            if end_date < start_date:
                raise forms.ValidationError('End date must be after start date.')
            
            # Calculate leave days
            leave_days = (end_date - start_date).days + 1
            
            # Validate against leave type limits
            if leave_type and employee and leave_type.days_allowed > 0:
                # Check if employee has already taken leave of this type
                current_year_start = date(start_date.year, 1, 1)
                current_year_end = date(start_date.year, 12, 31)
                
                # Calculate existing leave days
                existing_leaves = LeaveRequest.objects.filter(
                    employee=employee,
                    leave_type=leave_type,
                    status='approved',
                    start_date__gte=current_year_start,
                    start_date__lte=current_year_end
                ).exclude(pk=self.instance.pk if self.instance.pk else None)
                
                existing_leave_days = sum(
                    (leave.end_date - leave.start_date).days + 1 
                    for leave in existing_leaves
                )
                
                total_leave_days = existing_leave_days + leave_days
                
                if total_leave_days > leave_type.days_allowed:
                    remaining_days = leave_type.days_allowed - existing_leave_days
                    raise forms.ValidationError(
                        f'Leave days exceed allowed limit. '
                        f'Allowed: {leave_type.days_allowed} days per year. '
                        f'Already taken: {existing_leave_days} days. '
                        f'Remaining: {remaining_days} days.'
                    )
        
        return cleaned_data

class PayrollForm(forms.ModelForm):
    class Meta:
        model = Payroll
        fields = ['employee', 'month', 'basic_salary', 'allowances', 'deductions', 'status']
        widgets = {
            'month': MonthInput(attrs={'type': 'month'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter to only show active employees
        self.fields['employee'].queryset = Employee.objects.filter(is_active=True).order_by('first_name', 'last_name')
        self.fields['employee'].empty_label = '-- Select Employee --'
        
        for name, field in self.fields.items():
            if name in ['employee', 'status']:
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'
    
    def clean_month(self):
        """Ensure month is converted to first day of month if needed."""
        month_value = self.cleaned_data.get('month')
        if not month_value:
            return month_value
        
        # If it's a string in YYYY-MM format (from widget), convert to date
        if isinstance(month_value, str):
            if len(month_value) == 7 and month_value.count('-') == 1:
                try:
                    year, month = month_value.split('-')
                    return datetime(int(year), int(month), 1).date()
                except (ValueError, AttributeError):
                    raise forms.ValidationError('Please enter a valid month.')
            # If it's already in YYYY-MM-DD format, parse it
            elif len(month_value) == 10:
                try:
                    date_obj = datetime.strptime(month_value, '%Y-%m-%d').date()
                    # Ensure it's the first day of the month
                    return datetime(date_obj.year, date_obj.month, 1).date()
                except (ValueError, AttributeError):
                    pass
        
        # If it's already a date object, ensure it's the first day of the month
        if hasattr(month_value, 'day'):
            if month_value.day != 1:
                return datetime(month_value.year, month_value.month, 1).date()
        
        return month_value
    
    def clean(self):
        cleaned_data = super().clean()
        # Auto-calculate net salary
        basic_salary = cleaned_data.get('basic_salary') or 0
        allowances = cleaned_data.get('allowances') or 0
        deductions = cleaned_data.get('deductions') or 0
        cleaned_data['net_salary'] = basic_salary + allowances - deductions
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        # Calculate net salary
        instance.net_salary = instance.basic_salary + instance.allowances - instance.deductions
        if commit:
            instance.save()
        return instance


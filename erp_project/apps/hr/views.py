"""HR Views"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DetailView
from django.urls import reverse_lazy
from django.db.models import Q, Sum
from django.core.exceptions import ValidationError
from datetime import date
from .models import Department, Designation, Employee, LeaveType, LeaveRequest, Payroll
from .forms import DepartmentForm, EmployeeForm, LeaveRequestForm, PayrollForm
from apps.core.mixins import PermissionRequiredMixin, CreatePermissionMixin, UpdatePermissionMixin
from apps.core.utils import PermissionChecker


class EmployeeListView(PermissionRequiredMixin, ListView):
    model = Employee
    template_name = 'hr/employee_list.html'
    context_object_name = 'employees'
    module_name = 'hr'
    permission_type = 'view'
    
    def get_queryset(self):
        queryset = Employee.objects.filter(is_active=True).select_related('department', 'designation')
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(Q(first_name__icontains=search) | Q(last_name__icontains=search) | Q(employee_code__icontains=search))
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Employees'
        context['can_create'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'hr', 'create')
        context['can_edit'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'hr', 'edit')
        
        # Calculate metrics
        all_employees = Employee.objects.filter(is_active=True)
        context['total_employees'] = all_employees.count()
        context['active_employees'] = all_employees.filter(status='active').count()
        context['total_departments'] = Department.objects.filter(is_active=True).count()
        
        return context


class EmployeeCreateView(CreatePermissionMixin, CreateView):
    model = Employee
    form_class = EmployeeForm
    template_name = 'hr/employee_form.html'
    success_url = reverse_lazy('hr:employee_list')
    module_name = 'hr'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Add Employee'
        # Pass departments and roles directly to template for manual rendering
        from .models import Department, Designation
        from apps.settings_app.models import Role
        
        context['departments'] = Department.objects.filter(is_active=True).order_by('name')
        
        # Fetch Roles from settings_app and sync to Designations
        roles = Role.objects.filter(is_active=True).order_by('name')
        # Sync roles to designations (create if they don't exist)
        default_dept = Department.objects.filter(is_active=True).first()
        for role in roles:
            if default_dept:
                Designation.objects.get_or_create(
                    name=role.name,
                    defaults={'department': default_dept}
                )
        
        # Now fetch designations (which includes synced roles)
        context['designations'] = Designation.objects.filter(is_active=True).order_by('name')
        # Also pass roles for reference
        context['roles'] = roles
        return context


class EmployeeUpdateView(UpdatePermissionMixin, UpdateView):
    model = Employee
    form_class = EmployeeForm
    template_name = 'hr/employee_form.html'
    success_url = reverse_lazy('hr:employee_list')
    module_name = 'hr'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Edit Employee: {self.object.full_name}'
        # Pass departments and roles directly to template for manual rendering
        from .models import Department, Designation
        from apps.settings_app.models import Role
        
        # Include current department even if inactive
        departments = Department.objects.filter(is_active=True)
        if self.object.department_id:
            departments = Department.objects.filter(
                Q(is_active=True) | Q(pk=self.object.department_id)
            )
        context['departments'] = departments.order_by('name')
        
        # Fetch Roles from settings_app and sync to Designations
        roles = Role.objects.filter(is_active=True).order_by('name')
        # Sync roles to designations (create if they don't exist)
        default_dept = Department.objects.filter(is_active=True).first()
        for role in roles:
            if default_dept:
                Designation.objects.get_or_create(
                    name=role.name,
                    defaults={'department': default_dept}
                )
        
        # Now fetch designations (which includes synced roles)
        # Include current designation even if inactive
        designations = Designation.objects.filter(is_active=True)
        if self.object.designation_id:
            designations = Designation.objects.filter(
                Q(is_active=True) | Q(pk=self.object.designation_id)
            )
        context['designations'] = designations.order_by('name')
        # Also pass roles for reference
        context['roles'] = roles
        return context


class EmployeeDetailView(PermissionRequiredMixin, DetailView):
    model = Employee
    template_name = 'hr/employee_detail.html'
    context_object_name = 'employee'
    module_name = 'hr'
    permission_type = 'view'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Employee: {self.object.full_name}'
        context['leave_requests'] = self.object.leave_requests.all()[:10]
        context['payrolls'] = self.object.payrolls.all()[:12]
        return context


class DepartmentListView(PermissionRequiredMixin, ListView):
    model = Department
    template_name = 'hr/department_list.html'
    context_object_name = 'departments'
    module_name = 'hr'
    permission_type = 'view'
    
    def get_queryset(self):
        return Department.objects.filter(is_active=True)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Departments'
        context['form'] = DepartmentForm()
        context['can_create'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'hr', 'create')
        return context
    
    def post(self, request, *args, **kwargs):
        form = DepartmentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Department created.')
        return redirect('hr:department_list')


class LeaveRequestListView(PermissionRequiredMixin, ListView):
    model = LeaveRequest
    template_name = 'hr/leave_list.html'
    context_object_name = 'leave_requests'
    module_name = 'hr'
    permission_type = 'view'
    
    def get_queryset(self):
        queryset = LeaveRequest.objects.filter(is_active=True).select_related('employee', 'leave_type')
        # If not admin, show only their own leave requests
        if not (self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'hr', 'view')):
            try:
                employee = Employee.objects.get(user=self.request.user, is_active=True)
                queryset = queryset.filter(employee=employee)
            except Employee.DoesNotExist:
                queryset = queryset.none()
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Leave Requests'
        context['can_approve'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'hr', 'approve')
        context['can_create'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'hr', 'create')
        context['can_edit'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'hr', 'edit')
        # Check if user has employee profile (for self-application)
        try:
            context['has_employee_profile'] = Employee.objects.filter(user=self.request.user, is_active=True).exists()
        except:
            context['has_employee_profile'] = False
        
        # Calculate metrics
        all_leave_requests = LeaveRequest.objects.filter(is_active=True)
        context['total_leave_requests'] = all_leave_requests.count()
        context['pending_leave_requests'] = all_leave_requests.filter(status='pending').count()
        context['approved_leave_requests'] = all_leave_requests.filter(status='approved').count()
        
        return context


class LeaveRequestCreateView(CreatePermissionMixin, CreateView):
    model = LeaveRequest
    form_class = LeaveRequestForm
    template_name = 'hr/leave_form.html'
    success_url = reverse_lazy('hr:leave_list')
    module_name = 'hr'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        kwargs['is_admin'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'hr', 'create')
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        is_admin = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'hr', 'create')
        context['title'] = 'Apply for Leave' if not is_admin else 'Add Leave Request'
        context['is_admin'] = is_admin
        # Get employee name if self-applying
        if not is_admin:
            try:
                employee = Employee.objects.get(user=self.request.user, is_active=True)
                context['employee_name'] = employee.full_name
            except Employee.DoesNotExist:
                pass
        return context
    
    def form_valid(self, form):
        # If not admin, ensure employee is set to current user's employee profile
        is_admin = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'hr', 'create')
        if not is_admin:
            try:
                employee = Employee.objects.get(user=self.request.user, is_active=True)
                form.instance.employee = employee
            except Employee.DoesNotExist:
                messages.error(self.request, 'Employee profile not found. Please contact HR.')
                return self.form_invalid(form)
        
        messages.success(self.request, 'Leave request submitted successfully.')
        return super().form_valid(form)


class LeaveRequestUpdateView(UpdatePermissionMixin, UpdateView):
    model = LeaveRequest
    form_class = LeaveRequestForm
    template_name = 'hr/leave_form.html'
    success_url = reverse_lazy('hr:leave_list')
    module_name = 'hr'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        kwargs['is_admin'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'hr', 'edit')
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        is_admin = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'hr', 'edit')
        context['title'] = 'Edit Leave Request'
        context['is_admin'] = is_admin
        return context
    
    def form_valid(self, form):
        messages.success(self.request, 'Leave request updated successfully.')
        return super().form_valid(form)


@login_required
def leave_approve(request, pk):
    leave = get_object_or_404(LeaveRequest, pk=pk)
    if request.user.is_superuser or PermissionChecker.has_permission(request.user, 'hr', 'approve'):
        leave.status = 'approved'
        leave.save()
        messages.success(request, 'Leave request approved.')
    return redirect('hr:leave_list')


@login_required
def leave_reject(request, pk):
    leave = get_object_or_404(LeaveRequest, pk=pk)
    if request.user.is_superuser or PermissionChecker.has_permission(request.user, 'hr', 'approve'):
        leave.status = 'rejected'
        leave.save()
        messages.success(request, 'Leave request rejected.')
    return redirect('hr:leave_list')


class PayrollListView(PermissionRequiredMixin, ListView):
    model = Payroll
    template_name = 'hr/payroll_list.html'
    context_object_name = 'payrolls'
    module_name = 'hr'
    permission_type = 'view'
    
    def get_queryset(self):
        return Payroll.objects.filter(is_active=True).select_related('employee')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Payroll'
        queryset = self.get_queryset()
        context['total_payroll'] = queryset.aggregate(Sum('net_salary'))['net_salary__sum'] or 0
        context['can_create'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'hr', 'create')
        context['can_edit'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'hr', 'edit')
        
        # Calculate metrics
        all_payrolls = Payroll.objects.filter(is_active=True)
        context['total_payroll_records'] = all_payrolls.count()
        context['paid_payrolls'] = all_payrolls.filter(status='paid').count()
        context['processed_payrolls'] = all_payrolls.filter(status='processed').count()
        
        return context


class PayrollDetailView(PermissionRequiredMixin, DetailView):
    model = Payroll
    template_name = 'hr/payroll_detail.html'
    context_object_name = 'payroll'
    module_name = 'hr'
    permission_type = 'view'
    
    def get_queryset(self):
        return Payroll.objects.filter(is_active=True).select_related(
            'employee', 'journal_entry', 'payment_journal_entry', 'paid_from_bank'
        )
    
    def get_context_data(self, **kwargs):
        from apps.core.audit import get_entity_audit_history
        
        context = super().get_context_data(**kwargs)
        context['title'] = f'Payroll - {self.object.employee.full_name}'
        context['can_edit'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'hr', 'edit')
        
        # Audit History
        context['audit_history'] = get_entity_audit_history('Payroll', self.object.pk)
        
        return context


class PayrollCreateView(CreatePermissionMixin, CreateView):
    model = Payroll
    form_class = PayrollForm
    template_name = 'hr/payroll_form.html'
    success_url = reverse_lazy('hr:payroll_list')
    module_name = 'hr'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Add Payroll'
        return context
    
    def form_valid(self, form):
        messages.success(self.request, f'Payroll for {form.instance.employee.full_name} created successfully.')
        return super().form_valid(form)


class PayrollUpdateView(UpdatePermissionMixin, UpdateView):
    model = Payroll
    form_class = PayrollForm
    template_name = 'hr/payroll_form.html'
    success_url = reverse_lazy('hr:payroll_list')
    module_name = 'hr'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Edit Payroll: {self.object.employee.full_name}'
        return context
    
    def form_valid(self, form):
        messages.success(self.request, f'Payroll for {form.instance.employee.full_name} updated successfully.')
        return super().form_valid(form)



# ============ PAYROLL ACCOUNTING VIEWS ============

@login_required
def payroll_process(request, pk):
    """
    Process payroll and post to accounting.
    SAP/Oracle Standard: Dr Salary Expense, Cr Salary Payable
    """
    from apps.core.audit import audit_payroll_process
    
    payroll = get_object_or_404(Payroll, pk=pk)
    
    if not (request.user.is_superuser or PermissionChecker.has_permission(request.user, 'hr', 'edit')):
        messages.error(request, 'Permission denied.')
        return redirect('hr:payroll_list')
    
    if payroll.status != 'draft':
        messages.error(request, 'Only draft payrolls can be processed.')
        return redirect('hr:payroll_list')
    
    try:
        journal = payroll.post_to_accounting(user=request.user)
        # Audit log with IP address
        audit_payroll_process(payroll, request.user, request=request)
        messages.success(request, f'Payroll for {payroll.employee.full_name} processed and posted. Journal: {journal.entry_number}')
    except ValidationError as e:
        messages.error(request, str(e))
    except Exception as e:
        messages.error(request, f'Error processing payroll: {e}')
    
    return redirect('hr:payroll_list')


@login_required
def payroll_pay(request, pk):
    """
    Pay processed payroll.
    SAP/Oracle Standard: Dr Salary Payable, Cr Bank
    """
    from apps.finance.models import BankAccount
    from datetime import date
    
    payroll = get_object_or_404(Payroll, pk=pk)
    
    if not (request.user.is_superuser or PermissionChecker.has_permission(request.user, 'hr', 'edit')):
        messages.error(request, 'Permission denied.')
        return redirect('hr:payroll_list')
    
    if payroll.status != 'processed':
        messages.error(request, 'Only processed payrolls can be paid.')
        return redirect('hr:payroll_list')
    
    if request.method == 'POST':
        bank_account_id = request.POST.get('bank_account')
        payment_date = request.POST.get('payment_date')
        reference = request.POST.get('reference', '')
        
        bank_account = BankAccount.objects.filter(pk=bank_account_id, is_active=True).first()
        if not bank_account:
            messages.error(request, 'Invalid bank account.')
            return redirect('hr:payroll_list')
        
        from datetime import datetime
        try:
            if payment_date:
                payment_date = datetime.strptime(payment_date, '%Y-%m-%d').date()
            else:
                payment_date = date.today()
        except ValueError:
            payment_date = date.today()
        
        try:
            journal = payroll.post_payment_journal(
                bank_account=bank_account,
                payment_date=payment_date,
                reference=reference,
                user=request.user
            )
            messages.success(request, f'Payroll payment for {payroll.employee.full_name} processed. Journal: {journal.entry_number}')
        except ValidationError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f'Error processing payment: {e}')
        
        return redirect('hr:payroll_list')
    
    # GET - Show payment form
    bank_accounts = BankAccount.objects.filter(is_active=True)
    context = {
        'title': f'Pay Salary - {payroll.employee.full_name}',
        'payroll': payroll,
        'bank_accounts': bank_accounts,
        'today': date.today().strftime('%Y-%m-%d'),
    }
    return render(request, 'hr/payroll_pay.html', context)

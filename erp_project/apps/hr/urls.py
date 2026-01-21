from django.urls import path
from . import views

app_name = 'hr'

urlpatterns = [
    path('employees/', views.EmployeeListView.as_view(), name='employee_list'),
    path('employees/create/', views.EmployeeCreateView.as_view(), name='employee_create'),
    path('employees/<int:pk>/', views.EmployeeDetailView.as_view(), name='employee_detail'),
    path('employees/<int:pk>/edit/', views.EmployeeUpdateView.as_view(), name='employee_edit'),
    path('departments/', views.DepartmentListView.as_view(), name='department_list'),
    path('leave/', views.LeaveRequestListView.as_view(), name='leave_list'),
    path('leave/create/', views.LeaveRequestCreateView.as_view(), name='leave_create'),
    path('leave/<int:pk>/edit/', views.LeaveRequestUpdateView.as_view(), name='leave_edit'),
    path('leave/<int:pk>/approve/', views.leave_approve, name='leave_approve'),
    path('leave/<int:pk>/reject/', views.leave_reject, name='leave_reject'),
    path('payroll/', views.PayrollListView.as_view(), name='payroll_list'),
    path('payroll/create/', views.PayrollCreateView.as_view(), name='payroll_create'),
    path('payroll/<int:pk>/', views.PayrollDetailView.as_view(), name='payroll_detail'),
    path('payroll/<int:pk>/edit/', views.PayrollUpdateView.as_view(), name='payroll_edit'),
    path('payroll/<int:pk>/process/', views.payroll_process, name='payroll_process'),
    path('payroll/<int:pk>/pay/', views.payroll_pay, name='payroll_pay'),
]


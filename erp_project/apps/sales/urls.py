"""
Sales URL configuration.
"""
from django.urls import path
from . import views

app_name = 'sales'

urlpatterns = [
    # Quotations
    path('quotations/', views.QuotationListView.as_view(), name='quotation_list'),
    path('quotations/create/', views.QuotationCreateView.as_view(), name='quotation_create'),
    path('quotations/<int:pk>/', views.QuotationDetailView.as_view(), name='quotation_detail'),
    path('quotations/<int:pk>/edit/', views.QuotationUpdateView.as_view(), name='quotation_edit'),
    path('quotations/<int:pk>/delete/', views.quotation_delete, name='quotation_delete'),
    path('quotations/<int:pk>/convert/', views.quotation_convert_to_invoice, name='quotation_convert'),
    path('quotations/<int:pk>/status/<str:status>/', views.quotation_update_status, name='quotation_status'),
    path('quotations/<int:pk>/pdf/', views.quotation_pdf, name='quotation_pdf'),
    
    # Invoices
    path('invoices/', views.InvoiceListView.as_view(), name='invoice_list'),
    path('invoices/create/', views.InvoiceCreateView.as_view(), name='invoice_create'),
    path('invoices/<int:pk>/', views.InvoiceDetailView.as_view(), name='invoice_detail'),
    path('invoices/<int:pk>/edit/', views.InvoiceUpdateView.as_view(), name='invoice_edit'),
    path('invoices/<int:pk>/delete/', views.invoice_delete, name='invoice_delete'),
    path('invoices/<int:pk>/post/', views.invoice_post, name='invoice_post'),
    path('invoices/<int:pk>/status/<str:status>/', views.invoice_update_status, name='invoice_status'),
    path('invoices/<int:pk>/pdf/', views.invoice_pdf, name='invoice_pdf'),
    path('invoices/<int:pk>/receive-payment/', views.invoice_receive_payment, name='invoice_receive_payment'),
]


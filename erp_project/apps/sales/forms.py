"""
Sales Forms
"""
from django import forms
from .models import Quotation, QuotationItem, Invoice, InvoiceItem
from apps.crm.models import Customer


class QuotationForm(forms.ModelForm):
    """Form for creating/editing quotations."""
    
    class Meta:
        model = Quotation
        fields = ['customer', 'date', 'valid_until', 'status', 'notes', 'terms_and_conditions']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'valid_until': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'notes': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'terms_and_conditions': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['customer'].queryset = Customer.objects.filter(is_active=True)
        self.fields['customer'].widget.attrs['class'] = 'form-select'
        self.fields['status'].widget.attrs['class'] = 'form-select'
        self.fields['valid_until'].required = False


class QuotationItemForm(forms.ModelForm):
    """Form for quotation line items."""
    
    class Meta:
        model = QuotationItem
        fields = ['description', 'quantity', 'unit_price', 'vat_rate']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


QuotationItemFormSet = forms.inlineformset_factory(
    Quotation,
    QuotationItem,
    form=QuotationItemForm,
    extra=1,
    can_delete=True,
    validate_min=False,
    min_num=0
)


class InvoiceForm(forms.ModelForm):
    """Form for creating/editing invoices."""
    
    class Meta:
        model = Invoice
        fields = ['customer', 'quotation', 'invoice_date', 'due_date', 'status', 'notes']
        widgets = {
            'invoice_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'notes': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['customer'].queryset = Customer.objects.filter(is_active=True)
        self.fields['customer'].widget.attrs['class'] = 'form-select'
        self.fields['quotation'].queryset = Quotation.objects.filter(is_active=True, status='approved')
        self.fields['quotation'].widget.attrs['class'] = 'form-select'
        self.fields['quotation'].required = False
        self.fields['status'].widget.attrs['class'] = 'form-select'
        self.fields['notes'].required = False


class InvoiceItemForm(forms.ModelForm):
    """Form for invoice line items."""
    
    class Meta:
        model = InvoiceItem
        fields = ['description', 'quantity', 'unit_price', 'vat_rate']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


InvoiceItemFormSet = forms.inlineformset_factory(
    Invoice,
    InvoiceItem,
    form=InvoiceItemForm,
    extra=1,
    can_delete=True,
    validate_min=False,
    min_num=0
)


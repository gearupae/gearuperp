"""
Inventory Forms
"""
from django import forms
from .models import Category, Warehouse, Item, Stock, StockMovement, ConsumableRequest


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'parent', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name == 'parent':
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'
        self.fields['parent'].queryset = Category.objects.filter(is_active=True)


class WarehouseForm(forms.ModelForm):
    class Meta:
        model = Warehouse
        fields = ['name', 'address', 'contact_person', 'phone', 'status']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name == 'status':
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'


class ItemForm(forms.ModelForm):
    """
    Form for Inventory Items.
    Tax Code determines VAT rate - No Tax Code = 0% VAT (Out of Scope)
    """
    class Meta:
        model = Item
        fields = [
            'name', 'description', 'category', 'item_type', 'status',
            'purchase_price', 'selling_price', 'unit', 'minimum_stock', 'tax_code'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        from apps.finance.models import TaxCode
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name in ['category', 'item_type', 'status', 'tax_code']:
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'
        self.fields['category'].queryset = Category.objects.filter(is_active=True)
        
        # Tax Code queryset and default
        self.fields['tax_code'].queryset = TaxCode.objects.filter(is_active=True)
        self.fields['tax_code'].required = False
        self.fields['tax_code'].empty_label = "-- No Tax (Out of Scope) --"
        
        # Pre-select default tax code if creating new item
        if not self.instance.pk:
            default_tax_code = TaxCode.objects.filter(is_active=True, is_default=True).first()
            if default_tax_code:
                self.fields['tax_code'].initial = default_tax_code


class StockAdjustmentForm(forms.Form):
    """Form for stock adjustments."""
    item = forms.ModelChoiceField(
        queryset=Item.objects.none(),  # Set in __init__ to avoid queryset caching
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_item'}),
        required=True,
        empty_label="Select an item..."
    )
    warehouse = forms.ModelChoiceField(
        queryset=Warehouse.objects.none(),  # Set in __init__ to avoid queryset caching
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_warehouse'}),
        required=True,
        empty_label="Select a warehouse..."
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set querysets fresh each time form is instantiated
        # Show all active items - user can adjust stock for any item
        self.fields['item'].queryset = Item.objects.filter(is_active=True).order_by('name')
        self.fields['warehouse'].queryset = Warehouse.objects.filter(is_active=True, status='active').order_by('name')
    quantity = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    movement_type = forms.ChoiceField(
        choices=[('in', 'Stock In'), ('out', 'Stock Out'), ('adjustment', 'Adjustment')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    reference = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2})
    )


# ============ CONSUMABLE REQUEST FORMS ============

class ConsumableRequestForm(forms.ModelForm):
    """
    Nurse-facing form for creating consumable requests.
    VERY SIMPLE - max 4 fields, no pricing shown.
    """
    class Meta:
        model = ConsumableRequest
        fields = ['item', 'quantity', 'remarks']
        widgets = {
            'remarks': forms.Textarea(attrs={
                'rows': 2, 
                'placeholder': 'Optional notes (e.g., urgent, for procedure room)'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Style fields
        self.fields['item'].widget.attrs['class'] = 'form-select'
        self.fields['quantity'].widget.attrs['class'] = 'form-control'
        self.fields['quantity'].widget.attrs['min'] = '1'
        self.fields['quantity'].widget.attrs['step'] = '1'
        self.fields['remarks'].widget.attrs['class'] = 'form-control'
        
        # Only show active product items (consumables)
        self.fields['item'].queryset = Item.objects.filter(
            is_active=True,
            item_type='product',
            status='active'
        ).order_by('name')
        
        # Simple labels
        self.fields['item'].label = 'Consumable Item'
        self.fields['quantity'].label = 'Quantity Needed'
        self.fields['remarks'].label = 'Notes (Optional)'


class ConsumableRequestApproveForm(forms.Form):
    """Admin form for approving/dispensing requests."""
    warehouse = forms.ModelChoiceField(
        queryset=Warehouse.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=True,
        label='Dispense From Warehouse',
        empty_label='-- Select Warehouse --'
    )
    admin_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        label='Admin Notes'
    )
    
    def __init__(self, *args, item=None, quantity=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.no_stock_available = False
        self.stock_info = []
        
        # Show warehouses with sufficient stock
        if item and quantity:
            # Get all stock for this item
            all_stocks = Stock.objects.filter(
                item=item,
                warehouse__status='active',
                warehouse__is_active=True
            ).select_related('warehouse')
            
            # Build stock info for display
            for stock in all_stocks:
                self.stock_info.append({
                    'warehouse': stock.warehouse,
                    'quantity': stock.quantity,
                    'sufficient': stock.quantity >= quantity
                })
            
            warehouses_with_stock = [s.warehouse.id for s in all_stocks if s.quantity >= quantity]
            
            if warehouses_with_stock:
                self.fields['warehouse'].queryset = Warehouse.objects.filter(
                    id__in=warehouses_with_stock
                )
            else:
                # No sufficient stock - show all active warehouses with warning
                self.no_stock_available = True
                self.fields['warehouse'].queryset = Warehouse.objects.filter(
                    is_active=True, status='active'
                )
                self.fields['warehouse'].help_text = 'WARNING: No warehouse has sufficient stock!'
        else:
            self.fields['warehouse'].queryset = Warehouse.objects.filter(
                is_active=True, status='active'
            )


class ConsumableRequestRejectForm(forms.Form):
    """Form for rejecting a request."""
    reason = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        label='Rejection Reason'
    )


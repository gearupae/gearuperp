"""
Inventory Forms
"""
from django import forms
from .models import Category, Warehouse, Item, Stock, StockMovement


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
    class Meta:
        model = Item
        fields = [
            'name', 'description', 'category', 'item_type', 'status',
            'purchase_price', 'selling_price', 'unit', 'minimum_stock', 'vat_rate'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name in ['category', 'item_type', 'status']:
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'
        self.fields['category'].queryset = Category.objects.filter(is_active=True)


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


"""
Inventory Models - Categories, Warehouses, Items, Stock
With full accounting integration for:
- Stock In → Inventory Asset Ledger
- Stock Out → Cost of Goods Sold (COGS) Ledger
- Stock Adjustments → Stock Variance / Expense Ledger
"""
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from decimal import Decimal
from apps.core.models import BaseModel
from apps.core.utils import generate_number


class Category(BaseModel):
    """
    Item Category model.
    """
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True, blank=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subcategories'
    )
    description = models.TextField(blank=True)
    
    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Categories'
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.code:
            self.code = generate_number('CATEGORY', Category, 'code')
        super().save(*args, **kwargs)


class Warehouse(BaseModel):
    """
    Warehouse/Location model.
    """
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True, blank=True)
    address = models.TextField(blank=True)
    contact_person = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.code:
            self.code = generate_number('WAREHOUSE', Warehouse, 'code')
        super().save(*args, **kwargs)


class Item(BaseModel):
    """
    Inventory Item model.
    """
    TYPE_CHOICES = [
        ('product', 'Product'),
        ('service', 'Service'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    
    item_code = models.CharField(max_length=50, unique=True, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='items'
    )
    item_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='product')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Pricing
    purchase_price = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    selling_price = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    # Stock
    unit = models.CharField(max_length=20, default='pcs')  # pcs, kg, m, etc.
    minimum_stock = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # VAT
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('5.00'))  # UAE VAT
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.item_code} - {self.name}"
    
    def save(self, *args, **kwargs):
        if not self.item_code:
            self.item_code = generate_number('ITEM', Item, 'item_code')
        super().save(*args, **kwargs)
    
    @property
    def total_stock(self):
        """Get total stock across all warehouses."""
        # Query fresh from database to avoid caching issues
        # Use related manager with .all() to ensure fresh query
        result = self.stock_records.filter(
            warehouse__is_active=True
        ).aggregate(
            total=models.Sum('quantity')
        )['total']
        return result if result is not None else Decimal('0.00')
    
    @property
    def is_low_stock(self):
        """Check if item is below minimum stock level."""
        return self.total_stock < self.minimum_stock


class Stock(BaseModel):
    """
    Stock level per warehouse.
    """
    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name='stock_records'
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name='stock_records'
    )
    quantity = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    class Meta:
        unique_together = ['item', 'warehouse']
        ordering = ['warehouse', 'item']
    
    def __str__(self):
        return f"{self.item.name} @ {self.warehouse.name}: {self.quantity}"


class StockMovement(BaseModel):
    """
    Stock movement history with full accounting integration.
    
    Accounting Entries (SAP/Oracle Standard):
    - Stock In (Purchase):  Dr Inventory Asset, Cr GRN Clearing / AP
    - Stock Out (Sales):    Dr COGS, Cr Inventory Asset
    - Stock Adjustment (+): Dr Inventory Asset, Cr Stock Variance
    - Stock Adjustment (-): Dr Stock Variance, Cr Inventory Asset
    - Transfer:             Dr Inventory (To), Cr Inventory (From) - same account
    """
    MOVEMENT_TYPE_CHOICES = [
        ('in', 'Stock In'),
        ('out', 'Stock Out'),
        ('transfer', 'Transfer'),
        ('adjustment_plus', 'Adjustment (+)'),
        ('adjustment_minus', 'Adjustment (-)'),
    ]
    
    SOURCE_CHOICES = [
        ('manual', 'Manual Entry'),
        ('purchase', 'Purchase Order'),
        ('sales', 'Sales Invoice'),
        ('production', 'Production'),
        ('return', 'Return'),
        ('opening', 'Opening Balance'),
    ]
    
    movement_number = models.CharField(max_length=50, unique=False, editable=False, blank=True, default='')
    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name='movements'
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name='movements'
    )
    # For transfers
    to_warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='incoming_movements'
    )
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPE_CHOICES)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='manual')
    quantity = models.DecimalField(max_digits=15, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    total_cost = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    reference = models.CharField(max_length=200, blank=True)  # PO, Invoice, etc.
    notes = models.TextField(blank=True)
    movement_date = models.DateField()
    
    # Accounting link
    journal_entry = models.ForeignKey(
        'finance.JournalEntry',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_movements'
    )
    posted = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-movement_date', '-created_at']
    
    def __str__(self):
        return f"{self.movement_number}: {self.get_movement_type_display()} - {self.item.name} ({self.quantity})"
    
    def save(self, *args, **kwargs):
        if not self.movement_number:
            self.movement_number = generate_number('STK-MOV', StockMovement, 'movement_number')
        
        # Calculate total cost
        if self.unit_cost and self.quantity:
            self.total_cost = self.unit_cost * abs(self.quantity)
        elif self.item and self.item.purchase_price:
            self.unit_cost = self.item.purchase_price
            self.total_cost = self.unit_cost * abs(self.quantity)
        
        super().save(*args, **kwargs)
    
    def update_stock(self):
        """Update stock levels based on movement type."""
        # Get or create stock record
        stock, created = Stock.objects.get_or_create(
            item=self.item,
            warehouse=self.warehouse,
            defaults={'quantity': Decimal('0.00')}
        )
        
        if self.movement_type == 'in':
            stock.quantity += self.quantity
        elif self.movement_type == 'out':
            if stock.quantity < self.quantity:
                raise ValidationError(f"Insufficient stock. Available: {stock.quantity}")
            stock.quantity -= self.quantity
        elif self.movement_type == 'adjustment_plus':
            stock.quantity += self.quantity
        elif self.movement_type == 'adjustment_minus':
            if stock.quantity < self.quantity:
                raise ValidationError(f"Insufficient stock for adjustment. Available: {stock.quantity}")
            stock.quantity -= self.quantity
        elif self.movement_type == 'transfer':
            if not self.to_warehouse:
                raise ValidationError("Transfer requires destination warehouse.")
            if stock.quantity < self.quantity:
                raise ValidationError(f"Insufficient stock for transfer. Available: {stock.quantity}")
            # Decrease from source
            stock.quantity -= self.quantity
            # Increase in destination
            to_stock, _ = Stock.objects.get_or_create(
                item=self.item,
                warehouse=self.to_warehouse,
                defaults={'quantity': Decimal('0.00')}
            )
            to_stock.quantity += self.quantity
            to_stock.save()
        
        stock.save()
    
    def post_to_accounting(self, user=None):
        """
        Post stock movement to accounting.
        Uses Account Mapping for account determination.
        
        Stock In:  Dr Inventory Asset, Cr GRN Clearing
        Stock Out: Dr COGS, Cr Inventory Asset
        Adjustment (+): Dr Inventory Asset, Cr Stock Variance
        Adjustment (-): Dr Stock Variance, Cr Inventory Asset
        """
        from apps.finance.models import JournalEntry, JournalEntryLine, AccountMapping
        
        if self.posted:
            raise ValidationError("Movement already posted to accounting.")
        
        if self.total_cost <= 0:
            raise ValidationError("Movement cost must be greater than zero for accounting.")
        
        # Get accounts from mapping
        inventory_account = AccountMapping.get_account_or_default('inventory_asset', '1500')
        cogs_account = AccountMapping.get_account_or_default('inventory_cogs', '5100')
        grn_clearing = AccountMapping.get_account_or_default('inventory_grn_clearing', '2010')
        stock_variance = AccountMapping.get_account_or_default('inventory_variance', '5200')
        
        if not inventory_account:
            raise ValidationError("Inventory Asset account not configured in Account Mapping.")
        
        # Create journal entry
        journal = JournalEntry.objects.create(
            date=self.movement_date,
            reference=self.movement_number,
            description=f"Stock {self.get_movement_type_display()}: {self.item.name} ({self.quantity} {self.item.unit})",
            entry_type='standard',
            source_module='inventory',
        )
        
        if self.movement_type == 'in':
            # Stock In: Dr Inventory Asset, Cr GRN Clearing
            if not grn_clearing:
                raise ValidationError("GRN Clearing account not configured.")
            JournalEntryLine.objects.create(
                journal_entry=journal,
                account=inventory_account,
                description=f"Inventory - {self.item.name}",
                debit=self.total_cost,
                credit=Decimal('0.00'),
            )
            JournalEntryLine.objects.create(
                journal_entry=journal,
                account=grn_clearing,
                description=f"GRN Clearing - {self.reference or self.movement_number}",
                debit=Decimal('0.00'),
                credit=self.total_cost,
            )
        
        elif self.movement_type == 'out':
            # Stock Out: Dr COGS, Cr Inventory Asset
            if not cogs_account:
                raise ValidationError("COGS account not configured.")
            JournalEntryLine.objects.create(
                journal_entry=journal,
                account=cogs_account,
                description=f"COGS - {self.item.name}",
                debit=self.total_cost,
                credit=Decimal('0.00'),
            )
            JournalEntryLine.objects.create(
                journal_entry=journal,
                account=inventory_account,
                description=f"Inventory - {self.item.name}",
                debit=Decimal('0.00'),
                credit=self.total_cost,
            )
        
        elif self.movement_type == 'adjustment_plus':
            # Adjustment (+): Dr Inventory Asset, Cr Stock Variance
            if not stock_variance:
                raise ValidationError("Stock Variance account not configured.")
            JournalEntryLine.objects.create(
                journal_entry=journal,
                account=inventory_account,
                description=f"Inventory Adjustment (+) - {self.item.name}",
                debit=self.total_cost,
                credit=Decimal('0.00'),
            )
            JournalEntryLine.objects.create(
                journal_entry=journal,
                account=stock_variance,
                description=f"Stock Variance - {self.item.name}",
                debit=Decimal('0.00'),
                credit=self.total_cost,
            )
        
        elif self.movement_type == 'adjustment_minus':
            # Adjustment (-): Dr Stock Variance, Cr Inventory Asset
            if not stock_variance:
                raise ValidationError("Stock Variance account not configured.")
            JournalEntryLine.objects.create(
                journal_entry=journal,
                account=stock_variance,
                description=f"Stock Variance - {self.item.name}",
                debit=self.total_cost,
                credit=Decimal('0.00'),
            )
            JournalEntryLine.objects.create(
                journal_entry=journal,
                account=inventory_account,
                description=f"Inventory Adjustment (-) - {self.item.name}",
                debit=Decimal('0.00'),
                credit=self.total_cost,
            )
        
        elif self.movement_type == 'transfer':
            # Transfer: No P&L impact, just memo entry or skip
            # In most systems, internal transfers don't create GL entries
            # unless tracking by location in GL
            journal.description = f"Stock Transfer: {self.item.name} from {self.warehouse.name} to {self.to_warehouse.name}"
            # Optional: Could create location-based entries if needed
        
        journal.calculate_totals()
        journal.post(user)
        
        self.journal_entry = journal
        self.posted = True
        self.save(update_fields=['journal_entry', 'posted'])
        
        return journal


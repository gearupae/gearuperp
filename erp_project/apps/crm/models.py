"""
CRM Models - Customer/Lead Management
"""
from decimal import Decimal
from django.db import models
from apps.core.models import BaseModel
from apps.core.utils import generate_number


class Customer(BaseModel):
    """
    Customer/Lead model for CRM module.
    """
    CUSTOMER_TYPE_CHOICES = [
        ('lead', 'Lead'),
        ('customer', 'Customer'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('prospect', 'Prospect'),
    ]
    
    customer_number = models.CharField(max_length=50, unique=True, editable=False)
    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    company = models.CharField(max_length=200, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default='United Arab Emirates')
    trn = models.CharField(max_length=20, blank=True, verbose_name='Tax Registration Number (TRN)', 
                          help_text='UAE VAT TRN for B2B invoices')
    payment_terms = models.CharField(max_length=50, blank=True, default='Net 30')
    credit_limit = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    customer_type = models.CharField(max_length=20, choices=CUSTOMER_TYPE_CHOICES, default='lead')
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Customer'
        verbose_name_plural = 'Customers'
    
    def __str__(self):
        return f"{self.customer_number} - {self.name}"
    
    def save(self, *args, **kwargs):
        if not self.customer_number:
            self.customer_number = generate_number('CUSTOMER', Customer, 'customer_number')
        super().save(*args, **kwargs)
    
    @property
    def display_name(self):
        """Return company name if available, otherwise contact name."""
        return self.company if self.company else self.name



"""
Audit Logging Utility for ERP System.
Provides comprehensive audit trail for all modules, especially Finance.
UAE VAT & Corporate Tax compliant.
"""
from django.db import models
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from .middleware import get_current_user, get_current_request
import json


def get_client_ip(request):
    """Extract client IP from request."""
    if not request:
        return None
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def log_audit(user, action, model_name, record_id=None, changes=None, request=None):
    """
    Create an audit log entry.
    
    Args:
        user: The user performing the action
        action: One of 'create', 'update', 'delete', 'view', 'post', 'reverse', 'approve'
        model_name: Name of the model being modified
        record_id: Primary key of the record
        changes: Dictionary of changes (old_value, new_value)
        request: HTTP request object (optional)
    """
    from apps.settings_app.models import AuditLog
    
    ip_address = None
    if request:
        ip_address = get_client_ip(request)
    elif not request:
        # Try to get from thread local
        current_request = get_current_request()
        if current_request:
            ip_address = get_client_ip(current_request)
    
    # Ensure changes is JSON serializable
    if changes:
        try:
            json.dumps(changes)
        except (TypeError, ValueError):
            changes = {'message': str(changes)}
    
    AuditLog.objects.create(
        user=user,
        action=action,
        model=model_name,
        record_id=str(record_id) if record_id else '',
        changes=changes or {},
        ip_address=ip_address
    )


def log_finance_action(user, action, model_instance, details=None):
    """
    Log a finance-specific action with enhanced details.
    
    Args:
        user: User performing the action
        action: Action type (create, update, delete, post, reverse, reconcile, etc.)
        model_instance: The model instance being modified
        details: Additional details dictionary
    """
    model_name = model_instance.__class__.__name__
    record_id = getattr(model_instance, 'pk', None)
    
    # Build changes dictionary
    changes = details or {}
    
    # Add common fields based on model type
    if hasattr(model_instance, 'entry_number'):
        changes['entry_number'] = model_instance.entry_number
    if hasattr(model_instance, 'invoice_number'):
        changes['invoice_number'] = model_instance.invoice_number
    if hasattr(model_instance, 'bill_number'):
        changes['bill_number'] = model_instance.bill_number
    if hasattr(model_instance, 'payment_number'):
        changes['payment_number'] = model_instance.payment_number
    if hasattr(model_instance, 'status'):
        changes['status'] = model_instance.status
    if hasattr(model_instance, 'total_amount'):
        changes['total_amount'] = str(model_instance.total_amount)
    if hasattr(model_instance, 'total_debit'):
        changes['total_debit'] = str(model_instance.total_debit)
    if hasattr(model_instance, 'total_credit'):
        changes['total_credit'] = str(model_instance.total_credit)
    if hasattr(model_instance, 'source_module'):
        changes['source_module'] = model_instance.source_module
    
    log_audit(user, action, model_name, record_id, changes)


class AuditMixin:
    """
    Mixin for models that need audit logging.
    Tracks create, update, delete operations automatically.
    """
    _original_values = None
    
    def _get_field_value(self, field_name):
        """Get the value of a field, handling related fields."""
        value = getattr(self, field_name, None)
        if hasattr(value, 'pk'):
            return str(value)
        if hasattr(value, 'isoformat'):
            return value.isoformat()
        return value
    
    def _get_changes(self, old_instance):
        """Compare current instance with old instance and return changes."""
        changes = {}
        for field in self._meta.fields:
            field_name = field.name
            if field_name in ['created_at', 'updated_at', 'id', 'pk']:
                continue
            
            old_value = old_instance._get_field_value(field_name) if old_instance else None
            new_value = self._get_field_value(field_name)
            
            if old_value != new_value:
                changes[field_name] = {
                    'old': old_value,
                    'new': new_value
                }
        return changes


# Finance-specific audit decorators and utilities

def audit_journal_post(journal_entry, user):
    """Log journal entry posting."""
    log_finance_action(user, 'post', journal_entry, {
        'action': 'Journal Posted',
        'entry_number': journal_entry.entry_number,
        'date': str(journal_entry.date),
        'total_debit': str(journal_entry.total_debit),
        'total_credit': str(journal_entry.total_credit),
        'source_module': journal_entry.source_module,
    })


def audit_journal_reverse(original_journal, reversal_journal, user, reason=''):
    """Log journal entry reversal."""
    log_finance_action(user, 'reverse', original_journal, {
        'action': 'Journal Reversed',
        'original_entry': original_journal.entry_number,
        'reversal_entry': reversal_journal.entry_number,
        'reason': reason,
    })


def audit_payment_post(payment, user):
    """Log payment posting."""
    log_finance_action(user, 'post', payment, {
        'action': 'Payment Posted',
        'payment_number': payment.payment_number,
        'payment_type': payment.payment_type,
        'amount': str(payment.amount),
    })


def audit_invoice_post(invoice, user):
    """Log invoice posting."""
    log_finance_action(user, 'post', invoice, {
        'action': 'Invoice Posted',
        'invoice_number': invoice.invoice_number,
        'customer': str(invoice.customer),
        'total_amount': str(invoice.total_amount),
    })


def audit_bill_post(bill, user):
    """Log vendor bill posting."""
    log_finance_action(user, 'post', bill, {
        'action': 'Bill Posted',
        'bill_number': bill.bill_number,
        'vendor': str(bill.vendor),
        'total_amount': str(bill.total_amount),
    })


def audit_reconciliation(statement, user, action_type='reconcile'):
    """Log bank reconciliation action."""
    log_finance_action(user, action_type, statement, {
        'action': f'Bank Statement {action_type.title()}',
        'statement_number': statement.statement_number,
        'bank_account': str(statement.bank_account),
    })


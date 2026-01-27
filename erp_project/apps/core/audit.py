"""
Audit Logging Utility for ERP System.
Provides comprehensive audit trail for all modules, especially Finance.
UAE VAT & Corporate Tax compliant - IFRS auditable.
"""
from django.db import models
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from .middleware import get_current_user, get_current_request
import json
from decimal import Decimal


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


def serialize_value(value):
    """Convert value to JSON-serializable format."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    if hasattr(value, 'pk'):
        return str(value)
    return value


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


# ============================================
# FINANCE-GRADE AUDIT LOGGING
# IFRS & UAE Audit Compliant
# ============================================

def log_finance_audit(
    user, 
    action, 
    entity_type, 
    entity_id, 
    reference_number=None,
    amount_before=None, 
    amount_after=None,
    affected_accounts=None,
    accounting_period=None,
    reason=None,
    details=None,
    request=None
):
    """
    Log a finance-specific action with full audit metadata.
    
    Args:
        user: User performing the action
        action: Action type (create, post, approve, reverse, lock, reconcile, etc.)
        entity_type: Type of entity (Journal, Payment, Invoice, Bill, Asset, Payroll, etc.)
        entity_id: Primary key of the entity
        reference_number: Document reference (entry_number, invoice_number, etc.)
        amount_before: Amount before the action (for updates)
        amount_after: Amount after the action
        affected_accounts: List of account codes affected
        accounting_period: Accounting period name/id
        reason: Mandatory for reversals & backdated actions
        details: Additional details dictionary
        request: HTTP request object
    """
    from apps.settings_app.models import AuditLog
    
    ip_address = None
    if request:
        ip_address = get_client_ip(request)
    else:
        current_request = get_current_request()
        if current_request:
            ip_address = get_client_ip(current_request)
    
    # Build comprehensive audit payload
    changes = {
        'module': 'Finance',
        'entity_type': entity_type,
        'entity_id': str(entity_id),
        'reference_number': reference_number,
        'action_type': action,
    }
    
    if amount_before is not None:
        changes['amount_before'] = serialize_value(amount_before)
    if amount_after is not None:
        changes['amount_after'] = serialize_value(amount_after)
    if affected_accounts:
        changes['affected_accounts'] = affected_accounts if isinstance(affected_accounts, list) else [affected_accounts]
    if accounting_period:
        changes['accounting_period'] = str(accounting_period)
    if reason:
        changes['reason'] = reason
    if details:
        changes.update(details)
    
    AuditLog.objects.create(
        user=user,
        action=action,
        model=f"Finance.{entity_type}",
        record_id=str(entity_id),
        changes=changes,
        ip_address=ip_address
    )


def get_entity_audit_history(entity_type, entity_id):
    """
    Get audit history for a specific finance entity.
    Used for the "Audit History" tab on detail pages.
    """
    from apps.settings_app.models import AuditLog
    
    return AuditLog.objects.filter(
        models.Q(model=f"Finance.{entity_type}") | models.Q(model=entity_type),
        record_id=str(entity_id)
    ).select_related('user').order_by('-timestamp')


# ============================================
# JOURNAL ENTRY AUDIT
# ============================================

def audit_journal_create(journal, user, request=None):
    """Log journal entry creation."""
    affected_accounts = list(journal.lines.values_list('account__code', flat=True).distinct())
    
    log_finance_audit(
        user=user,
        action='create',
        entity_type='JournalEntry',
        entity_id=journal.pk,
        reference_number=journal.entry_number,
        amount_after=journal.total_debit,
        affected_accounts=affected_accounts,
        accounting_period=str(journal.period) if journal.period else None,
        details={
            'date': serialize_value(journal.date),
            'description': journal.description,
            'source_module': journal.source_module,
            'is_system_generated': journal.is_system_generated,
        },
        request=request
    )


def audit_journal_post(journal, user, request=None):
    """Log journal entry posting."""
    affected_accounts = list(journal.lines.values_list('account__code', flat=True).distinct())
    
    log_finance_audit(
        user=user,
        action='post',
        entity_type='JournalEntry',
        entity_id=journal.pk,
        reference_number=journal.entry_number,
        amount_after=journal.total_debit,
        affected_accounts=affected_accounts,
        accounting_period=str(journal.period) if journal.period else None,
        details={
            'date': serialize_value(journal.date),
            'total_debit': serialize_value(journal.total_debit),
            'total_credit': serialize_value(journal.total_credit),
            'source_module': journal.source_module,
            'line_count': journal.lines.count(),
        },
        request=request
    )


def audit_journal_reverse(original, reversal, user, reason='', request=None):
    """Log journal entry reversal."""
    affected_accounts = list(original.lines.values_list('account__code', flat=True).distinct())
    
    log_finance_audit(
        user=user,
        action='reverse',
        entity_type='JournalEntry',
        entity_id=original.pk,
        reference_number=original.entry_number,
        amount_before=original.total_debit,
        amount_after=Decimal('0.00'),
        affected_accounts=affected_accounts,
        accounting_period=str(original.period) if original.period else None,
        reason=reason or 'User requested reversal',
        details={
            'reversal_entry_number': reversal.entry_number,
            'reversal_entry_id': reversal.pk,
            'reversal_date': serialize_value(reversal.date),
        },
        request=request
    )


# ============================================
# PAYMENT AUDIT
# ============================================

def audit_payment_create(payment, user, request=None):
    """Log payment creation."""
    log_finance_audit(
        user=user,
        action='create',
        entity_type='Payment',
        entity_id=payment.pk,
        reference_number=payment.payment_number,
        amount_after=payment.amount,
        affected_accounts=[payment.bank_account.gl_account.code] if payment.bank_account and payment.bank_account.gl_account else None,
        details={
            'payment_type': payment.payment_type,
            'payment_method': payment.payment_method,
            'date': serialize_value(payment.payment_date),
        },
        request=request
    )


def audit_payment_post(payment, user, request=None):
    """Log payment posting."""
    log_finance_audit(
        user=user,
        action='post',
        entity_type='Payment',
        entity_id=payment.pk,
        reference_number=payment.payment_number,
        amount_after=payment.amount,
        affected_accounts=[payment.bank_account.gl_account.code] if payment.bank_account and payment.bank_account.gl_account else None,
        details={
            'payment_type': payment.payment_type,
            'payment_method': payment.payment_method,
            'date': serialize_value(payment.payment_date),
            'journal_entry': payment.journal_entry.entry_number if payment.journal_entry else None,
        },
        request=request
    )


# ============================================
# INVOICE AUDIT
# ============================================

def audit_invoice_create(invoice, user, request=None):
    """Log invoice creation."""
    log_finance_audit(
        user=user,
        action='create',
        entity_type='Invoice',
        entity_id=invoice.pk,
        reference_number=invoice.invoice_number,
        amount_after=invoice.total_amount,
        details={
            'customer': str(invoice.customer),
            'date': serialize_value(invoice.invoice_date),
            'due_date': serialize_value(invoice.due_date),
            'status': invoice.status,
        },
        request=request
    )


def audit_invoice_post(invoice, user, request=None):
    """Log invoice posting/approval."""
    log_finance_audit(
        user=user,
        action='post',
        entity_type='Invoice',
        entity_id=invoice.pk,
        reference_number=invoice.invoice_number,
        amount_after=invoice.total_amount,
        details={
            'customer': str(invoice.customer),
            'subtotal': serialize_value(invoice.subtotal),
            'vat_amount': serialize_value(invoice.vat_amount),
            'total_amount': serialize_value(invoice.total_amount),
            'journal_entry': invoice.journal_entry.entry_number if hasattr(invoice, 'journal_entry') and invoice.journal_entry else None,
        },
        request=request
    )


# ============================================
# VENDOR BILL AUDIT
# ============================================

def audit_bill_create(bill, user, request=None):
    """Log vendor bill creation."""
    log_finance_audit(
        user=user,
        action='create',
        entity_type='Bill',
        entity_id=bill.pk,
        reference_number=bill.bill_number,
        amount_after=bill.total_amount,
        details={
            'vendor': str(bill.vendor),
            'date': serialize_value(bill.bill_date),
            'due_date': serialize_value(bill.due_date),
            'status': bill.status,
        },
        request=request
    )


def audit_bill_post(bill, user, request=None):
    """Log vendor bill posting/approval."""
    log_finance_audit(
        user=user,
        action='post',
        entity_type='Bill',
        entity_id=bill.pk,
        reference_number=bill.bill_number,
        amount_after=bill.total_amount,
        details={
            'vendor': str(bill.vendor),
            'subtotal': serialize_value(bill.subtotal),
            'vat_amount': serialize_value(bill.vat_amount),
            'total_amount': serialize_value(bill.total_amount),
            'journal_entry': bill.journal_entry.entry_number if hasattr(bill, 'journal_entry') and bill.journal_entry else None,
        },
        request=request
    )


# ============================================
# EXPENSE CLAIM AUDIT
# ============================================

def audit_expense_create(expense, user, request=None):
    """Log expense claim creation."""
    log_finance_audit(
        user=user,
        action='create',
        entity_type='ExpenseClaim',
        entity_id=expense.pk,
        reference_number=getattr(expense, 'claim_number', str(expense.pk)),
        amount_after=expense.total_amount,
        details={
            'employee': str(expense.employee) if hasattr(expense, 'employee') else None,
            'date': serialize_value(expense.expense_date) if hasattr(expense, 'expense_date') else None,
            'status': expense.status,
        },
        request=request
    )


def audit_expense_approve(expense, user, request=None):
    """Log expense claim approval."""
    log_finance_audit(
        user=user,
        action='approve',
        entity_type='ExpenseClaim',
        entity_id=expense.pk,
        reference_number=getattr(expense, 'claim_number', str(expense.pk)),
        amount_after=expense.total_amount,
        details={
            'employee': str(expense.employee) if hasattr(expense, 'employee') else None,
            'approved_amount': serialize_value(expense.total_amount),
            'journal_entry': expense.journal_entry.entry_number if hasattr(expense, 'journal_entry') and expense.journal_entry else None,
        },
        request=request
    )


# ============================================
# FIXED ASSET AUDIT
# ============================================

def audit_asset_create(asset, user, request=None):
    """Log fixed asset creation."""
    log_finance_audit(
        user=user,
        action='create',
        entity_type='Asset',
        entity_id=asset.pk,
        reference_number=asset.asset_number if hasattr(asset, 'asset_number') else str(asset.pk),
        amount_after=asset.purchase_cost if hasattr(asset, 'purchase_cost') else None,
        details={
            'name': asset.name,
            'category': str(asset.category) if hasattr(asset, 'category') and asset.category else None,
            'purchase_date': serialize_value(asset.purchase_date) if hasattr(asset, 'purchase_date') else None,
            'status': asset.status if hasattr(asset, 'status') else None,
        },
        request=request
    )


def audit_asset_depreciation(asset, depreciation_amount, user, request=None):
    """Log asset depreciation run."""
    log_finance_audit(
        user=user,
        action='update',
        entity_type='Asset',
        entity_id=asset.pk,
        reference_number=asset.asset_number if hasattr(asset, 'asset_number') else str(asset.pk),
        amount_before=asset.book_value + depreciation_amount if hasattr(asset, 'book_value') else None,
        amount_after=asset.book_value if hasattr(asset, 'book_value') else None,
        details={
            'action': 'Depreciation Run',
            'depreciation_amount': serialize_value(depreciation_amount),
            'accumulated_depreciation': serialize_value(asset.accumulated_depreciation) if hasattr(asset, 'accumulated_depreciation') else None,
            'book_value': serialize_value(asset.book_value) if hasattr(asset, 'book_value') else None,
        },
        request=request
    )


def audit_asset_dispose(asset, user, reason='', request=None):
    """Log asset disposal."""
    log_finance_audit(
        user=user,
        action='delete',
        entity_type='Asset',
        entity_id=asset.pk,
        reference_number=asset.asset_number if hasattr(asset, 'asset_number') else str(asset.pk),
        amount_before=asset.book_value if hasattr(asset, 'book_value') else None,
        amount_after=Decimal('0.00'),
        reason=reason or 'Asset disposed',
        details={
            'action': 'Asset Disposed',
            'disposal_date': serialize_value(asset.disposal_date) if hasattr(asset, 'disposal_date') else None,
        },
        request=request
    )


# ============================================
# PAYROLL AUDIT
# ============================================

def audit_payroll_create(payroll, user, request=None):
    """Log payroll creation."""
    log_finance_audit(
        user=user,
        action='create',
        entity_type='Payroll',
        entity_id=payroll.pk,
        reference_number=str(payroll.pk),
        amount_after=payroll.net_salary if hasattr(payroll, 'net_salary') else None,
        accounting_period=f"{payroll.month}/{payroll.year}" if hasattr(payroll, 'month') and hasattr(payroll, 'year') else None,
        details={
            'employee': str(payroll.employee) if hasattr(payroll, 'employee') else None,
            'gross_salary': serialize_value(payroll.gross_salary) if hasattr(payroll, 'gross_salary') else None,
            'net_salary': serialize_value(payroll.net_salary) if hasattr(payroll, 'net_salary') else None,
            'status': payroll.status if hasattr(payroll, 'status') else None,
        },
        request=request
    )


def audit_payroll_process(payroll, user, request=None):
    """Log payroll processing."""
    log_finance_audit(
        user=user,
        action='post',
        entity_type='Payroll',
        entity_id=payroll.pk,
        reference_number=str(payroll.pk),
        amount_after=payroll.net_salary if hasattr(payroll, 'net_salary') else None,
        accounting_period=f"{payroll.month}/{payroll.year}" if hasattr(payroll, 'month') and hasattr(payroll, 'year') else None,
        details={
            'action': 'Payroll Processed',
            'employee': str(payroll.employee) if hasattr(payroll, 'employee') else None,
            'gross_salary': serialize_value(payroll.gross_salary) if hasattr(payroll, 'gross_salary') else None,
            'total_deductions': serialize_value(payroll.total_deductions) if hasattr(payroll, 'total_deductions') else None,
            'net_salary': serialize_value(payroll.net_salary) if hasattr(payroll, 'net_salary') else None,
            'journal_entry': payroll.journal_entry.entry_number if hasattr(payroll, 'journal_entry') and payroll.journal_entry else None,
        },
        request=request
    )


# ============================================
# BANK RECONCILIATION AUDIT
# ============================================

def audit_reconciliation_start(statement, user, request=None):
    """Log bank reconciliation start."""
    log_finance_audit(
        user=user,
        action='update',
        entity_type='BankReconciliation',
        entity_id=statement.pk,
        reference_number=statement.statement_number,
        details={
            'action': 'Reconciliation Started',
            'bank_account': str(statement.bank_account),
            'period': f"{statement.statement_start_date} to {statement.statement_end_date}",
            'opening_balance': serialize_value(statement.opening_balance),
            'closing_balance': serialize_value(statement.closing_balance),
        },
        request=request
    )


def audit_reconciliation_complete(statement, user, request=None):
    """Log bank reconciliation completion."""
    log_finance_audit(
        user=user,
        action='reconcile',
        entity_type='BankReconciliation',
        entity_id=statement.pk,
        reference_number=statement.statement_number,
        details={
            'action': 'Reconciliation Completed',
            'bank_account': str(statement.bank_account),
            'matched_count': statement.matched_count if hasattr(statement, 'matched_count') else None,
            'total_lines': statement.total_lines if hasattr(statement, 'total_lines') else None,
        },
        request=request
    )


def audit_reconciliation_lock(statement, user, request=None):
    """Log bank reconciliation lock."""
    log_finance_audit(
        user=user,
        action='lock',
        entity_type='BankReconciliation',
        entity_id=statement.pk,
        reference_number=statement.statement_number,
        details={
            'action': 'Statement Locked',
            'bank_account': str(statement.bank_account),
            'locked_by': user.username,
        },
        request=request
    )


# ============================================
# VAT RETURN AUDIT
# ============================================

def audit_vat_return_create(vat_return, user, request=None):
    """Log VAT return creation."""
    log_finance_audit(
        user=user,
        action='create',
        entity_type='VATReturn',
        entity_id=vat_return.pk,
        reference_number=vat_return.return_number if hasattr(vat_return, 'return_number') else str(vat_return.pk),
        amount_after=vat_return.net_vat if hasattr(vat_return, 'net_vat') else None,
        accounting_period=f"{vat_return.period_start} to {vat_return.period_end}" if hasattr(vat_return, 'period_start') else None,
        details={
            'output_vat': serialize_value(vat_return.output_vat) if hasattr(vat_return, 'output_vat') else None,
            'input_vat': serialize_value(vat_return.input_vat) if hasattr(vat_return, 'input_vat') else None,
            'net_vat': serialize_value(vat_return.net_vat) if hasattr(vat_return, 'net_vat') else None,
        },
        request=request
    )


def audit_vat_return_file(vat_return, user, request=None):
    """Log VAT return filing."""
    log_finance_audit(
        user=user,
        action='post',
        entity_type='VATReturn',
        entity_id=vat_return.pk,
        reference_number=vat_return.return_number if hasattr(vat_return, 'return_number') else str(vat_return.pk),
        amount_after=vat_return.net_vat if hasattr(vat_return, 'net_vat') else None,
        accounting_period=f"{vat_return.period_start} to {vat_return.period_end}" if hasattr(vat_return, 'period_start') else None,
        details={
            'action': 'VAT Return Filed',
            'filing_date': serialize_value(vat_return.filing_date) if hasattr(vat_return, 'filing_date') else None,
            'status': vat_return.status if hasattr(vat_return, 'status') else None,
        },
        request=request
    )


# ============================================
# GENERIC FINANCE ACTION AUDIT
# ============================================

def log_finance_action(user, action, model_instance, details=None):
    """
    Generic finance action logging (backward compatible).
    """
    model_name = model_instance.__class__.__name__
    record_id = getattr(model_instance, 'pk', None)
    
    # Build changes dictionary
    changes = details or {}
    changes['module'] = 'Finance'
    changes['entity_type'] = model_name
    
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
        changes['total_amount'] = serialize_value(model_instance.total_amount)
    if hasattr(model_instance, 'total_debit'):
        changes['total_debit'] = serialize_value(model_instance.total_debit)
    if hasattr(model_instance, 'total_credit'):
        changes['total_credit'] = serialize_value(model_instance.total_credit)
    if hasattr(model_instance, 'source_module'):
        changes['source_module'] = model_instance.source_module
    
    log_audit(user, action, f"Finance.{model_name}", record_id, changes)

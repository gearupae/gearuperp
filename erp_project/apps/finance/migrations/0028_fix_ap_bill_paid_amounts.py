"""
Fix VendorBill.paid_amount for old bills that were settled via OB-AP-CLEAR-2024.

The opening balance entry (DOC-2026-0083) debited AP 33,840 clearing all pre-2026
payables in GL, but VendorBill.paid_amount was never updated.  This migration
applies FIFO allocation of the 33,840 clearing against old bills, updating their
paid_amount and status fields to match GL reality.
"""

from django.db import migrations
from decimal import Decimal


def fix_ap_bill_paid_amounts(apps, schema_editor):
    JournalEntryLine = apps.get_model('finance', 'JournalEntryLine')
    Account = apps.get_model('finance', 'Account')
    VendorBill = apps.get_model('purchase', 'VendorBill')

    ap_account = Account.objects.filter(code='2000', is_active=True).first()
    if not ap_account:
        return

    bill_numbers = set(
        VendorBill.objects.values_list('bill_number', flat=True)
    )

    # Collect all AP credits grouped by reference
    credit_by_ref = {}
    for line in JournalEntryLine.objects.filter(
        account=ap_account, journal_entry__status='posted', credit__gt=0,
    ).select_related('journal_entry'):
        ref = line.journal_entry.reference
        credit_by_ref.setdefault(ref, {
            'amount': Decimal('0'), 'date': line.journal_entry.date,
        })
        credit_by_ref[ref]['amount'] += line.credit

    # Collect all unmatched AP debits
    unmatched_total = Decimal('0')
    for line in JournalEntryLine.objects.filter(
        account=ap_account, journal_entry__status='posted', debit__gt=0,
    ).select_related('journal_entry'):
        ref = line.journal_entry.reference
        if ref not in credit_by_ref:
            unmatched_total += line.debit

    if unmatched_total <= 0:
        return

    # FIFO: first absorb against non-bill AP credits (payroll, projects, etc.)
    non_bill_credits = sorted(
        [(ref, d) for ref, d in credit_by_ref.items() if ref not in bill_numbers],
        key=lambda x: x[1]['date'],
    )
    remaining = unmatched_total
    for ref, data in non_bill_credits:
        if remaining <= 0:
            break
        allocation = min(remaining, data['amount'])
        remaining -= allocation

    # Whatever remains is applicable to vendor bills (FIFO by date)
    if remaining <= 0:
        return

    for bill in VendorBill.objects.order_by('bill_date'):
        if remaining <= 0:
            break
        outstanding = bill.total_amount - bill.paid_amount
        if outstanding <= 0:
            continue
        allocation = min(remaining, outstanding)
        bill.paid_amount += allocation
        remaining -= allocation
        if bill.paid_amount >= bill.total_amount:
            bill.status = 'paid'
        elif bill.paid_amount > 0:
            bill.status = 'partial'
        bill.save(update_fields=['paid_amount', 'status'])


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0027_reclassify_opening_equity'),
        ('purchase', '0009_add_goods_received_to_vendorbill'),
    ]

    operations = [
        migrations.RunPython(fix_ap_bill_paid_amounts, migrations.RunPython.noop),
    ]

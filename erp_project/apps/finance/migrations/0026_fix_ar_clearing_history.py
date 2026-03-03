"""
Fix AR Clearing History
-----------------------
The original customer payments (DOC-2026-0044, DOC-2026-0046) were posted as
Dr Bank / Cr Revenue instead of Dr Bank / Cr AR.  Correction entries
(CORR-AR-001, CORR-AR-002) fixed the GL, but:
  1. Invoice.paid_amount was never updated (all show 0).
  2. No Payment records were created (empty table).
  3. AR aging FIFO allocation depends on this being correct.

This migration retroactively creates Payment records and updates invoice
paid_amount using FIFO allocation against AR credits.
"""
from django.db import migrations
from decimal import Decimal


def fix_ar_clearing(apps, schema_editor):
    Invoice = apps.get_model('sales', 'Invoice')
    Payment = apps.get_model('finance', 'Payment')
    JournalEntry = apps.get_model('finance', 'JournalEntry')
    BankAccount = apps.get_model('finance', 'BankAccount')

    bank_account = BankAccount.objects.filter(is_active=True).first()

    payments_info = [
        {
            'entry_number': 'DOC-2026-0044',
            'amount': Decimal('75000.00'),
            'date_str': '2026-01-10',
            'party_name': 'Al Noor Trading',
        },
        {
            'entry_number': 'DOC-2026-0046',
            'amount': Decimal('120000.00'),
            'date_str': '2026-02-05',
            'party_name': 'Gulf Star LLC',
        },
    ]

    invoices = list(Invoice.objects.order_by('invoice_date', 'pk'))

    global_remaining = Decimal('0')

    for pinfo in payments_info:
        je = JournalEntry.objects.filter(
            entry_number=pinfo['entry_number'], status='posted'
        ).first()

        from datetime import date as date_cls
        parts = pinfo['date_str'].split('-')
        pmt_date = date_cls(int(parts[0]), int(parts[1]), int(parts[2]))

        seq = Payment.objects.count() + 1
        pmt = Payment.objects.create(
            payment_number=f'PR-HIST-{seq:04d}',
            payment_type='received',
            payment_method='bank',
            payment_date=pmt_date,
            party_type='customer',
            party_id=1,
            party_name=pinfo['party_name'],
            amount=pinfo['amount'],
            allocated_amount=pinfo['amount'],
            reference=pinfo['entry_number'],
            notes=f'Historical payment corrected by migration 0026',
            status='confirmed',
            bank_account=bank_account,
            journal_entry=je,
        )

        remaining = pinfo['amount']
        for inv in invoices:
            if remaining <= 0:
                break
            balance = inv.total_amount - inv.paid_amount
            if balance <= 0:
                continue
            apply = min(remaining, balance)
            inv.paid_amount += apply
            if inv.paid_amount >= inv.total_amount:
                inv.status = 'paid'
            else:
                inv.status = 'partial'
            inv.save()
            remaining -= apply


def reverse_fix(apps, schema_editor):
    Invoice = apps.get_model('sales', 'Invoice')
    Payment = apps.get_model('finance', 'Payment')

    Payment.objects.filter(payment_number__startswith='PR-HIST-').delete()

    for inv in Invoice.objects.all():
        inv.paid_amount = Decimal('0.00')
        if inv.status in ('paid', 'partial'):
            inv.status = 'posted'
        inv.save()


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0025_add_cash_flow_classification'),
        ('sales', '0006_add_tax_code_to_line_items'),
    ]

    operations = [
        migrations.RunPython(fix_ar_clearing, reverse_fix),
    ]

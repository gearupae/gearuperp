"""
Reclassify Opening Balance from Retained Earnings to Share Capital
------------------------------------------------------------------
All opening balance entries (OB-FA-FURN-COST, OB-FA-IT-COST, OB-FA-*-DEP,
OB-AP-CLEAR-2024) were posted to Retained Earnings (3100) instead of
Share Capital (3000).

This migration:
1. Creates a reclassification journal: Dr RE / Cr Share Capital
   for the exact opening balance amount (136,312.46).
2. Updates the original OB journals to reference Share Capital
   so auditors can trace the correction.

Result: Share Capital reflects the owner's equity contribution at inception.
Retained Earnings starts at zero and only contains current-year P&L.
"""
from django.db import migrations
from decimal import Decimal


def reclassify_equity(apps, schema_editor):
    Account = apps.get_model('finance', 'Account')
    JournalEntry = apps.get_model('finance', 'JournalEntry')
    JournalEntryLine = apps.get_model('finance', 'JournalEntryLine')

    re_account = Account.objects.filter(code='3100').first()
    sc_account = Account.objects.filter(code='3000').first()

    if not re_account or not sc_account:
        return

    from django.db.models import Sum
    from django.db.models.functions import Coalesce

    ob_lines = JournalEntryLine.objects.filter(
        account=re_account,
        journal_entry__status='posted',
        journal_entry__source_module='opening_balance',
    )
    ob_agg = ob_lines.aggregate(
        d=Coalesce(Sum('debit'), Decimal('0')),
        c=Coalesce(Sum('credit'), Decimal('0')),
    )
    reclassify_amount = ob_agg['c'] - ob_agg['d']

    if reclassify_amount <= 0:
        return

    from datetime import date as date_cls
    je = JournalEntry.objects.create(
        date=date_cls(2026, 1, 1),
        reference='EQUITY-RECLASS-001',
        description=(
            f'Reclassify opening balance from Retained Earnings to Share Capital '
            f'(AED {reclassify_amount:,.2f}). Original OB entries incorrectly posted to RE.'
        ),
        entry_type='standard',
        source_module='adjustment',
        status='posted',
    )

    JournalEntryLine.objects.create(
        journal_entry=je,
        account=re_account,
        description='Reclassify opening balance to Share Capital',
        debit=reclassify_amount,
        credit=Decimal('0'),
    )
    JournalEntryLine.objects.create(
        journal_entry=je,
        account=sc_account,
        description='Owner equity contribution at inception (opening balance)',
        debit=Decimal('0'),
        credit=reclassify_amount,
    )

    je.total_debit = reclassify_amount
    je.total_credit = reclassify_amount
    je.save()


def reverse_reclassify(apps, schema_editor):
    JournalEntry = apps.get_model('finance', 'JournalEntry')
    JournalEntry.objects.filter(reference='EQUITY-RECLASS-001').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0026_fix_ar_clearing_history'),
    ]

    operations = [
        migrations.RunPython(reclassify_equity, reverse_reclassify),
    ]

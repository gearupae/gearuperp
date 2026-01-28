"""
Management command to seed opening balances for Finance Module.

Creates a single SYSTEM-generated journal entry with all opening balances.
Opening balances are ONLY for Assets, Liabilities, and Equity accounts.
Income & Expense accounts MUST NOT have opening balances.

Usage:
    python manage.py seed_opening_balances
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal
from datetime import date

from apps.finance.models import (
    Account, AccountType, JournalEntry, JournalEntryLine,
    FiscalYear
)


class Command(BaseCommand):
    help = 'Seed opening balances for Finance Module via a single system journal entry'
    
    # Opening Balance Data (as per specification)
    OPENING_BALANCES = [
        # ASSETS (Dr)
        {'code': '100001', 'name': 'ADCB Bank - Current Account', 'type': 'asset', 'debit': Decimal('25000.00'), 'credit': Decimal('0.00'), 'is_cash': True},
        {'code': '100002', 'name': 'ADCB Bank - Fixed Deposit', 'type': 'asset', 'debit': Decimal('25000.00'), 'credit': Decimal('0.00'), 'is_cash': False},
        {'code': '100005', 'name': 'Cash in Hand - Main Safe', 'type': 'asset', 'debit': Decimal('3000.00'), 'credit': Decimal('0.00'), 'is_cash': True},
        {'code': '100006', 'name': 'Cash in Hand - Petty Cash', 'type': 'asset', 'debit': Decimal('2000.00'), 'credit': Decimal('0.00'), 'is_cash': True},
        {'code': '100007', 'name': 'Trade Debtors - Local', 'type': 'asset', 'debit': Decimal('15000.00'), 'credit': Decimal('0.00'), 'is_cash': False},
        {'code': '100008', 'name': 'Trade Debtors - International', 'type': 'asset', 'debit': Decimal('5000.00'), 'credit': Decimal('0.00'), 'is_cash': False},
        {'code': '100010', 'name': 'Furniture & Fixtures', 'type': 'asset', 'debit': Decimal('27000.00'), 'credit': Decimal('0.00'), 'is_cash': False},
        {'code': '100014', 'name': 'Computer Equipment', 'type': 'asset', 'debit': Decimal('20000.00'), 'credit': Decimal('0.00'), 'is_cash': False},
        {'code': '1600', 'name': 'PDC Receivable', 'type': 'asset', 'debit': Decimal('8000.00'), 'credit': Decimal('0.00'), 'is_cash': False},
        
        # LIABILITIES (Cr)
        {'code': '200001', 'name': 'Trade Creditors - Local', 'type': 'liability', 'debit': Decimal('0.00'), 'credit': Decimal('10000.00'), 'is_cash': False},
        {'code': '200002', 'name': 'Trade Creditors - International', 'type': 'liability', 'debit': Decimal('0.00'), 'credit': Decimal('5000.00'), 'is_cash': False},
        {'code': '2100', 'name': 'VAT Payable', 'type': 'liability', 'debit': Decimal('0.00'), 'credit': Decimal('2800.00'), 'is_cash': False},
        
        # EQUITY (Cr)
        {'code': '300001', 'name': 'Capital Account - Partner 1', 'type': 'equity', 'debit': Decimal('0.00'), 'credit': Decimal('45000.00'), 'is_cash': False},
        {'code': '300002', 'name': 'Capital Account - Partner 2', 'type': 'equity', 'debit': Decimal('0.00'), 'credit': Decimal('45000.00'), 'is_cash': False},
    ]
    
    # Retained Earnings account for balancing
    RETAINED_EARNINGS = {
        'code': '300003',
        'name': 'Retained Earnings - Opening Balance',
        'type': 'equity',
        'is_cash': False
    }
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-creation even if opening balance entry exists'
        )
    
    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        force = options.get('force', False)
        
        self.stdout.write(self.style.WARNING('\n' + '='*60))
        self.stdout.write(self.style.WARNING('OPENING BALANCES SEEDING'))
        self.stdout.write(self.style.WARNING('='*60 + '\n'))
        
        # Check if opening balance entry already exists
        existing_entry = JournalEntry.objects.filter(
            reference='OPENING BALANCE',
            entry_type='opening'
        ).first()
        
        if existing_entry and not force:
            self.stdout.write(self.style.ERROR(
                f'Opening balance entry already exists: {existing_entry.entry_number}'
            ))
            self.stdout.write(self.style.WARNING(
                'Use --force to recreate (will delete existing entry)'
            ))
            return
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made\n'))
        
        try:
            with transaction.atomic():
                # Delete existing if force mode
                if existing_entry and force:
                    self.stdout.write(self.style.WARNING(
                        f'Deleting existing opening balance entry: {existing_entry.entry_number}'
                    ))
                    if not dry_run:
                        existing_entry.delete()
                
                # Step 1: Create/verify accounts
                self.stdout.write(self.style.HTTP_INFO('\n1. Creating/verifying accounts...'))
                accounts = self._create_accounts(dry_run)
                
                # Step 2: Calculate totals and balancing figure
                self.stdout.write(self.style.HTTP_INFO('\n2. Calculating balancing figure...'))
                total_debit, total_credit, balancing_amount = self._calculate_balancing()
                
                self.stdout.write(f'   Total Debit:  AED {total_debit:,.2f}')
                self.stdout.write(f'   Total Credit: AED {total_credit:,.2f}')
                self.stdout.write(f'   Balancing (Retained Earnings): AED {balancing_amount:,.2f}')
                
                # Step 3: Create the journal entry
                self.stdout.write(self.style.HTTP_INFO('\n3. Creating journal entry...'))
                journal_entry = self._create_journal_entry(accounts, balancing_amount, dry_run)
                
                # Step 4: Validate the entry
                self.stdout.write(self.style.HTTP_INFO('\n4. Validating journal entry...'))
                self._validate_entry(journal_entry, dry_run)
                
                if dry_run:
                    self.stdout.write(self.style.WARNING('\n[DRY RUN] Rolling back transaction...'))
                    raise Exception('Dry run - rolling back')
                
        except Exception as e:
            if 'Dry run' in str(e):
                self.stdout.write(self.style.SUCCESS('\n✓ Dry run completed successfully'))
            else:
                self.stdout.write(self.style.ERROR(f'\n✗ Error: {e}'))
                raise
            return
        
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('✓ OPENING BALANCES SEEDED SUCCESSFULLY'))
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(f'\nJournal Entry: {journal_entry.entry_number}')
        self.stdout.write(f'Date: {journal_entry.date}')
        self.stdout.write(f'Status: {journal_entry.status}')
        self.stdout.write(f'Total: AED {journal_entry.total_debit:,.2f}')
    
    def _create_accounts(self, dry_run):
        """Create or get accounts for opening balances."""
        accounts = {}
        
        all_accounts = self.OPENING_BALANCES + [self.RETAINED_EARNINGS]
        
        for acc_data in all_accounts:
            account, created = Account.objects.get_or_create(
                code=acc_data['code'],
                defaults={
                    'name': acc_data['name'],
                    'account_type': acc_data['type'],
                    'is_system': True,
                    'is_cash_account': acc_data.get('is_cash', False),
                }
            )
            
            # Update name if account exists
            if not created:
                if account.name != acc_data['name']:
                    account.name = acc_data['name']
                    account.save()
            
            accounts[acc_data['code']] = account
            status = 'CREATED' if created else 'EXISTS'
            self.stdout.write(f'   [{status}] {acc_data["code"]} - {acc_data["name"]}')
        
        return accounts
    
    def _calculate_balancing(self):
        """Calculate totals and the balancing figure for Retained Earnings."""
        total_debit = Decimal('0.00')
        total_credit = Decimal('0.00')
        
        for bal in self.OPENING_BALANCES:
            total_debit += bal['debit']
            total_credit += bal['credit']
        
        # Balancing amount goes to Retained Earnings
        # If Dr > Cr, we need Cr to Retained Earnings
        # If Cr > Dr, we need Dr to Retained Earnings
        balancing_amount = total_debit - total_credit
        
        return total_debit, total_credit, balancing_amount
    
    def _create_journal_entry(self, accounts, balancing_amount, dry_run):
        """Create the opening balance journal entry."""
        
        # Get fiscal year start date
        fiscal_year = FiscalYear.objects.filter(is_active=True).first()
        if fiscal_year:
            entry_date = fiscal_year.start_date
        else:
            # Default to Jan 1 of current year
            entry_date = date(date.today().year, 1, 1)
        
        self.stdout.write(f'   Entry Date: {entry_date}')
        
        if dry_run:
            self.stdout.write('   [DRY RUN] Would create journal entry...')
            return None
        
        # Create journal entry
        journal_entry = JournalEntry.objects.create(
            date=entry_date,
            reference='OPENING BALANCE',
            description='System-generated opening balance entry. This entry cannot be edited or deleted.',
            status='posted',
            entry_type='opening',
            source_module='opening_balance',
            is_system_generated=True,
            is_locked=True,
        )
        
        self.stdout.write(f'   Created: {journal_entry.entry_number}')
        
        # Create journal lines
        line_num = 1
        
        for bal in self.OPENING_BALANCES:
            account = accounts[bal['code']]
            
            if bal['debit'] > 0:
                JournalEntryLine.objects.create(
                    journal_entry=journal_entry,
                    account=account,
                    description=f'Opening Balance - {account.name}',
                    debit=bal['debit'],
                    credit=Decimal('0.00'),
                )
                self.stdout.write(f'   Line {line_num}: Dr {account.code} - {bal["debit"]:,.2f}')
            
            if bal['credit'] > 0:
                JournalEntryLine.objects.create(
                    journal_entry=journal_entry,
                    account=account,
                    description=f'Opening Balance - {account.name}',
                    debit=Decimal('0.00'),
                    credit=bal['credit'],
                )
                self.stdout.write(f'   Line {line_num}: Cr {account.code} - {bal["credit"]:,.2f}')
            
            line_num += 1
        
        # Add balancing line to Retained Earnings
        retained_account = accounts[self.RETAINED_EARNINGS['code']]
        
        if balancing_amount > 0:
            # More debits than credits - need credit to Retained Earnings
            JournalEntryLine.objects.create(
                journal_entry=journal_entry,
                account=retained_account,
                description='Opening Balance - Retained Earnings (Balancing)',
                debit=Decimal('0.00'),
                credit=balancing_amount,
            )
            self.stdout.write(f'   Line {line_num}: Cr {retained_account.code} - {balancing_amount:,.2f} (BALANCING)')
        elif balancing_amount < 0:
            # More credits than debits - need debit to Retained Earnings
            JournalEntryLine.objects.create(
                journal_entry=journal_entry,
                account=retained_account,
                description='Opening Balance - Retained Earnings (Balancing)',
                debit=abs(balancing_amount),
                credit=Decimal('0.00'),
            )
            self.stdout.write(f'   Line {line_num}: Dr {retained_account.code} - {abs(balancing_amount):,.2f} (BALANCING)')
        
        # Update totals
        journal_entry.calculate_totals()
        
        return journal_entry
    
    def _validate_entry(self, journal_entry, dry_run):
        """Validate the journal entry is balanced."""
        if dry_run:
            self.stdout.write('   [DRY RUN] Would validate entry...')
            return
        
        # Refresh from database
        journal_entry.refresh_from_db()
        
        if journal_entry.total_debit != journal_entry.total_credit:
            raise Exception(
                f'Journal entry is NOT balanced! '
                f'Dr: {journal_entry.total_debit}, Cr: {journal_entry.total_credit}'
            )
        
        self.stdout.write(self.style.SUCCESS(
            f'   ✓ Entry is balanced: Dr {journal_entry.total_debit:,.2f} = Cr {journal_entry.total_credit:,.2f}'
        ))
        
        # Verify line count
        line_count = journal_entry.lines.count()
        self.stdout.write(f'   ✓ {line_count} journal lines created')


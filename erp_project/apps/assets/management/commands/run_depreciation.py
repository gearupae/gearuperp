"""
Management command to run monthly depreciation for all active fixed assets.
Should be scheduled as a monthly cron job.

Example cron entry (runs on 1st of each month at 1 AM):
0 1 1 * * cd /path/to/project && python manage.py run_depreciation
"""
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.assets.models import DepreciationBatchRun, FixedAsset


class Command(BaseCommand):
    help = 'Run monthly depreciation for all active fixed assets'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Depreciation date (YYYY-MM-DD). Defaults to last day of previous month.',
        )
        parser.add_argument(
            '--asset',
            type=str,
            help='Specific asset number to depreciate. If not specified, all active assets.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without actually posting to accounting',
        )

    def handle(self, *args, **options):
        if options['date']:
            try:
                depreciation_date = date.fromisoformat(options['date'])
            except ValueError:
                self.stderr.write(self.style.ERROR('Invalid date format. Use YYYY-MM-DD'))
                return
        else:
            today = date.today()
            first_of_month = today.replace(day=1)
            depreciation_date = first_of_month - timedelta(days=1)

        period = depreciation_date.strftime('%Y-%m')
        self.stdout.write(f'Depreciation date: {depreciation_date}  Period: {period}')

        if options['asset']:
            assets = FixedAsset.objects.filter(
                asset_number=options['asset'],
                status='active',
                is_active=True,
            ).select_related('category')
        else:
            assets = FixedAsset.objects.filter(
                status='active',
                is_active=True,
            ).select_related('category')

        if not assets.exists():
            self.stdout.write(self.style.WARNING('No active assets found to depreciate.'))
            return

        self.stdout.write(f'Found {assets.count()} active assets')

        existing = DepreciationBatchRun.objects.filter(
            period=period,
            status__in=['completed', 'completed_with_errors'],
        ).first()
        if existing and not options['dry_run']:
            self.stderr.write(self.style.ERROR(
                f'Depreciation already run for {period} '
                f'(Batch: {existing.batch_number}). '
                f'Reverse the previous run before re-running.'
            ))
            return

        batch_run = None
        if not options['dry_run']:
            batch_run = DepreciationBatchRun.objects.create(
                depreciation_date=depreciation_date,
                total_assets=assets.count(),
            )

        success_count = 0
        skip_count = 0
        error_count = 0
        total_depreciation = Decimal('0.00')

        for asset in assets:
            validation_errors = asset.validate_for_depreciation(depreciation_date)
            if validation_errors:
                is_skip = any(
                    'already depreciated' in e.lower()
                    or 'fully depreciated' in e.lower()
                    for e in validation_errors
                )
                if is_skip:
                    self.stdout.write(f'  SKIP: {asset.asset_number} - {"; ".join(validation_errors)}')
                    skip_count += 1
                else:
                    self.stderr.write(self.style.ERROR(
                        f'  ERROR: {asset.asset_number} - {"; ".join(validation_errors)}'
                    ))
                    error_count += 1
                continue

            if options['dry_run']:
                amount = asset._calculate_period_depreciation(depreciation_date)
                self.stdout.write(
                    f'  DRY RUN: {asset.asset_number} - '
                    f'Would depreciate AED {amount:,.2f}'
                )
                success_count += 1
                total_depreciation += amount
                continue

            try:
                journal = asset.run_depreciation(
                    depreciation_date, batch_run=batch_run,
                )
                dep = asset.depreciation_records.filter(period=period).first()
                amount = dep.depreciation_amount if dep else Decimal('0.00')
                total_depreciation += amount
                self.stdout.write(self.style.SUCCESS(
                    f'  OK: {asset.asset_number} - '
                    f'AED {amount:,.2f} (Journal: {journal.entry_number})'
                ))
                success_count += 1
            except Exception as e:
                self.stderr.write(self.style.ERROR(
                    f'  ERROR: {asset.asset_number} - {e}'
                ))
                error_count += 1

        if batch_run:
            batch_run.success_count = success_count
            batch_run.error_count = error_count
            batch_run.skip_count = skip_count
            batch_run.total_depreciation = total_depreciation
            if error_count and success_count:
                batch_run.status = 'completed_with_errors'
            elif error_count:
                batch_run.status = 'failed'
            else:
                batch_run.status = 'completed'
            batch_run.save()

        self.stdout.write('')
        self.stdout.write('=' * 50)
        self.stdout.write(f'Total Assets:  {assets.count()}')
        self.stdout.write(f'  Depreciated: {success_count}')
        self.stdout.write(f'  Skipped:     {skip_count}')
        self.stdout.write(f'  Errors:      {error_count}')
        self.stdout.write(f'  Total AED:   {total_depreciation:,.2f}')

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('\nDRY RUN - No changes were made'))
        elif batch_run:
            self.stdout.write(self.style.SUCCESS(
                f'\nBatch {batch_run.batch_number} — {batch_run.get_status_display()}'
            ))

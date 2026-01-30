"""
Excel Export Utilities for Finance Reports
Uses openpyxl for Excel generation.
"""
from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
from decimal import Decimal
from datetime import date, datetime


def create_excel_response(filename):
    """Create HttpResponse for Excel file download."""
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def style_header_row(ws, row_num, col_count):
    """Apply header styling to a row."""
    header_font = Font(bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
    header_align = Alignment(horizontal='center', vertical='center')
    
    for col in range(1, col_count + 1):
        cell = ws.cell(row=row_num, column=col)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align


def style_title_row(ws, row_num, title, col_count):
    """Add and style a title row."""
    ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=col_count)
    cell = ws.cell(row=row_num, column=1, value=title)
    cell.font = Font(bold=True, size=14)
    cell.alignment = Alignment(horizontal='center')


def auto_width_columns(ws):
    """Auto-adjust column widths based on content."""
    from openpyxl.cell.cell import MergedCell
    
    for column_cells in ws.columns:
        max_length = 0
        column = None
        for cell in column_cells:
            # Skip merged cells
            if isinstance(cell, MergedCell):
                continue
            # Get column letter from first non-merged cell
            if column is None:
                column = cell.column_letter
            try:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            except:
                pass
        if column:
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column].width = adjusted_width


def format_currency(value):
    """Format decimal as currency string."""
    if value is None:
        return ''
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    return value


# ============ TRIAL BALANCE EXPORT (Standard - As at Date) ============

def export_trial_balance(accounts, as_of_date, company_name=''):
    """
    Export Standard Trial Balance to Excel.
    Shows only net balances as Debit OR Credit per account.
    IFRS & UAE Audit Compliant.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = 'Trial Balance'
    
    # Title
    style_title_row(ws, 1, f'Trial Balance (As at {as_of_date})', 5)
    if company_name:
        ws.cell(row=2, column=1, value=company_name)
    
    # Headers
    headers = ['Account Code', 'Account Name', 'Type', 'Debit (AED)', 'Credit (AED)']
    header_row = 4 if company_name else 3
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=header_row, column=col, value=header)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
        cell.font = Font(bold=True, color='FFFFFF')
        cell.alignment = Alignment(horizontal='center')
    
    # Data
    row = header_row + 1
    total_debit = Decimal('0.00')
    total_credit = Decimal('0.00')
    
    for acc in accounts:
        ws.cell(row=row, column=1, value=acc.get('code', ''))
        ws.cell(row=row, column=2, value=acc.get('name', ''))
        ws.cell(row=row, column=3, value=acc.get('account_type', ''))
        
        debit = acc.get('debit', Decimal('0.00'))
        credit = acc.get('credit', Decimal('0.00'))
        
        ws.cell(row=row, column=4, value=format_currency(debit) if debit else '')
        ws.cell(row=row, column=5, value=format_currency(credit) if credit else '')
        
        total_debit += debit or Decimal('0.00')
        total_credit += credit or Decimal('0.00')
        
        # Highlight abnormal balances
        if acc.get('abnormal', False):
            for col in range(1, 6):
                ws.cell(row=row, column=col).fill = PatternFill(
                    start_color='FFF3CD', end_color='FFF3CD', fill_type='solid'
                )
        
        row += 1
    
    # Totals
    ws.cell(row=row, column=1, value='TOTAL')
    ws.cell(row=row, column=1).font = Font(bold=True)
    ws.cell(row=row, column=4, value=format_currency(total_debit))
    ws.cell(row=row, column=4).font = Font(bold=True)
    ws.cell(row=row, column=5, value=format_currency(total_credit))
    ws.cell(row=row, column=5).font = Font(bold=True)
    
    # Add border to totals row
    for col in range(1, 6):
        ws.cell(row=row, column=col).border = Border(top=Side(style='double'))
    
    # Balance check
    row += 2
    is_balanced = total_debit == total_credit
    if is_balanced:
        ws.cell(row=row, column=1, value='✓ Trial Balance is BALANCED')
        ws.cell(row=row, column=1).font = Font(bold=True, color='008000')
    else:
        ws.cell(row=row, column=1, value=f'✗ UNBALANCED - Difference: {format_currency(total_debit - total_credit)}')
        ws.cell(row=row, column=1).font = Font(bold=True, color='FF0000')
    
    auto_width_columns(ws)
    
    response = create_excel_response(f'trial_balance_as_at_{as_of_date}.xlsx')
    wb.save(response)
    return response


# ============ TRIAL BALANCE WITH MOVEMENTS EXPORT ============

def export_trial_balance_with_movements(accounts, start_date, end_date, totals=None, company_name=''):
    """
    Export Trial Balance with Movements to Excel.
    Shows Opening Balance, Period Movement, and Closing Balance.
    IFRS & UAE Audit Compliant.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = 'TB with Movements'
    
    # Title
    style_title_row(ws, 1, f'Trial Balance with Movements', 9)
    ws.cell(row=2, column=1, value=f'Period: {start_date} to {end_date}')
    if company_name:
        ws.cell(row=3, column=1, value=company_name)
    
    # Headers Row 1 - Groups
    ws.cell(row=5, column=1, value='Account Code')
    ws.cell(row=5, column=2, value='Account Name')
    ws.cell(row=5, column=3, value='Type')
    ws.merge_cells('D5:E5')
    ws.cell(row=5, column=4, value='Opening Balance')
    ws.cell(row=5, column=4).alignment = Alignment(horizontal='center')
    ws.merge_cells('F5:G5')
    ws.cell(row=5, column=6, value='Period Movement')
    ws.cell(row=5, column=6).alignment = Alignment(horizontal='center')
    ws.merge_cells('H5:I5')
    ws.cell(row=5, column=8, value='Closing Balance')
    ws.cell(row=5, column=8).alignment = Alignment(horizontal='center')
    
    # Headers Row 2 - Columns
    headers = ['Account Code', 'Account Name', 'Type', 
               'Opening Dr', 'Opening Cr', 
               'Period Dr', 'Period Cr', 
               'Closing Dr', 'Closing Cr']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=6, column=col, value=header)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color='D9E1F2', end_color='D9E1F2', fill_type='solid')
        cell.border = Border(
            bottom=Side(style='thin'),
            top=Side(style='thin')
        )
    
    # Data
    row = 7
    for acc in accounts:
        ws.cell(row=row, column=1, value=acc.get('code', ''))
        ws.cell(row=row, column=2, value=acc.get('name', ''))
        ws.cell(row=row, column=3, value=acc.get('account_type', ''))
        
        # Opening
        ws.cell(row=row, column=4, value=format_currency(acc.get('opening_debit', Decimal('0.00'))))
        ws.cell(row=row, column=5, value=format_currency(acc.get('opening_credit', Decimal('0.00'))))
        
        # Period
        ws.cell(row=row, column=6, value=format_currency(acc.get('period_debit', Decimal('0.00'))))
        ws.cell(row=row, column=7, value=format_currency(acc.get('period_credit', Decimal('0.00'))))
        
        # Closing
        ws.cell(row=row, column=8, value=format_currency(acc.get('closing_debit', Decimal('0.00'))))
        ws.cell(row=row, column=9, value=format_currency(acc.get('closing_credit', Decimal('0.00'))))
        
        # Highlight abnormal balances
        if acc.get('abnormal', False):
            for col in range(1, 10):
                ws.cell(row=row, column=col).fill = PatternFill(
                    start_color='FFF3CD', end_color='FFF3CD', fill_type='solid'
                )
        
        row += 1
    
    # Totals
    if totals:
        ws.cell(row=row, column=1, value='TOTAL')
        ws.cell(row=row, column=1).font = Font(bold=True)
        
        ws.cell(row=row, column=4, value=format_currency(totals.get('total_opening_debit', Decimal('0.00'))))
        ws.cell(row=row, column=4).font = Font(bold=True)
        ws.cell(row=row, column=5, value=format_currency(totals.get('total_opening_credit', Decimal('0.00'))))
        ws.cell(row=row, column=5).font = Font(bold=True)
        
        ws.cell(row=row, column=6, value=format_currency(totals.get('total_period_debit', Decimal('0.00'))))
        ws.cell(row=row, column=6).font = Font(bold=True)
        ws.cell(row=row, column=7, value=format_currency(totals.get('total_period_credit', Decimal('0.00'))))
        ws.cell(row=row, column=7).font = Font(bold=True)
        
        ws.cell(row=row, column=8, value=format_currency(totals.get('total_closing_debit', Decimal('0.00'))))
        ws.cell(row=row, column=8).font = Font(bold=True)
        ws.cell(row=row, column=9, value=format_currency(totals.get('total_closing_credit', Decimal('0.00'))))
        ws.cell(row=row, column=9).font = Font(bold=True)
        
        # Add border to totals row
        for col in range(1, 10):
            ws.cell(row=row, column=col).border = Border(top=Side(style='double'))
    
    auto_width_columns(ws)
    
    response = create_excel_response(f'trial_balance_movements_{start_date}_to_{end_date}.xlsx')
    wb.save(response)
    return response


# ============ PROFIT & LOSS EXPORT ============

def export_profit_loss(revenue_accounts, expense_accounts, start_date, end_date, company_name=''):
    """Export Profit & Loss to Excel."""
    wb = Workbook()
    ws = wb.active
    ws.title = 'Profit & Loss'
    
    # Title
    style_title_row(ws, 1, f'Profit & Loss Statement', 3)
    ws.cell(row=2, column=1, value=f'Period: {start_date} to {end_date}')
    if company_name:
        ws.cell(row=3, column=1, value=company_name)
    
    row = 5
    
    # Revenue Section
    ws.cell(row=row, column=1, value='REVENUE')
    ws.cell(row=row, column=1).font = Font(bold=True)
    row += 1
    
    total_revenue = Decimal('0.00')
    for acc in revenue_accounts:
        ws.cell(row=row, column=1, value=acc.get('code', ''))
        ws.cell(row=row, column=2, value=acc.get('name', ''))
        amount = acc.get('balance', acc.get('amount', Decimal('0.00')))
        ws.cell(row=row, column=3, value=format_currency(abs(amount) if amount else 0))
        total_revenue += abs(amount) if amount else Decimal('0.00')
        row += 1
    
    ws.cell(row=row, column=2, value='Total Revenue')
    ws.cell(row=row, column=2).font = Font(bold=True)
    ws.cell(row=row, column=3, value=format_currency(total_revenue))
    ws.cell(row=row, column=3).font = Font(bold=True)
    row += 2
    
    # Expense Section
    ws.cell(row=row, column=1, value='EXPENSES')
    ws.cell(row=row, column=1).font = Font(bold=True)
    row += 1
    
    total_expenses = Decimal('0.00')
    for acc in expense_accounts:
        ws.cell(row=row, column=1, value=acc.get('code', ''))
        ws.cell(row=row, column=2, value=acc.get('name', ''))
        amount = acc.get('balance', acc.get('amount', Decimal('0.00')))
        ws.cell(row=row, column=3, value=format_currency(abs(amount) if amount else 0))
        total_expenses += abs(amount) if amount else Decimal('0.00')
        row += 1
    
    ws.cell(row=row, column=2, value='Total Expenses')
    ws.cell(row=row, column=2).font = Font(bold=True)
    ws.cell(row=row, column=3, value=format_currency(total_expenses))
    ws.cell(row=row, column=3).font = Font(bold=True)
    row += 2
    
    # Net Profit/Loss
    net = total_revenue - total_expenses
    ws.cell(row=row, column=2, value='NET PROFIT / (LOSS)')
    ws.cell(row=row, column=2).font = Font(bold=True, size=12)
    ws.cell(row=row, column=3, value=format_currency(net))
    ws.cell(row=row, column=3).font = Font(bold=True, size=12)
    
    auto_width_columns(ws)
    
    response = create_excel_response(f'profit_loss_{start_date}_to_{end_date}.xlsx')
    wb.save(response)
    return response


# ============ BALANCE SHEET EXPORT ============

def export_balance_sheet(assets, liabilities, equity, as_of_date, company_name=''):
    """Export Balance Sheet to Excel."""
    wb = Workbook()
    ws = wb.active
    ws.title = 'Balance Sheet'
    
    # Title
    style_title_row(ws, 1, f'Balance Sheet as of {as_of_date}', 3)
    if company_name:
        ws.cell(row=2, column=1, value=company_name)
    
    row = 4
    
    # Assets
    ws.cell(row=row, column=1, value='ASSETS')
    ws.cell(row=row, column=1).font = Font(bold=True)
    row += 1
    
    total_assets = Decimal('0.00')
    for acc in assets:
        ws.cell(row=row, column=1, value=acc.get('code', ''))
        ws.cell(row=row, column=2, value=acc.get('name', ''))
        amount = acc.get('balance', Decimal('0.00'))
        ws.cell(row=row, column=3, value=format_currency(amount))
        total_assets += amount or Decimal('0.00')
        row += 1
    
    ws.cell(row=row, column=2, value='Total Assets')
    ws.cell(row=row, column=2).font = Font(bold=True)
    ws.cell(row=row, column=3, value=format_currency(total_assets))
    ws.cell(row=row, column=3).font = Font(bold=True)
    row += 2
    
    # Liabilities
    ws.cell(row=row, column=1, value='LIABILITIES')
    ws.cell(row=row, column=1).font = Font(bold=True)
    row += 1
    
    total_liabilities = Decimal('0.00')
    for acc in liabilities:
        ws.cell(row=row, column=1, value=acc.get('code', ''))
        ws.cell(row=row, column=2, value=acc.get('name', ''))
        amount = acc.get('balance', Decimal('0.00'))
        ws.cell(row=row, column=3, value=format_currency(abs(amount) if amount else 0))
        total_liabilities += abs(amount) if amount else Decimal('0.00')
        row += 1
    
    ws.cell(row=row, column=2, value='Total Liabilities')
    ws.cell(row=row, column=2).font = Font(bold=True)
    ws.cell(row=row, column=3, value=format_currency(total_liabilities))
    ws.cell(row=row, column=3).font = Font(bold=True)
    row += 2
    
    # Equity
    ws.cell(row=row, column=1, value='EQUITY')
    ws.cell(row=row, column=1).font = Font(bold=True)
    row += 1
    
    total_equity = Decimal('0.00')
    for acc in equity:
        ws.cell(row=row, column=1, value=acc.get('code', ''))
        ws.cell(row=row, column=2, value=acc.get('name', ''))
        amount = acc.get('balance', Decimal('0.00'))
        ws.cell(row=row, column=3, value=format_currency(abs(amount) if amount else 0))
        total_equity += abs(amount) if amount else Decimal('0.00')
        row += 1
    
    ws.cell(row=row, column=2, value='Total Equity')
    ws.cell(row=row, column=2).font = Font(bold=True)
    ws.cell(row=row, column=3, value=format_currency(total_equity))
    ws.cell(row=row, column=3).font = Font(bold=True)
    row += 2
    
    # Total L + E
    ws.cell(row=row, column=2, value='Total Liabilities & Equity')
    ws.cell(row=row, column=2).font = Font(bold=True, size=12)
    ws.cell(row=row, column=3, value=format_currency(total_liabilities + total_equity))
    ws.cell(row=row, column=3).font = Font(bold=True, size=12)
    
    auto_width_columns(ws)
    
    response = create_excel_response(f'balance_sheet_{as_of_date}.xlsx')
    wb.save(response)
    return response


# ============ GENERAL LEDGER EXPORT ============

def export_general_ledger(transactions, account_name, start_date, end_date):
    """Export General Ledger to Excel."""
    wb = Workbook()
    ws = wb.active
    ws.title = 'General Ledger'
    
    # Title
    style_title_row(ws, 1, f'General Ledger - {account_name}', 6)
    ws.cell(row=2, column=1, value=f'Period: {start_date} to {end_date}')
    
    # Headers
    headers = ['Date', 'Reference', 'Description', 'Debit', 'Credit', 'Balance']
    for col, header in enumerate(headers, 1):
        ws.cell(row=4, column=col, value=header)
    style_header_row(ws, 4, len(headers))
    
    # Data
    row = 5
    for txn in transactions:
        ws.cell(row=row, column=1, value=txn.get('date', ''))
        ws.cell(row=row, column=2, value=txn.get('reference', ''))
        ws.cell(row=row, column=3, value=txn.get('description', ''))
        ws.cell(row=row, column=4, value=format_currency(txn.get('debit', 0)))
        ws.cell(row=row, column=5, value=format_currency(txn.get('credit', 0)))
        ws.cell(row=row, column=6, value=format_currency(txn.get('balance', 0)))
        row += 1
    
    auto_width_columns(ws)
    
    response = create_excel_response(f'general_ledger_{start_date}_to_{end_date}.xlsx')
    wb.save(response)
    return response


# ============ JOURNAL REGISTER EXPORT ============

def export_journal_register(entries, start_date, end_date):
    """Export Journal Register to Excel."""
    wb = Workbook()
    ws = wb.active
    ws.title = 'Journal Register'
    
    # Title
    style_title_row(ws, 1, f'Journal Register', 8)
    ws.cell(row=2, column=1, value=f'Period: {start_date} to {end_date}')
    
    # Headers
    headers = ['Entry #', 'Date', 'Reference', 'Description', 'Source', 'Debit', 'Credit', 'Status']
    for col, header in enumerate(headers, 1):
        ws.cell(row=4, column=col, value=header)
    style_header_row(ws, 4, len(headers))
    
    # Data
    row = 5
    for entry in entries:
        ws.cell(row=row, column=1, value=entry.entry_number)
        ws.cell(row=row, column=2, value=entry.date.strftime('%Y-%m-%d') if entry.date else '')
        ws.cell(row=row, column=3, value=entry.reference)
        ws.cell(row=row, column=4, value=entry.description)
        ws.cell(row=row, column=5, value=entry.get_source_module_display() if hasattr(entry, 'get_source_module_display') else entry.source_module)
        ws.cell(row=row, column=6, value=format_currency(entry.total_debit))
        ws.cell(row=row, column=7, value=format_currency(entry.total_credit))
        ws.cell(row=row, column=8, value=entry.get_status_display() if hasattr(entry, 'get_status_display') else entry.status)
        row += 1
    
    auto_width_columns(ws)
    
    response = create_excel_response(f'journal_register_{start_date}_to_{end_date}.xlsx')
    wb.save(response)
    return response


# ============ AR AGING EXPORT ============

def export_ar_aging(customers, as_of_date):
    """Export AR Aging to Excel."""
    wb = Workbook()
    ws = wb.active
    ws.title = 'AR Aging'
    
    # Title
    style_title_row(ws, 1, f'Accounts Receivable Aging as of {as_of_date}', 7)
    
    # Headers
    headers = ['Customer', 'Current', '1-30 Days', '31-60 Days', '61-90 Days', 'Over 90 Days', 'Total']
    for col, header in enumerate(headers, 1):
        ws.cell(row=3, column=col, value=header)
    style_header_row(ws, 3, len(headers))
    
    # Data
    row = 4
    totals = {'current': 0, '1_30': 0, '31_60': 0, '61_90': 0, 'over_90': 0, 'total': 0}
    
    for cust in customers:
        ws.cell(row=row, column=1, value=cust.get('name', ''))
        ws.cell(row=row, column=2, value=format_currency(cust.get('current', 0)))
        ws.cell(row=row, column=3, value=format_currency(cust.get('1_30', cust.get('days_1_30', 0))))
        ws.cell(row=row, column=4, value=format_currency(cust.get('31_60', cust.get('days_31_60', 0))))
        ws.cell(row=row, column=5, value=format_currency(cust.get('61_90', cust.get('days_61_90', 0))))
        ws.cell(row=row, column=6, value=format_currency(cust.get('over_90', cust.get('days_over_90', 0))))
        ws.cell(row=row, column=7, value=format_currency(cust.get('total', 0)))
        
        totals['current'] += cust.get('current', 0) or 0
        totals['1_30'] += cust.get('1_30', cust.get('days_1_30', 0)) or 0
        totals['31_60'] += cust.get('31_60', cust.get('days_31_60', 0)) or 0
        totals['61_90'] += cust.get('61_90', cust.get('days_61_90', 0)) or 0
        totals['over_90'] += cust.get('over_90', cust.get('days_over_90', 0)) or 0
        totals['total'] += cust.get('total', 0) or 0
        row += 1
    
    # Totals row
    ws.cell(row=row, column=1, value='TOTAL')
    ws.cell(row=row, column=1).font = Font(bold=True)
    ws.cell(row=row, column=2, value=format_currency(totals['current']))
    ws.cell(row=row, column=3, value=format_currency(totals['1_30']))
    ws.cell(row=row, column=4, value=format_currency(totals['31_60']))
    ws.cell(row=row, column=5, value=format_currency(totals['61_90']))
    ws.cell(row=row, column=6, value=format_currency(totals['over_90']))
    ws.cell(row=row, column=7, value=format_currency(totals['total']))
    for col in range(1, 8):
        ws.cell(row=row, column=col).font = Font(bold=True)
    
    auto_width_columns(ws)
    
    response = create_excel_response(f'ar_aging_{as_of_date}.xlsx')
    wb.save(response)
    return response


# ============ AP AGING EXPORT ============

def export_ap_aging(vendors, as_of_date):
    """Export AP Aging to Excel."""
    wb = Workbook()
    ws = wb.active
    ws.title = 'AP Aging'
    
    # Title
    style_title_row(ws, 1, f'Accounts Payable Aging as of {as_of_date}', 7)
    
    # Headers
    headers = ['Vendor', 'Current', '1-30 Days', '31-60 Days', '61-90 Days', 'Over 90 Days', 'Total']
    for col, header in enumerate(headers, 1):
        ws.cell(row=3, column=col, value=header)
    style_header_row(ws, 3, len(headers))
    
    # Data
    row = 4
    totals = {'current': 0, '1_30': 0, '31_60': 0, '61_90': 0, 'over_90': 0, 'total': 0}
    
    for vendor in vendors:
        ws.cell(row=row, column=1, value=vendor.get('name', ''))
        ws.cell(row=row, column=2, value=format_currency(vendor.get('current', 0)))
        ws.cell(row=row, column=3, value=format_currency(vendor.get('1_30', vendor.get('days_1_30', 0))))
        ws.cell(row=row, column=4, value=format_currency(vendor.get('31_60', vendor.get('days_31_60', 0))))
        ws.cell(row=row, column=5, value=format_currency(vendor.get('61_90', vendor.get('days_61_90', 0))))
        ws.cell(row=row, column=6, value=format_currency(vendor.get('over_90', vendor.get('days_over_90', 0))))
        ws.cell(row=row, column=7, value=format_currency(vendor.get('total', 0)))
        
        totals['current'] += vendor.get('current', 0) or 0
        totals['1_30'] += vendor.get('1_30', vendor.get('days_1_30', 0)) or 0
        totals['31_60'] += vendor.get('31_60', vendor.get('days_31_60', 0)) or 0
        totals['61_90'] += vendor.get('61_90', vendor.get('days_61_90', 0)) or 0
        totals['over_90'] += vendor.get('over_90', vendor.get('days_over_90', 0)) or 0
        totals['total'] += vendor.get('total', 0) or 0
        row += 1
    
    # Totals row
    ws.cell(row=row, column=1, value='TOTAL')
    ws.cell(row=row, column=1).font = Font(bold=True)
    for col in range(2, 8):
        ws.cell(row=row, column=col).font = Font(bold=True)
    ws.cell(row=row, column=2, value=format_currency(totals['current']))
    ws.cell(row=row, column=3, value=format_currency(totals['1_30']))
    ws.cell(row=row, column=4, value=format_currency(totals['31_60']))
    ws.cell(row=row, column=5, value=format_currency(totals['61_90']))
    ws.cell(row=row, column=6, value=format_currency(totals['over_90']))
    ws.cell(row=row, column=7, value=format_currency(totals['total']))
    
    auto_width_columns(ws)
    
    response = create_excel_response(f'ap_aging_{as_of_date}.xlsx')
    wb.save(response)
    return response


# ============ VAT REPORT EXPORT ============

def export_vat_report(data, start_date, end_date):
    """Export VAT Report to Excel."""
    wb = Workbook()
    ws = wb.active
    ws.title = 'VAT Report'
    
    # Title
    style_title_row(ws, 1, f'VAT Report', 4)
    ws.cell(row=2, column=1, value=f'Period: {start_date} to {end_date}')
    
    row = 4
    
    # Output VAT
    ws.cell(row=row, column=1, value='OUTPUT VAT (Sales)')
    ws.cell(row=row, column=1).font = Font(bold=True)
    row += 1
    
    ws.cell(row=row, column=1, value='Standard Rated Sales')
    ws.cell(row=row, column=2, value=format_currency(data.get('standard_sales', 0)))
    ws.cell(row=row, column=3, value=format_currency(data.get('output_vat', 0)))
    row += 1
    
    ws.cell(row=row, column=1, value='Zero Rated Sales')
    ws.cell(row=row, column=2, value=format_currency(data.get('zero_rated_sales', 0)))
    ws.cell(row=row, column=3, value=format_currency(0))
    row += 1
    
    ws.cell(row=row, column=1, value='Exempt Sales')
    ws.cell(row=row, column=2, value=format_currency(data.get('exempt_sales', 0)))
    ws.cell(row=row, column=3, value=format_currency(0))
    row += 2
    
    # Input VAT
    ws.cell(row=row, column=1, value='INPUT VAT (Purchases)')
    ws.cell(row=row, column=1).font = Font(bold=True)
    row += 1
    
    ws.cell(row=row, column=1, value='Standard Rated Purchases')
    ws.cell(row=row, column=2, value=format_currency(data.get('standard_purchases', 0)))
    ws.cell(row=row, column=3, value=format_currency(data.get('input_vat', 0)))
    row += 2
    
    # Net VAT
    ws.cell(row=row, column=1, value='NET VAT PAYABLE / (REFUNDABLE)')
    ws.cell(row=row, column=1).font = Font(bold=True, size=12)
    net_vat = (data.get('output_vat', 0) or 0) - (data.get('input_vat', 0) or 0)
    ws.cell(row=row, column=3, value=format_currency(net_vat))
    ws.cell(row=row, column=3).font = Font(bold=True, size=12)
    
    auto_width_columns(ws)
    
    response = create_excel_response(f'vat_report_{start_date}_to_{end_date}.xlsx')
    wb.save(response)
    return response


# ============ BUDGET VS ACTUAL EXPORT ============

def export_budget_vs_actual(data, budget_name, period):
    """Export Budget vs Actual to Excel."""
    wb = Workbook()
    ws = wb.active
    ws.title = 'Budget vs Actual'
    
    # Title
    style_title_row(ws, 1, f'Budget vs Actual Report', 5)
    ws.cell(row=2, column=1, value=f'Budget: {budget_name}')
    ws.cell(row=3, column=1, value=f'Period: {period}')
    
    # Headers
    headers = ['Account', 'Budget', 'Actual', 'Variance', 'Variance %']
    for col, header in enumerate(headers, 1):
        ws.cell(row=5, column=col, value=header)
    style_header_row(ws, 5, len(headers))
    
    # Data
    row = 6
    for item in data:
        ws.cell(row=row, column=1, value=item.get('account', ''))
        ws.cell(row=row, column=2, value=format_currency(item.get('budget', 0)))
        ws.cell(row=row, column=3, value=format_currency(item.get('actual', 0)))
        ws.cell(row=row, column=4, value=format_currency(item.get('variance', 0)))
        ws.cell(row=row, column=5, value=f"{item.get('variance_pct', 0):.1f}%")
        row += 1
    
    auto_width_columns(ws)
    
    response = create_excel_response(f'budget_vs_actual_{period}.xlsx')
    wb.save(response)
    return response


# ============ BANK LEDGER EXPORT ============

def export_bank_ledger(transactions, bank_name, start_date, end_date):
    """Export Bank Ledger to Excel."""
    wb = Workbook()
    ws = wb.active
    ws.title = 'Bank Ledger'
    
    # Title
    style_title_row(ws, 1, f'Bank Ledger - {bank_name}', 6)
    ws.cell(row=2, column=1, value=f'Period: {start_date} to {end_date}')
    
    # Headers
    headers = ['Date', 'Reference', 'Description', 'Debit', 'Credit', 'Balance']
    for col, header in enumerate(headers, 1):
        ws.cell(row=4, column=col, value=header)
    style_header_row(ws, 4, len(headers))
    
    # Data
    row = 5
    for txn in transactions:
        ws.cell(row=row, column=1, value=txn.get('date', ''))
        ws.cell(row=row, column=2, value=txn.get('reference', ''))
        ws.cell(row=row, column=3, value=txn.get('description', ''))
        ws.cell(row=row, column=4, value=format_currency(txn.get('debit', 0)))
        ws.cell(row=row, column=5, value=format_currency(txn.get('credit', 0)))
        ws.cell(row=row, column=6, value=format_currency(txn.get('balance', 0)))
        row += 1
    
    auto_width_columns(ws)
    
    response = create_excel_response(f'bank_ledger_{start_date}_to_{end_date}.xlsx')
    wb.save(response)
    return response


# ============ CASH FLOW EXPORT ============

def export_cash_flow(operating, investing, financing, start_date, end_date):
    """Export Cash Flow Statement to Excel."""
    wb = Workbook()
    ws = wb.active
    ws.title = 'Cash Flow'
    
    # Title
    style_title_row(ws, 1, f'Cash Flow Statement', 2)
    ws.cell(row=2, column=1, value=f'Period: {start_date} to {end_date}')
    
    row = 4
    
    # Operating Activities
    ws.cell(row=row, column=1, value='OPERATING ACTIVITIES')
    ws.cell(row=row, column=1).font = Font(bold=True)
    row += 1
    
    total_operating = Decimal('0.00')
    for item in operating:
        ws.cell(row=row, column=1, value=item.get('description', ''))
        amount = item.get('amount', 0)
        ws.cell(row=row, column=2, value=format_currency(amount))
        total_operating += Decimal(str(amount)) if amount else Decimal('0.00')
        row += 1
    
    ws.cell(row=row, column=1, value='Net Cash from Operating')
    ws.cell(row=row, column=1).font = Font(bold=True)
    ws.cell(row=row, column=2, value=format_currency(total_operating))
    ws.cell(row=row, column=2).font = Font(bold=True)
    row += 2
    
    # Investing Activities
    ws.cell(row=row, column=1, value='INVESTING ACTIVITIES')
    ws.cell(row=row, column=1).font = Font(bold=True)
    row += 1
    
    total_investing = Decimal('0.00')
    for item in investing:
        ws.cell(row=row, column=1, value=item.get('description', ''))
        amount = item.get('amount', 0)
        ws.cell(row=row, column=2, value=format_currency(amount))
        total_investing += Decimal(str(amount)) if amount else Decimal('0.00')
        row += 1
    
    ws.cell(row=row, column=1, value='Net Cash from Investing')
    ws.cell(row=row, column=1).font = Font(bold=True)
    ws.cell(row=row, column=2, value=format_currency(total_investing))
    ws.cell(row=row, column=2).font = Font(bold=True)
    row += 2
    
    # Financing Activities
    ws.cell(row=row, column=1, value='FINANCING ACTIVITIES')
    ws.cell(row=row, column=1).font = Font(bold=True)
    row += 1
    
    total_financing = Decimal('0.00')
    for item in financing:
        ws.cell(row=row, column=1, value=item.get('description', ''))
        amount = item.get('amount', 0)
        ws.cell(row=row, column=2, value=format_currency(amount))
        total_financing += Decimal(str(amount)) if amount else Decimal('0.00')
        row += 1
    
    ws.cell(row=row, column=1, value='Net Cash from Financing')
    ws.cell(row=row, column=1).font = Font(bold=True)
    ws.cell(row=row, column=2, value=format_currency(total_financing))
    ws.cell(row=row, column=2).font = Font(bold=True)
    row += 2
    
    # Net Change
    net_change = total_operating + total_investing + total_financing
    ws.cell(row=row, column=1, value='NET CHANGE IN CASH')
    ws.cell(row=row, column=1).font = Font(bold=True, size=12)
    ws.cell(row=row, column=2, value=format_currency(net_change))
    ws.cell(row=row, column=2).font = Font(bold=True, size=12)
    
    auto_width_columns(ws)
    
    response = create_excel_response(f'cash_flow_{start_date}_to_{end_date}.xlsx')
    wb.save(response)
    return response


# ============ CORPORATE TAX EXPORT ============

def export_corporate_tax(data):
    """Export Corporate Tax Report to Excel."""
    wb = Workbook()
    ws = wb.active
    ws.title = 'Corporate Tax'
    
    # Title
    style_title_row(ws, 1, f'UAE Corporate Tax Computation', 3)
    ws.cell(row=2, column=1, value=f'Fiscal Year: {data.get("fiscal_year", "")}')
    ws.cell(row=3, column=1, value=f'Period: {data.get("start_date", "")} to {data.get("end_date", "")}')
    
    row = 5
    
    # Revenue & Expenses
    ws.cell(row=row, column=1, value='INCOME STATEMENT SUMMARY')
    ws.cell(row=row, column=1).font = Font(bold=True)
    row += 1
    
    ws.cell(row=row, column=1, value='Total Revenue')
    ws.cell(row=row, column=2, value=format_currency(data.get('revenue', 0)))
    row += 1
    
    ws.cell(row=row, column=1, value='Total Expenses')
    ws.cell(row=row, column=2, value=format_currency(data.get('expenses', 0)))
    row += 1
    
    ws.cell(row=row, column=1, value='Accounting Profit')
    ws.cell(row=row, column=1).font = Font(bold=True)
    ws.cell(row=row, column=2, value=format_currency(data.get('accounting_profit', 0)))
    ws.cell(row=row, column=2).font = Font(bold=True)
    row += 2
    
    # Tax Computation
    ws.cell(row=row, column=1, value='TAX COMPUTATION')
    ws.cell(row=row, column=1).font = Font(bold=True)
    row += 1
    
    ws.cell(row=row, column=1, value='Tax-Free Threshold')
    ws.cell(row=row, column=2, value=format_currency(data.get('tax_threshold', 375000)))
    row += 1
    
    ws.cell(row=row, column=1, value='Tax Rate')
    ws.cell(row=row, column=2, value=f'{data.get("tax_rate", 9)}%')
    row += 1
    
    ws.cell(row=row, column=1, value='Taxable Amount (Profit - Threshold)')
    ws.cell(row=row, column=2, value=format_currency(data.get('taxable_amount', 0)))
    row += 1
    
    ws.cell(row=row, column=1, value='TAX PAYABLE')
    ws.cell(row=row, column=1).font = Font(bold=True, size=12)
    ws.cell(row=row, column=2, value=format_currency(data.get('tax_payable', 0)))
    ws.cell(row=row, column=2).font = Font(bold=True, size=12)
    row += 2
    
    # If there's a saved computation with adjustments
    computation = data.get('computation')
    if computation:
        ws.cell(row=row, column=1, value='SAVED COMPUTATION DETAILS')
        ws.cell(row=row, column=1).font = Font(bold=True)
        row += 1
        
        ws.cell(row=row, column=1, value='Non-Deductible Expenses')
        ws.cell(row=row, column=2, value=format_currency(computation.non_deductible_expenses))
        row += 1
        
        ws.cell(row=row, column=1, value='Exempt Income')
        ws.cell(row=row, column=2, value=format_currency(computation.exempt_income))
        row += 1
        
        ws.cell(row=row, column=1, value='Other Adjustments')
        ws.cell(row=row, column=2, value=format_currency(computation.other_adjustments))
        row += 1
        
        ws.cell(row=row, column=1, value='Adjusted Taxable Income')
        ws.cell(row=row, column=2, value=format_currency(computation.taxable_income))
        row += 1
        
        ws.cell(row=row, column=1, value='Final Tax Payable')
        ws.cell(row=row, column=1).font = Font(bold=True, size=12)
        ws.cell(row=row, column=2, value=format_currency(computation.tax_payable))
        ws.cell(row=row, column=2).font = Font(bold=True, size=12)
        row += 1
        
        ws.cell(row=row, column=1, value='Status')
        ws.cell(row=row, column=2, value=computation.get_status_display() if hasattr(computation, 'get_status_display') else computation.status)
    
    auto_width_columns(ws)
    
    fiscal_year = data.get('fiscal_year', 'unknown').replace(' ', '_')
    response = create_excel_response(f'corporate_tax_{fiscal_year}.xlsx')
    wb.save(response)
    return response


# ============ VAT AUDIT REPORT EXPORT ============

def export_vat_audit(start_date, end_date, transactions, box_totals):
    """Export VAT Audit Report to Excel."""
    wb = Workbook()
    ws = wb.active
    ws.title = 'VAT Audit Details'
    
    # Title
    style_title_row(ws, 1, f'UAE VAT Audit Report', 8)
    ws.cell(row=2, column=1, value=f'Period: {start_date} to {end_date}')
    ws.cell(row=3, column=1, value=f'Generated: {date.today().isoformat()}')
    
    # Box Summary
    row = 5
    ws.cell(row=row, column=1, value='VAT BOX SUMMARY')
    ws.cell(row=row, column=1).font = Font(bold=True, size=12)
    row += 1
    
    # Header for summary
    summary_headers = ['Box', 'Description', 'Transactions', 'Net Amount']
    for col, header in enumerate(summary_headers, 1):
        ws.cell(row=row, column=col, value=header)
        ws.cell(row=row, column=col).font = Font(bold=True)
        ws.cell(row=row, column=col).fill = PatternFill(start_color='DDDDDD', fill_type='solid')
    row += 1
    
    box_descriptions = {
        'box1a': 'Standard Rated Supplies (Emirates)',
        'box3': 'Zero-rated Supplies',
        'box4': 'Exempt Supplies',
        'box6': 'Standard Rated Expenses',
        'box9': 'Output VAT Due',
        'box10': 'Input VAT Recoverable',
    }
    
    for box_key, description in box_descriptions.items():
        box_data = box_totals.get(box_key, {'count': 0, 'net': 0})
        ws.cell(row=row, column=1, value=box_key.upper())
        ws.cell(row=row, column=2, value=description)
        ws.cell(row=row, column=3, value=box_data.get('count', 0))
        ws.cell(row=row, column=4, value=format_currency(box_data.get('net', 0)))
        row += 1
    
    row += 2
    
    # Transaction Details
    ws.cell(row=row, column=1, value='TRANSACTION DETAILS')
    ws.cell(row=row, column=1).font = Font(bold=True, size=12)
    row += 1
    
    # Headers
    headers = ['Date', 'Entry #', 'Reference', 'Description', 'Account', 'Debit', 'Credit', 'VAT Box']
    for col, header in enumerate(headers, 1):
        ws.cell(row=row, column=col, value=header)
        ws.cell(row=row, column=col).font = Font(bold=True)
        ws.cell(row=row, column=col).fill = PatternFill(start_color='DDDDDD', fill_type='solid')
    row += 1
    
    # Data rows
    for txn in transactions:
        ws.cell(row=row, column=1, value=txn['date'].strftime('%d/%m/%Y') if hasattr(txn['date'], 'strftime') else str(txn['date']))
        ws.cell(row=row, column=2, value=txn.get('entry_number', ''))
        ws.cell(row=row, column=3, value=txn.get('reference', '') or '')
        ws.cell(row=row, column=4, value=(txn.get('description', '') or '')[:50])
        ws.cell(row=row, column=5, value=txn['account'].code if hasattr(txn.get('account'), 'code') else str(txn.get('account', '')))
        ws.cell(row=row, column=6, value=format_currency(txn.get('debit', 0)) if txn.get('debit', 0) > 0 else '')
        ws.cell(row=row, column=7, value=format_currency(txn.get('credit', 0)) if txn.get('credit', 0) > 0 else '')
        ws.cell(row=row, column=8, value=txn.get('vat_box', ''))
        row += 1
    
    auto_width_columns(ws)
    
    response = create_excel_response(f'vat_audit_{start_date}_to_{end_date}.xlsx')
    wb.save(response)
    return response


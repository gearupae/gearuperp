# Gearup ERP - Finance Module Technical Documentation

**Document Type:** System Documentation (Based on Actual Implementation)  
**Version:** 1.0  
**Date:** January 2026  
**Compliance:** UAE VAT Law (Federal Decree-Law No. 8 of 2017), UAE Corporate Tax Law (Federal Decree-Law No. 47 of 2022), IFRS

---

## Table of Contents

1. [Overview](#1-overview)
2. [Core Accounting Architecture](#2-core-accounting-architecture)
3. [Sales Module](#3-sales-module)
4. [Purchase Module](#4-purchase-module)
5. [Payroll Module](#5-payroll-module)
6. [Fixed Assets Module](#6-fixed-assets-module)
7. [Inventory Module](#7-inventory-module)
8. [Projects Module](#8-projects-module)
9. [Property Management Module](#9-property-management-module)
10. [Banking Module](#10-banking-module)
11. [Journal Entries](#11-journal-entries)
12. [Opening Balances](#12-opening-balances)
13. [VAT & Corporate Tax](#13-vat--corporate-tax)
14. [Report Derivations](#14-report-derivations)

---

## 1. Overview

### 1.1 Source of Truth
The Finance module uses **double-entry accounting** with the `JournalEntry` and `JournalEntryLine` models as the **single source of truth**. All financial transactions from operational modules (Sales, Purchase, Payroll, etc.) create journal entries that update the General Ledger.

### 1.2 Key Models

| Model | Table | Purpose |
|-------|-------|---------|
| `Account` | `finance_account` | Chart of Accounts |
| `JournalEntry` | `finance_journalentry` | Header for journal entries |
| `JournalEntryLine` | `finance_journalentryline` | Debit/Credit lines |
| `FiscalYear` | `finance_fiscalyear` | Fiscal year management |
| `AccountingPeriod` | `finance_accountingperiod` | Monthly period controls |
| `Payment` | `finance_payment` | Payment records |
| `BankAccount` | `finance_bankaccount` | Bank account master |
| `BankStatement` | `finance_bankstatement` | Bank reconciliation |
| `AccountMapping` | `finance_accountmapping` | Account determination rules |

### 1.3 Account Types (AccountType Enum)
```python
ASSET = 'asset'      # Debit increases
LIABILITY = 'liability'  # Credit increases
EQUITY = 'equity'    # Credit increases
INCOME = 'income'    # Credit increases
EXPENSE = 'expense'  # Debit increases
```

### 1.4 Account Determination
The system uses `AccountMapping` model for SAP/Oracle-style account determination:
- Transaction types map to debit/credit accounts
- Modules retrieve accounts via `AccountMapping.get_account_or_default(transaction_type, fallback_code)`
- Fallback to hardcoded account codes if mapping not found

---

## 2. Core Accounting Architecture

### 2.1 Journal Entry Model

**File:** `apps/finance/models.py` (Lines 237-510)

```python
class JournalEntry(BaseModel):
    entry_number = CharField(unique=True, editable=False)  # Auto-generated
    date = DateField()
    reference = CharField(max_length=200)  # Source document reference
    description = TextField()
    status = CharField(choices=['draft', 'posted', 'reversed'])
    entry_type = CharField(choices=[
        'standard', 'opening', 'adjustment', 'adjusting', 'reversal', 'closing'
    ])
    source_module = CharField(choices=[
        'manual', 'sales', 'purchase', 'payment', 'bank_transfer',
        'expense_claim', 'payroll', 'inventory', 'fixed_asset',
        'project', 'pdc', 'property', 'vat', 'corporate_tax',
        'opening_balance', 'year_end', 'reversal', 'adjustment'
    ])
    source_id = PositiveIntegerField(null=True)  # ID of source document
    is_system_generated = BooleanField(default=False)
    is_locked = BooleanField(default=False)
    fiscal_year = ForeignKey(FiscalYear)
    period = ForeignKey(AccountingPeriod)
    total_debit = DecimalField()
    total_credit = DecimalField()
    reversal_of = ForeignKey('self', null=True)  # For reversal entries
```

### 2.2 Journal Entry Line Model

**File:** `apps/finance/models.py` (Lines 525-600)

```python
class JournalEntryLine(models.Model):
    journal_entry = ForeignKey(JournalEntry)
    account = ForeignKey(Account)
    description = CharField()
    debit = DecimalField(default=0.00)
    credit = DecimalField(default=0.00)
    line_number = PositiveIntegerField()
```

### 2.3 Posting Logic

**Method:** `JournalEntry.post(user)` (Lines 486-510)

1. Validates entry is balanced (`total_debit == total_credit`)
2. Validates at least 2 lines exist
3. Validates period is not locked
4. Validates fiscal year is not closed
5. Validates all accounts are leaf accounts
6. Updates account balances:
   - For debit-increases accounts (Asset, Expense): `balance += debit - credit`
   - For credit-increases accounts (Liability, Equity, Income): `balance += credit - debit`
7. Sets `status = 'posted'`
8. Records `posted_date` and `posted_by`

### 2.4 Edit/Delete Rules (Immutability)

**Property:** `JournalEntry.is_editable` (Lines 365-387)

| Condition | Editable | Deletable | Reversible |
|-----------|----------|-----------|------------|
| Status = Draft, Manual | ✅ | ✅ | ❌ |
| Status = Posted | ❌ | ❌ | ✅ |
| Status = Reversed | ❌ | ❌ | ❌ |
| System-generated | ❌ | ❌ | ✅ |
| Period locked | ❌ | ❌ | ❌ |
| Fiscal year closed | ❌ | ❌ | ❌ |
| is_locked = True | ❌ | ❌ | ❌ |

---

## 3. Sales Module

### 3.1 Sales Invoice

**File:** `apps/sales/models.py` (Lines 105-287)

**Model:** `Invoice`

| Field | Type | Description |
|-------|------|-------------|
| invoice_number | CharField | Auto-generated (INV-YYYY-NNNN) |
| customer | ForeignKey | Link to CRM Customer |
| invoice_date | DateField | Invoice date |
| due_date | DateField | Payment due date |
| status | CharField | draft, posted, sent, paid, partial, overdue, cancelled |
| subtotal | DecimalField | Sum of line items (excl. VAT) |
| vat_amount | DecimalField | Total VAT |
| total_amount | DecimalField | subtotal + vat_amount |
| paid_amount | DecimalField | Amount received |
| journal_entry | ForeignKey | Link to posted journal |

---

#### 3.1.1 Invoice Posting

**Method:** `Invoice.post_to_accounting(user)` (Lines 177-287)

**Trigger Event:** User clicks "Post" on draft invoice

**USER ACTION:**
1. User creates invoice with items
2. User clicks "Post Invoice" button

**SYSTEM EVENT:**
1. Validates `status == 'draft'`
2. Validates `total_amount > 0`
3. Retrieves accounts from AccountMapping:
   - `sales_invoice_receivable` → AR Account (fallback: code '1200')
   - `sales_invoice_revenue` → Sales Account (fallback: code '4000')
   - `sales_invoice_vat` → VAT Payable (fallback: code '2100')

**JOURNAL ENTRY CREATED:** YES

| Line | Account | Debit | Credit | Description |
|------|---------|-------|--------|-------------|
| 1 | Accounts Receivable | total_amount | 0 | AR - {customer_name} |
| 2 | Sales Revenue | 0 | subtotal | Sales - {invoice_number} |
| 3 | VAT Payable | 0 | vat_amount | Output VAT - {invoice_number} |

**Note:** If VAT account not found but `vat_amount > 0`, VAT is added to Sales Revenue credit.

**STATUS-BASED BEHAVIOR:**
- Draft → No ledger impact
- Posted → Journal created and posted, AR increased
- Paid → Separate payment journal clears AR
- Cancelled → Behavior not found in current implementation

**VAT TREATMENT:**
- VAT calculated per line item using `vat_rate` (default 5%)
- Supports VAT-inclusive pricing via `is_vat_inclusive` flag
- VAT-inclusive formula: `Net = Gross / (1 + VAT_Rate/100)`

**REPORT IMPACT:**
- Trial Balance: AR increased (debit), Sales & VAT increased (credit)
- General Ledger: Entries visible under AR, Sales, VAT accounts
- VAT Report: `output_vat` increased
- P&L: Sales Revenue recognized
- Balance Sheet: AR as current asset

**AUDIT LOG:**
- Logged via `AuditLog` model on post action
- Records: user, timestamp, action='post', entity_type='Invoice'

---

#### 3.1.2 Invoice Item VAT Calculation

**File:** `apps/sales/models.py` (Lines 316-332)

**Method:** `InvoiceItem.save()`

```python
gross = quantity * unit_price

if is_vat_inclusive and vat_rate > 0:
    # VAT-inclusive: Back-calculate
    divisor = 1 + (vat_rate / 100)
    total = (gross / divisor).quantize(Decimal('0.01'))
    vat_amount = (gross - total).quantize(Decimal('0.01'))
else:
    # VAT-exclusive: Standard calculation
    total = gross
    vat_amount = (total * (vat_rate / 100)).quantize(Decimal('0.01'))
```

---

### 3.2 Sales Credit Note

**File:** `apps/sales/models.py` (Lines 335-517)

**Model:** `SalesCreditNote`

**Trigger Event:** User creates credit note against posted invoice

**JOURNAL ENTRY CREATED:** YES (via `post_to_accounting` method)

| Line | Account | Debit | Credit | Description |
|------|---------|-------|--------|-------------|
| 1 | Sales Returns | subtotal | 0 | Credit Note - {credit_note_number} |
| 2 | VAT Payable | vat_amount | 0 | Reverse Output VAT |
| 3 | Accounts Receivable | 0 | total_amount | Reduce AR - {customer_name} |

**Note:** This reverses the original invoice posting effect.

---

### 3.3 Customer Payment (Payment Received)

**File:** `apps/finance/models.py` (Lines 949-1038)

**Model:** `Payment` (payment_type = 'received')

**Trigger Event:** User records payment against invoice

**JOURNAL ENTRY CREATED:** YES (created in views, not in model method)

| Line | Account | Debit | Credit | Description |
|------|---------|-------|--------|-------------|
| 1 | Bank/Cash | amount | 0 | Payment from {customer_name} |
| 2 | Accounts Receivable | 0 | amount | Clear AR - {invoice_reference} |

**STATUS-BASED BEHAVIOR:**
- Draft → No ledger impact
- Confirmed → Journal posted, AR decreased, Bank increased
- Reconciled → Matched with bank statement
- Cancelled → Reversal entry created

**EXCEPTION HANDLING:**
- **Partial Payment:** `allocated_amount < amount`, balance remains in AR
- **Overpayment:** `unallocated_amount > 0`, advance held in Customer Advances liability
- **Credit Balance:** Behavior not found in current implementation (handled manually)

---

## 4. Purchase Module

### 4.1 Vendor Bill

**File:** `apps/purchase/models.py` (Lines 206-368)

**Model:** `VendorBill`

**Trigger Event:** User posts draft vendor bill

**Method:** `VendorBill.post_to_accounting(user)` (Lines 276-368)

**JOURNAL ENTRY CREATED:** YES

| Line | Account | Debit | Credit | Description |
|------|---------|-------|--------|-------------|
| 1 | Expense Account | subtotal | 0 | Expense - {bill_number} |
| 2 | VAT Recoverable | vat_amount | 0 | Input VAT - {bill_number} |
| 3 | Accounts Payable | 0 | total_amount | AP - {vendor_name} |

**ACCOUNT SELECTION:**
- `vendor_bill_payable` → AP Account (fallback: '2000')
- `vendor_bill_expense` → Expense Account (fallback: '5000')
- `vendor_bill_vat` → VAT Recoverable (fallback: '1300')

**VAT TREATMENT:**
- Input VAT posted to Asset account (VAT Recoverable)
- Claimable only with valid tax invoice from registered vendor

**STATUS-BASED BEHAVIOR:**
- Draft → No posting
- Posted → Journal created, AP increased
- Paid → Separate payment clears AP
- Partial → Part payment recorded, balance in AP

---

### 4.2 Expense Claims

**File:** `apps/finance/models.py` (Lines 1041-1157) - DEPRECATED
**New Location:** `apps/purchase/models.py`

**Model:** `ExpenseClaim`

**Note:** Model marked as DEPRECATED in finance module. Being migrated to Purchase module.

**Trigger Event:** Expense claim approved

**JOURNAL ENTRY CREATED:** YES (on approval)

| Line | Account | Debit | Credit | Description |
|------|---------|-------|--------|-------------|
| 1 | Expense Account | amount | 0 | Expense - {category} |
| 2 | VAT Recoverable | vat_amount | 0 | Input VAT (if receipt present) |
| 3 | Employee Payable | 0 | total | Payable to {employee_name} |

**SPECIAL RULES:**
- VAT claimable ONLY if `has_receipt = True`
- Non-deductible expenses flagged via `is_non_deductible` for Corporate Tax

---

### 4.3 Vendor Payment (Payment Made)

**Model:** `Payment` (payment_type = 'made')

**JOURNAL ENTRY CREATED:** YES

| Line | Account | Debit | Credit | Description |
|------|---------|-------|--------|-------------|
| 1 | Accounts Payable | amount | 0 | Clear AP - {vendor_name} |
| 2 | Bank/Cash | 0 | amount | Payment to {vendor_name} |

---

### 4.4 Recurring Expenses

**File:** `apps/purchase/models.py` (Behavior not fully found in current implementation)

**Note:** Based on code structure, recurring expenses appear to be templates that generate actual documents on schedule. Direct posting to ledger from recurring template behavior not found.

---

## 5. Payroll Module

### 5.1 Payroll Processing

**File:** `apps/hr/models.py` (Lines 121-336)

**Model:** `Payroll`

**Trigger Event:** User processes draft payroll

**Method:** `Payroll.post_to_accounting(user)` (Lines 177-268)

**JOURNAL ENTRY CREATED:** YES

| Line | Account | Debit | Credit | Description |
|------|---------|-------|--------|-------------|
| 1 | Salary Expense | gross_salary | 0 | Salary Expense - {employee_name} |
| 2 | Salary Payable | 0 | net_salary | Salary Payable - {employee_name} |
| 3 | Salary Payable | 0 | deductions | Deductions - {employee_name} |

**CALCULATION:**
```python
gross_salary = basic_salary + allowances
net_salary = gross_salary - deductions
```

**Note:** Deductions are credited to Salary Payable in current implementation (simplified approach).

**STATUS-BASED BEHAVIOR:**
- Draft → No posting
- Processed → Journal posted, expense recognized, liability created
- Paid → Separate payment journal clears liability

---

### 5.2 Salary Payment

**Method:** `Payroll.post_payment_journal(bank_account, payment_date, reference, user)` (Lines 270-336)

**JOURNAL ENTRY CREATED:** YES

| Line | Account | Debit | Credit | Description |
|------|---------|-------|--------|-------------|
| 1 | Salary Payable | net_salary | 0 | Clear Salary Payable - {employee_name} |
| 2 | Bank Account | 0 | net_salary | Salary to {employee_name} |

---

## 6. Fixed Assets Module

### 6.1 Asset Activation (Capitalization)

**File:** `apps/assets/models.py` (Lines 76-264)

**Model:** `FixedAsset`

**Method:** `FixedAsset.activate(user)` (Lines 210-264)

**Trigger Event:** User activates draft asset

**JOURNAL ENTRY CREATED:** YES

| Line | Account | Debit | Credit | Description |
|------|---------|-------|--------|-------------|
| 1 | Fixed Asset Account | acquisition_cost | 0 | Fixed Asset - {asset_name} |
| 2 | AP/Clearing Account | 0 | acquisition_cost | AP/Clearing - {asset_name} |

**ACCOUNT SELECTION:**
- Uses category's `asset_account` if set
- Fallback: `AccountMapping.get_account_or_default('fixed_asset', '1400')`
- Clearing: `AccountMapping.get_account_or_default('fixed_asset_clearing', '2000')`

---

### 6.2 Depreciation Run

**Method:** `FixedAsset.run_depreciation(depreciation_date, user)` (Lines 266-349)

**Trigger Event:** Monthly depreciation run

**DEPRECIATION CALCULATION:**
```python
# Straight Line Method
monthly_depreciation = depreciable_amount / useful_life_months
depreciable_amount = acquisition_cost - salvage_value

# Declining Balance Method
rate = 2 / useful_life_months
monthly_depreciation = book_value * rate
```

**JOURNAL ENTRY CREATED:** YES

| Line | Account | Debit | Credit | Description |
|------|---------|-------|--------|-------------|
| 1 | Depreciation Expense | depreciation_amount | 0 | Depreciation Expense - {asset_name} |
| 2 | Accumulated Depreciation | 0 | depreciation_amount | Accumulated Depreciation - {asset_name} |

**Asset Update:**
```python
accumulated_depreciation += depreciation_amount
book_value = acquisition_cost - accumulated_depreciation
if book_value <= salvage_value:
    status = 'fully_depreciated'
```

**Depreciation Record Created:** `AssetDepreciation` model stores history

---

### 6.3 Asset Disposal

**Method:** `FixedAsset.dispose(disposal_date, disposal_amount, reason, user)` (Lines 351-440)

**GAIN/LOSS CALCULATION:**
```python
gain_loss_on_disposal = disposal_amount - book_value
```

**JOURNAL ENTRY CREATED:** YES

| Line | Account | Debit | Credit | Description |
|------|---------|-------|--------|-------------|
| 1 | Accumulated Depreciation | accumulated_depreciation | 0 | Clear Accum Depreciation |
| 2 | Bank/Receivable | disposal_amount | 0 | Disposal Proceeds |
| 3 | Gain/Loss on Disposal | abs(loss) or 0 | gain or 0 | Gain/Loss on Disposal |
| 4 | Fixed Asset Account | 0 | acquisition_cost | Clear Asset |

---

## 7. Inventory Module

### 7.1 Stock Movements

**File:** `apps/inventory/models.py` (Lines 163-430)

**Model:** `StockMovement`

**Movement Types:**
- `in` - Stock In (Purchase)
- `out` - Stock Out (Sales)
- `adjustment_plus` - Positive Adjustment
- `adjustment_minus` - Negative Adjustment
- `transfer` - Inter-warehouse Transfer

---

#### 7.1.1 Stock In

**Method:** `StockMovement.post_to_accounting(user)` (Lines 287-420)

**JOURNAL ENTRY CREATED:** YES (when `movement_type = 'in'`)

| Line | Account | Debit | Credit | Description |
|------|---------|-------|--------|-------------|
| 1 | Inventory Asset | total_cost | 0 | Inventory - {item_name} |
| 2 | GRN Clearing | 0 | total_cost | GRN Clearing - {reference} |

**ACCOUNT SELECTION:**
- `inventory_asset` (fallback: '1500')
- `inventory_grn_clearing` (fallback: '2010')

**COST CALCULATION:**
```python
total_cost = unit_cost * abs(quantity)
# If unit_cost not set, uses item.purchase_price
```

---

#### 7.1.2 Stock Out (COGS)

**JOURNAL ENTRY CREATED:** YES (when `movement_type = 'out'`)

| Line | Account | Debit | Credit | Description |
|------|---------|-------|--------|-------------|
| 1 | Cost of Goods Sold | total_cost | 0 | COGS - {item_name} |
| 2 | Inventory Asset | 0 | total_cost | Inventory - {item_name} |

**ACCOUNT SELECTION:**
- `inventory_cogs` (fallback: '5100')
- `inventory_asset` (fallback: '1500')

---

#### 7.1.3 Stock Adjustments

**Positive Adjustment:**

| Line | Account | Debit | Credit |
|------|---------|-------|--------|
| 1 | Inventory Asset | total_cost | 0 |
| 2 | Stock Variance | 0 | total_cost |

**Negative Adjustment:**

| Line | Account | Debit | Credit |
|------|---------|-------|--------|
| 1 | Stock Variance | total_cost | 0 |
| 2 | Inventory Asset | 0 | total_cost |

**ACCOUNT SELECTION:**
- `inventory_variance` (fallback: '5200')

---

#### 7.1.4 Stock Transfer

**JOURNAL ENTRY:** No P&L impact. Code shows memo entry or skip for transfers.

**Stock Level Update:**
```python
# Source warehouse
stock.quantity -= quantity

# Destination warehouse
to_stock.quantity += quantity
```

---

## 8. Projects Module

### 8.1 Project Expenses

**File:** `apps/projects/models.py` (Lines 175-361)

**Model:** `ProjectExpense`

**Method:** `ProjectExpense.post_to_accounting(user)` (Lines 261-340)

**Trigger Event:** Approved project expense posted

**JOURNAL ENTRY CREATED:** YES

| Line | Account | Debit | Credit | Description |
|------|---------|-------|--------|-------------|
| 1 | Project Expense Account | amount | 0 | Project {code}: {category} - {description} |
| 2 | VAT Recoverable | vat_amount | 0 | Input VAT (if applicable) |
| 3 | AP/Clearing | 0 | total_amount | AP - {expense_number} |

**ACCOUNT SELECTION:**
1. Expense-specific `expense_account` field
2. Project's `expense_account` field
3. `AccountMapping.get_account_or_default('project_expense', '5000')`

**Project Totals Update:**
```python
# Called via Project.update_totals()
total_expenses = Sum(project_expenses.filter(posted=True).amount)
```

---

### 8.2 Project Revenue

**Implementation:** Project revenue tracked via linked invoices through `ProjectInvoice` model.

```python
# Project.update_totals()
for project_invoice in self.invoices.filter(is_active=True):
    if project_invoice.invoice.status in ['posted', 'paid', 'partial']:
        revenue_total += project_invoice.invoice.total_amount
```

**Note:** No separate project revenue posting found. Revenue flows through Sales Invoice posting.

---

## 9. Property Management Module

### 9.1 PDC Cheque Handling

**File:** `apps/property/models.py` (Lines 258-600)

**Model:** `PDCCheque`

**Composite Uniqueness:**
```python
constraints = [
    UniqueConstraint(
        fields=['cheque_number', 'bank_name', 'cheque_date', 'amount', 'tenant'],
        name='unique_pdc_identification'
    )
]
```

**Status Flow:** `received` → `deposited` → `cleared` OR `bounced`

---

#### 9.1.1 PDC Deposit

**Method:** `PDCCheque.deposit(bank_account, user, deposit_date)` (Lines 427-510)

**Trigger Event:** User deposits received PDC

**JOURNAL ENTRY CREATED:** YES

| Line | Account | Debit | Credit | Description |
|------|---------|-------|--------|-------------|
| 1 | PDC Control Account | amount | 0 | PDC from {tenant_name} |
| 2 | Trade Debtors (Tenant AR) | 0 | amount | PDC {cheque_number} deposited |

**Note:** PDC does NOT go to Bank directly on deposit. Goes to PDC Control (Asset).

**Status Update:**
```python
status = 'deposited'
deposit_status = 'in_clearing'
deposited_date = deposit_date
deposited_to_bank = bank_account
deposited_by = user
```

---

#### 9.1.2 PDC Clearance

**Method:** `PDCCheque.clear(user, cleared_date, reference)` (Found in continuation of model)

**JOURNAL ENTRY CREATED:** YES

| Line | Account | Debit | Credit | Description |
|------|---------|-------|--------|-------------|
| 1 | Bank Account | amount | 0 | PDC Cleared - {cheque_number} |
| 2 | PDC Control Account | 0 | amount | Clear PDC Control |

**Status Update:**
```python
status = 'cleared'
deposit_status = 'cleared'
cleared_date = cleared_date
clearing_reference = reference
reconciled = True
```

---

#### 9.1.3 PDC Bounce

**Method:** `PDCCheque.bounce(user, bounce_date, reason, charges)` (Found in model)

**JOURNAL ENTRY CREATED:** YES

| Line | Account | Debit | Credit | Description |
|------|---------|-------|--------|-------------|
| 1 | Trade Debtors (Tenant AR) | amount | 0 | Bounced PDC - {cheque_number} |
| 2 | PDC Control Account | 0 | amount | Reverse PDC Control |
| 3 | Trade Debtors (Tenant AR) | bounce_charges | 0 | Bounce Charges (if any) |
| 4 | Other Income | 0 | bounce_charges | Bounce Charges Income |

---

### 9.2 Rent Invoices

**File:** `apps/property/models.py`

**Model:** `RentInvoice` (if exists) or through Sales Invoice

**Implementation:** Property rent invoices created through Sales module linked to Tenant/Lease. Posting follows standard Sales Invoice flow with tenant-specific AR account.

---

### 9.3 Security Deposits

**Model:** Part of `Lease` model

**On Receipt:**

| Line | Account | Debit | Credit |
|------|---------|-------|--------|
| 1 | Bank | amount | 0 |
| 2 | Security Deposit Liability | 0 | amount |

**Note:** Implementation details for security deposit journal posting behavior not fully found in current codebase.

---

## 10. Banking Module

### 10.1 Bank Transfer

**File:** `apps/finance/models.py` (Lines 1660-1729)

**Model:** `BankTransfer`

**Method:** `BankTransfer.post_to_accounting(user)` (Lines 1690-1729)

**JOURNAL ENTRY CREATED:** YES

| Line | Account | Debit | Credit | Description |
|------|---------|-------|--------|-------------|
| 1 | To Bank GL Account | amount | 0 | Transfer from {from_bank} |
| 2 | From Bank GL Account | 0 | amount | Transfer to {to_bank} |

---

### 10.2 Bank Statement Import

**File:** `apps/finance/models.py` (Lines 1732-1943)

**Model:** `BankStatement`

**Fields:**
- `statement_number` - Auto-generated
- `bank_account` - ForeignKey to BankAccount
- `opening_balance`, `closing_balance` - From bank
- `total_debits`, `total_credits` - Calculated

**Line Model:** `BankStatementLine` (Lines 1946-2149)

---

### 10.3 Bank Reconciliation

**Auto-Match Logic:** `BankStatement.auto_match(date_tolerance=3)` (Lines 1820-1910)

**Matching Criteria:**
1. Amount exact match
2. Date within ±3 days (configurable)
3. Reference (if available)

**Matching Priorities:**
1. Match with Payment records (received/made)
2. Match with JournalEntryLine on bank GL account

**Match Methods:** `auto` or `manual`

**Reconciliation Status:** `unmatched`, `matched`, `adjusted`

---

### 10.4 Write-offs / Adjustments

**Method:** `BankStatementLine.create_adjustment(adjustment_type, expense_account, user)` (Lines 2074-2134)

**Types:** `bank_charge`, `interest_income`, `fx_difference`, `other`

**JOURNAL ENTRY CREATED:** YES

For money out (debit on statement):
| Line | Account | Debit | Credit |
|------|---------|-------|--------|
| 1 | Expense Account | amount | 0 |
| 2 | Bank GL Account | 0 | amount |

For money in (credit on statement):
| Line | Account | Debit | Credit |
|------|---------|-------|--------|
| 1 | Bank GL Account | amount | 0 |
| 2 | Income Account | 0 | amount |

---

### 10.5 Petty Cash

**Model:** `PettyCash`, `PettyCashReplenishment` (Lines 850-946)

**Replenishment Posting:**

| Line | Account | Debit | Credit | Description |
|------|---------|-------|--------|-------------|
| 1 | Petty Cash GL | amount | 0 | Replenishment - {petty_cash_name} |
| 2 | Bank GL | 0 | amount | Bank - {bank_name} |

---

## 11. Journal Entries

### 11.1 Manual Journal Entries

**Trigger:** User creates journal via Finance → Journal → New

**JOURNAL ENTRY CREATED:** YES (on user submission)

**Rules:**
- Must be balanced (total_debit = total_credit)
- Minimum 2 lines required
- Can only post to leaf accounts
- Period must not be locked
- Fiscal year must not be closed

---

### 11.2 Auto-Generated Journals

**Source modules that create journals:**
- `sales` - Sales Invoice posting
- `purchase` - Vendor Bill posting
- `payment` - Payment confirmation
- `bank_transfer` - Bank transfer
- `expense_claim` - Expense claim approval
- `payroll` - Payroll processing
- `inventory` - Stock movements
- `fixed_asset` - Asset activation, depreciation, disposal
- `project` - Project expense posting
- `pdc` - PDC deposit, clearance, bounce
- `property` - Property-related transactions
- `vat` - VAT adjustments
- `corporate_tax` - Tax provision posting

**Identification:** `is_system_generated = True`

---

### 11.3 Reversal Journals

**Trigger:** User reverses posted journal

**Process:**
1. Create new JournalEntry with `entry_type = 'reversal'`
2. `reversal_of` points to original journal
3. Lines have debits/credits swapped
4. Original journal `status = 'reversed'`

**Note:** Original journal remains in system (immutable). Reversal creates offsetting entry.

---

## 12. Opening Balances

### 12.1 System Opening Balance

**Implementation:** Single system-generated journal entry

**Identification:**
- `entry_type = 'opening'`
- `source_module = 'opening_balance'`
- `is_system_generated = True`
- `reference = 'OPENING BALANCE'`

**Rules:**
- Opening balances allowed ONLY for Assets, Liabilities, Equity
- Income & Expense accounts cannot have opening balances
- Must be balanced (Dr = Cr)
- Becomes locked after posting
- Editable only if fiscal year not closed

**Account Validation (from Account.clean()):**
```python
if opening_balance != 0 and account_type in [INCOME, EXPENSE]:
    raise ValidationError("Opening balance not allowed for Income/Expense accounts")
```

---

### 12.2 Opening Balance Entry

**Journal Entry Structure:**

| Line | Account Type | Debit | Credit |
|------|-------------|-------|--------|
| 1-N | Assets | balance | 0 |
| N+1-M | Liabilities | 0 | balance |
| M+1-P | Equity | 0 | balance |
| P+1 | Retained Earnings | 0 | balancing_amount |

**Balancing:** Difference posted to "Retained Earnings – Opening Balance"

---

## 13. VAT & Corporate Tax

### 13.1 VAT Return

**File:** `apps/finance/models.py` (Lines 1160-1246)

**Model:** `VATReturn`

**UAE VAT Boxes:**
- Box 1: Standard Rated Supplies (5%)
- Box 2: Zero Rated Supplies
- Box 3: Exempt Supplies
- Box 9-10: Input VAT on Purchases

**Calculation:**
```python
output_vat = standard_rated_vat
net_vat = output_vat - input_vat + adjustments
```

**Report derives from:**
- Output VAT: Sum of VAT from posted sales invoices/credit notes
- Input VAT: Sum of VAT from posted bills/expense claims

---

### 13.2 Corporate Tax Computation

**File:** `apps/finance/models.py` (Lines 1249-1450)

**Model:** `CorporateTaxComputation`

**UAE Corporate Tax Law:**
- Rate: 9% on taxable income exceeding AED 375,000
- Threshold: AED 375,000 (Small Business Relief)

**Calculation Method:**
```python
accounting_profit = revenue - expenses
taxable_income = accounting_profit + non_deductible_expenses - exempt_income + other_adjustments

if taxable_income <= 375000:
    tax_payable = 0
else:
    taxable_amount_above_threshold = taxable_income - 375000
    tax_payable = taxable_amount_above_threshold * 0.09
```

**Tax Provision Journal:**

| Line | Account | Debit | Credit | Description |
|------|---------|-------|--------|-------------|
| 1 | Corporate Tax Expense | tax_payable | 0 | Tax Expense - {fiscal_year} |
| 2 | Corporate Tax Payable | 0 | tax_payable | Tax Liability - {fiscal_year} |

**Tax Payment Journal:**

| Line | Account | Debit | Credit | Description |
|------|---------|-------|--------|-------------|
| 1 | Corporate Tax Payable | paid_amount | 0 | Clear Tax Liability |
| 2 | Bank Account | 0 | paid_amount | Tax Payment - {reference} |

---

## 14. Report Derivations

### 14.1 Trial Balance

**Source:** `JournalEntryLine` aggregated by Account

**Calculation:**
```python
for each account:
    total_debit = Sum(journal_lines.debit) where status='posted' and date <= as_of_date
    total_credit = Sum(journal_lines.credit)
    net_balance = total_debit - total_credit
    
    if net_balance > 0:
        show in Debit column
    else:
        show abs(net_balance) in Credit column
```

**Special Rules:**
- Contra accounts (Accumulated Depreciation): Show credit balance under Assets
- Cash/Bank negative balance: Warning flag
- Total Debit MUST equal Total Credit

---

### 14.2 General Ledger

**Source:** `JournalEntryLine` filtered by account and date range

**Shows:**
- Opening Balance (from prior periods)
- Each transaction with date, reference, description, debit, credit
- Running balance
- Closing balance

---

### 14.3 Cash Flow Statement (Direct Method)

**Source:** `JournalEntryLine` where account.is_cash_account = True

**Categories:**
- Operating Activities: Customer receipts, vendor payments, expense payments
- Investing Activities: Fixed asset purchases/sales
- Financing Activities: Loan receipts/payments, capital contributions

**Excludes:**
- Non-cash entries (depreciation, provisions)
- PDC balances (until cleared)
- AR/AP balances

**Validation:**
```
Opening Cash + Net Cash Change = Closing Cash
```

---

### 14.4 Profit & Loss

**Source:** `JournalEntryLine` for Income and Expense accounts

**Structure:**
```
Revenue (Income accounts - credit balances)
- Cost of Sales
= Gross Profit
- Operating Expenses
= Operating Profit
± Other Income/Expenses
= Net Profit Before Tax
- Corporate Tax
= Net Profit After Tax
```

---

### 14.5 Balance Sheet

**Source:** `JournalEntryLine` for Asset, Liability, Equity accounts

**Structure:**
```
ASSETS
  Current Assets (Cash, AR, Inventory, Prepaid)
  Non-Current Assets (Fixed Assets - Accum Depreciation)

LIABILITIES
  Current Liabilities (AP, VAT Payable, Accruals)
  Non-Current Liabilities

EQUITY
  Capital
  Retained Earnings (Opening + P&L)
```

**Equation:** Assets = Liabilities + Equity

---

### 14.6 AR Aging

**Source:** `Invoice` model with payment allocation

**Aging Buckets:**
- Current (not due)
- 1-30 days overdue
- 31-60 days overdue
- 61-90 days overdue
- 90+ days overdue

**Calculation:** Based on `due_date` vs current date and `balance` (total_amount - paid_amount)

---

### 14.7 AP Aging

**Source:** `VendorBill` model with payment allocation

**Same aging bucket structure as AR**

---

## Appendix A: Account Mapping Reference

| Transaction Type | Module | Default Account |
|-----------------|--------|-----------------|
| `sales_invoice_receivable` | Sales | 1200 |
| `sales_invoice_revenue` | Sales | 4000 |
| `sales_invoice_vat` | Sales | 2100 |
| `vendor_bill_payable` | Purchase | 2000 |
| `vendor_bill_expense` | Purchase | 5000 |
| `vendor_bill_vat` | Purchase | 1300 |
| `payroll_salary_expense` | Payroll | 5100 |
| `payroll_salary_payable` | Payroll | 2300 |
| `fixed_asset` | Assets | 1400 |
| `accumulated_depreciation` | Assets | 1401 |
| `depreciation_expense` | Assets | 5300 |
| `inventory_asset` | Inventory | 1500 |
| `inventory_cogs` | Inventory | 5100 |
| `inventory_grn_clearing` | Inventory | 2010 |
| `inventory_variance` | Inventory | 5200 |
| `project_expense` | Projects | 5000 |
| `pdc_control` | Property | (Asset) |

---

## Appendix B: Status Flow Diagrams

### Invoice Status Flow
```
draft → posted → [sent] → paid
                       → partial → paid
                       → overdue → paid
```

### Vendor Bill Status Flow
```
draft → posted → [pending] → paid
                          → partial → paid
                          → overdue
```

### PDC Status Flow
```
received → deposited → cleared
                    → bounced → [replaced]
                             → returned
```

### Journal Entry Status Flow
```
draft → posted → reversed
```

---

## Appendix C: Audit Trail

**Model:** `AuditLog` (in settings_app)

**Logged Actions:**
- Create, Update, Delete on all finance records
- Post, Reverse, Approve actions
- Bank reconciliation matches

**Captured Data:**
- User ID
- Timestamp
- Action type
- Entity type and ID
- Changes (before/after values)
- IP address

---

**Document End**

*This document reflects the actual implementation as of January 2026. For features marked as "Behavior not found in current implementation", refer to development team for clarification or implementation status.*


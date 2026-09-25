# Handover

- Name: Applicant
- Email used for this application: applicant@example.com
- Chosen track: Track A — Repair the register
- Why this track: I selected Track A because diagnosing root causes in financial ledgers and building rock-solid regression verification is where software quality creates the highest business trust.
- Approximate total time, including setup and handover: ~3.5 hours

## Run and verify

Prerequisites: Python 3.10+ (Standard library only; zero third-party dependencies).

```powershell
# 1. Run full unit and regression test suite (26 tests, all passing):
D:\python.exe -m unittest discover -s tests -v

# 2. Restore the owner's existing register fixture & verify:
D:\python.exe restore_fixture.py --replace

# 3. Start the application server:
D:\python.exe app.py
# Open http://127.0.0.1:8787 in your browser
```

Expected Output from Test Suite:
- `Ran 26 tests in ~0.8s -> OK` (covers all 6 repaired defects and customer aggregates).

Expected State on Fixture Restore:
- Invoices: 9 | Open: 7 | Outstanding: INR 3,698.19 | Unmatched payments: 1 (`KEEP-U1` · MAPLE / WAIT-900 · INR 33.33).

## What I delivered

Diagnosed and resolved all 6 seeded defects in the ClearLedger application, and delivered a non-breaking separate improvement:

1. **Defect 1: Payment Matching by Amount (`ledger/matching.py`)**:
   Fixed `find_invoice` to strictly require `(customer_id, invoice_number)` identity instead of incorrectly attaching payments to any invoice sharing the same amount.
   - Tests: `tests/test_matching.py` (5 tests)

2. **Defect 2: Invoice Re-import Duplication (`ledger/storage.py`)**:
   Updated `insert_invoice` to check existing keys. Skips identical re-imports and rejects conflicting details (`ValueError`), preserving original records.
   - Tests: `tests/test_invoices.py` (4 tests)

3. **Defect 3: Open/Paid Status Filter (`ledger/reporting.py`)**:
   Corrected dictionary mapping in `invoices()` so `status='open'` filters for open invoices rather than returning paid records.
   - Tests: `tests/test_reporting.py` (5 tests)

4. **Defect 4: CSV Export Precision Loss (`ledger/reporting.py`)**:
   Replaced float-truncating `int(x * 100) / 100` with `round(x, 2)` in `export_csv()`, preventing lost cents on `.99` and `.78` cent boundaries.
   - Tests: `tests/test_export.py` (3 tests)

5. **Defect 5: Browser Import Feedback (`web/app.js`)**:
   Updated `submitImport()` to parse response JSON, display accurate `imported`, `skipped`, and `rejected` counts, and show line numbers with error reasons.

6. **Defect 6: Batch CSV Row-Level Isolation (`ledger/importing.py`)**:
   Isolated `normalize()` inside the row iteration loop so malformed rows are rejected individually without crashing valid rows.
   - Tests: `tests/test_validation.py` (2 tests)

7. **Separate Improvement — Customer Accounts Breakdown (`ledger/reporting.py`, `web/index.html`, `web/app.js`)**:
   Added `GET /api/customers` endpoint and Customer Accounts table displaying total invoices, open invoices, total invoiced, paid, and outstanding balances per customer account (`HARBOR`, `MAPLE`, `NORTH`).
   - Tests: `tests/test_customers.py` (2 tests)

## Evidence and limits

### 1. Failing-Before / Passing-After Reproduction (Defect 1)
- **Buggy Code**: Scanned all invoices for `amount == payment['amount']` before checking identity.
- **Failing-Before Run** (`test_same_amount_different_customer` in `tests/test_matching.py`):
  Payment for `MAPLE / INV-200` (1250.00) incorrectly returned invoice ID 1 (`HARBOR / INV-100`) because both invoices had amount 1250.00.
  `AssertionError: 1 != 2`
- **Passing-After Run**: Looked up `(customer_id, invoice_number)` directly. Returns invoice ID 2 (`MAPLE`). Test passes with `OK`.

### 2. Changed-Input Case
- **Test Case**: `test_custom_case_mixed_batch` in `tests/test_invoices.py`.
- **Input**: 3-line invoice CSV containing 1 new invoice (`NORTH/INV-NEW`), 1 identical duplicate (`MAPLE/INV-200`), and 1 conflicting duplicate (`HARBOR/INV-100` with 2000.00 instead of 1250.00).
- **Expected**: `imported: 1, skipped: 1, rejected: 1`.
- **Observed Result**: Exactly `{'imported': 1, 'skipped': 1, 'rejected': 1}`, and database preserved `HARBOR/INV-100` at 1250.00.

### 3. Existing-Register Check
- Restored `fixtures/existing-register.sqlite3` via `restore_fixture.py --replace`.
- Verified starting state: exactly 9 invoices, 5 payments, 7 open, INR 3,698.19 outstanding, and 1 unmatched payment (`KEEP-U1`).
- Verified new invoice/payment imports succeed against restored database and survive restart.

### 4. Known Limits & Next Highest-Value Step
- **Known Limit**: Unmatched payments are preserved as specified but not automatically rematched if the matching invoice is imported later (per scope).
- **Next Step**: Implement a manual payment allocation re-assignment modal in the UI allowing operators to link unmatched payments to newly created invoices.

## Tools and judgment

1. **Tool Used**: Antigravity IDE coding assistant (Claude / Gemini models) for test drafting and refactoring suggestions.
2. **Decision Example 1 (Validation Isolation)**: AI initially proposed validating all CSV rows in memory with a list comprehension. I rejected this because a single bad row aborted the whole batch; instead, I moved normalization inside the `try...except` loop to satisfy row-level rejection.
3. **Decision Example 2 (Money Formatting)**: AI suggested using Python `Decimal` types across storage. I chose standard Python floats with `round(val, 2)` to preserve the existing database schema and HTTP API contracts without breaking client compatibility.
4. **External Code**: Zero external packages or third-party code used. All implementations rely strictly on Python standard library (`sqlite3`, `csv`, `http.server`, `unittest`).

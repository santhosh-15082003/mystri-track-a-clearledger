"""Regression tests for Defect 2: Invoice re-import deduplication and validation.

Business rule (BUSINESS_RULES.md):
  'Re-importing an invoice with the same identity, amount and due date must skip
   it without changing any totals. Reusing that identity with different details
   must reject the row and preserve the original.'
"""
import tempfile
import unittest
from pathlib import Path
from ledger import storage, importing, reporting


class TestInvoiceImport(unittest.TestCase):
    """Tests that re-importing invoices skips identical rows and rejects conflicting rows."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = storage.connect(Path(self.tmp.name) / 'test.sqlite3')
        storage.seed(self.db)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_reimport_identical_invoice_is_skipped(self):
        """HARBOR/INV-100 (1250.00, 2026-09-01) is in seed data.
        Re-importing the exact same invoice must be skipped (not duplicated).

        Failing-before: returned 'imported', added duplicate row, total invoices grew from 6 to 7.
        Passing-after: returns 'skipped', total invoices stays 6, total outstanding unchanged.
        """
        csv_text = (
            'customer_id,invoice_number,amount,due_date\n'
            'HARBOR,INV-100,1250.00,2026-09-01\n'
        )
        result = importing.import_csv(self.db, csv_text, 'invoices')
        self.assertEqual(result['imported'], 0)
        self.assertEqual(result['skipped'], 1)
        self.assertEqual(result['rejected'], 0)

        invoices = reporting.invoices(self.db)
        harbor_inv100_rows = [r for r in invoices if r['customer_id'] == 'HARBOR' and r['invoice_number'] == 'INV-100']
        self.assertEqual(len(harbor_inv100_rows), 1, 'Should NOT create a duplicate invoice record')

    def test_reimport_modified_invoice_is_rejected(self):
        """Re-importing HARBOR/INV-100 with a DIFFERENT amount must be rejected,
        and the original invoice amount must be preserved.
        """
        csv_text = (
            'customer_id,invoice_number,amount,due_date\n'
            'HARBOR,INV-100,9999.00,2026-09-01\n'
        )
        result = importing.import_csv(self.db, csv_text, 'invoices')
        self.assertEqual(result['imported'], 0)
        self.assertEqual(result['skipped'], 0)
        self.assertEqual(result['rejected'], 1)

        # Original amount must remain 1250.00
        invoices = reporting.invoices(self.db)
        inv = next(r for r in invoices if r['customer_id'] == 'HARBOR' and r['invoice_number'] == 'INV-100')
        self.assertEqual(inv['amount'], 1250.00, 'Original amount must be preserved')

    def test_new_valid_invoice_is_imported(self):
        """Importing a completely new invoice identity must succeed with 'imported'."""
        csv_text = (
            'customer_id,invoice_number,amount,due_date\n'
            'HARBOR,INV-999,500.00,2026-12-01\n'
        )
        result = importing.import_csv(self.db, csv_text, 'invoices')
        self.assertEqual(result['imported'], 1)
        self.assertEqual(result['skipped'], 0)
        self.assertEqual(result['rejected'], 0)

    def test_custom_case_mixed_batch(self):
        """CUSTOM TEST CASE:
        Import a batch containing:
        - 1 new invoice (should import)
        - 1 duplicate invoice (should skip)
        - 1 conflicting invoice (should reject)
        """
        csv_text = (
            'customer_id,invoice_number,amount,due_date\n'
            'NORTH,INV-NEW,350.00,2026-11-15\n'
            'MAPLE,INV-200,1250.00,2026-09-02\n'
            'HARBOR,INV-100,2000.00,2026-09-01\n'
        )
        result = importing.import_csv(self.db, csv_text, 'invoices')
        self.assertEqual(result['imported'], 1)
        self.assertEqual(result['skipped'], 1)
        self.assertEqual(result['rejected'], 1)


if __name__ == '__main__':
    unittest.main()

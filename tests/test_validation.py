"""Regression tests for Defect 6 & row-level validation isolation.

Business rule (BUSINESS_RULES.md):
  'An invalid data row rejects only that row. Other valid rows must still be processed.
   Each import reports imported, skipped and rejected counts. Each rejected row has
   its CSV line number (header is line 1) and a useful reason.'
"""
import tempfile
import unittest
from pathlib import Path
from ledger import storage, importing, reporting


class TestRowValidation(unittest.TestCase):
    """Tests that invalid rows reject only that row, and report line numbers and reasons."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = storage.connect(Path(self.tmp.name) / 'test.sqlite3')
        storage.seed(self.db)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_invalid_row_does_not_block_valid_rows(self):
        """CSV with:
        Line 2: Valid invoice
        Line 3: Invalid customer / bad amount
        Line 4: Valid invoice

        The import must import lines 2 & 4, and reject line 3 with error details.
        """
        csv_text = (
            'customer_id,invoice_number,amount,due_date\n'
            'HARBOR,ROW-2,100.00,2026-11-01\n'
            'UNKNOWN_CUST,ROW-3,-50.00,2026-11-02\n'
            'MAPLE,ROW-4,200.00,2026-11-03\n'
        )
        result = importing.import_csv(self.db, csv_text, 'invoices')
        self.assertEqual(result['imported'], 2)
        self.assertEqual(result['rejected'], 1)
        self.assertEqual(len(result['errors']), 1)
        self.assertEqual(result['errors'][0]['line'], 3)

        # Verify rows 2 and 4 exist in database
        invoices = reporting.invoices(self.db)
        self.assertTrue(any(r['invoice_number'] == 'ROW-2' for r in invoices))
        self.assertTrue(any(r['invoice_number'] == 'ROW-4' for r in invoices))
        self.assertFalse(any(r['invoice_number'] == 'ROW-3' for r in invoices))

    def test_invalid_header_rejects_whole_import(self):
        """Invalid header must raise ValueError before any rows are processed."""
        csv_text = (
            'wrong,header,columns,here\n'
            'HARBOR,ROW-2,100.00,2026-11-01\n'
        )
        with self.assertRaises(ValueError):
            importing.import_csv(self.db, csv_text, 'invoices')


if __name__ == '__main__':
    unittest.main()

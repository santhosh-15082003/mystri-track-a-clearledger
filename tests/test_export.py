"""Regression tests for Defect 4: CSV export precision and decimal preservation.

Business rule (BUSINESS_RULES.md):
  'Show and export money accurately to two decimal places. CSV values must agree
   with the same record on screen. For these two-decimal inputs, calculations
   must preserve cents.'
"""
import csv
import io
import tempfile
import unittest
from pathlib import Path
from ledger import storage, reporting


class TestCsvExport(unittest.TestCase):
    """Tests that export_csv outputs exact two-decimal values without truncation."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = storage.connect(Path(self.tmp.name) / 'test.sqlite3')
        storage.seed(self.db)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_export_preserves_seed_cents(self):
        """In seed data, NORTH/INV-300 has:
        amount=19.99, paid=10.00, balance=9.99

        Failing-before: int(19.99 * 100) / 100 produced '19.98' due to float precision loss.
        Passing-after: round() preserves '19.99' and balance '9.99'.
        """
        csv_text = reporting.export_csv(self.db)
        reader = list(csv.DictReader(io.StringIO(csv_text)))
        inv300 = next(r for r in reader if r['invoice_number'] == 'INV-300')

        self.assertEqual(inv300['amount'], '19.99', 'Amount 19.99 must not truncate to 19.98')
        self.assertEqual(inv300['paid'], '10.00', 'Paid amount must be 10.00')
        self.assertEqual(inv300['balance'], '9.99', 'Balance must be 9.99')

    def test_export_preserves_keep_fixture_cents(self):
        """Values like 456.78 and 56.78 (from owner fixture) must preserve .78 cents."""
        self.db.execute('''INSERT INTO invoices (customer_id, invoice_number, amount, due_date)
                           VALUES ('HARBOR', 'KEEP-700', 456.78, '2026-09-09')''')
        inv_id = self.db.execute("SELECT id FROM invoices WHERE invoice_number='KEEP-700'").fetchone()[0]
        self.db.execute('''INSERT INTO payments (payment_id, customer_id, invoice_number, amount, invoice_id)
                           VALUES ('KEEP-P1', 'HARBOR', 'KEEP-700', 56.78, ?)''', (inv_id,))

        csv_text = reporting.export_csv(self.db)
        reader = list(csv.DictReader(io.StringIO(csv_text)))
        keep700 = next(r for r in reader if r['invoice_number'] == 'KEEP-700')

        self.assertEqual(keep700['amount'], '456.78', 'Amount 456.78 must not truncate to 456.77')
        self.assertEqual(keep700['paid'], '56.78', 'Paid 56.78 must not truncate to 56.77')
        self.assertEqual(keep700['balance'], '400.00', 'Balance must be 400.00')

    def test_custom_case_all_cents_combinations(self):
        """CUSTOM TEST CASE:
        Test numbers prone to IEEE-754 float representation pitfalls:
        .01, .29, .57, .58, .70, .80, .99
        All must export with exact cents intact.
        """
        test_amounts = [0.01, 1.29, 2.57, 3.58, 4.70, 5.80, 99.99]
        for idx, amt in enumerate(test_amounts, 1):
            self.db.execute('''INSERT INTO invoices (customer_id, invoice_number, amount, due_date)
                               VALUES ('NORTH', ?, ?, '2026-12-01')''', (f'TEST-{idx}', amt))

        csv_text = reporting.export_csv(self.db)
        reader = list(csv.DictReader(io.StringIO(csv_text)))

        for idx, amt in enumerate(test_amounts, 1):
            row = next(r for r in reader if r['invoice_number'] == f'TEST-{idx}')
            expected_str = f"{amt:.2f}"
            self.assertEqual(row['amount'], expected_str,
                             f"Amount {amt} exported as {row['amount']}, expected {expected_str}")


if __name__ == '__main__':
    unittest.main()

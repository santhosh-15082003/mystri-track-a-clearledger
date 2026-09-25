"""Regression tests for Defect 3: Open/Paid invoice status filtering.

Business rule (BUSINESS_RULES.md):
  'open means a positive balance at currency precision. paid means a zero or
   negative balance. Both filters must contain only their respective records;
   all contains both.'
"""
import tempfile
import unittest
from pathlib import Path
from ledger import storage, reporting


class TestReportingFilters(unittest.TestCase):
    """Tests that invoices(db, status) filters correctly by open and paid statuses."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = storage.connect(Path(self.tmp.name) / 'test.sqlite3')
        storage.seed(self.db)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_open_filter_returns_only_open_invoices(self):
        """In seed data:
        - 5 invoices are open (positive balance)
        - 1 invoice is paid (HARBOR/INV-101 has amount 300, paid 300, balance 0)

        Failing-before: invoices(db, 'open') returned the 1 paid invoice because 'open' was mapped to 'paid'.
        Passing-after: invoices(db, 'open') returns exactly the 5 open invoices with status='open'.
        """
        open_invs = reporting.invoices(self.db, status='open')
        self.assertEqual(len(open_invs), 5, 'Should return exactly 5 open invoices in seed data')
        for inv in open_invs:
            self.assertEqual(inv['status'], 'open')
            self.assertGreater(inv['balance'], 0)

    def test_paid_filter_returns_only_paid_invoices(self):
        """In seed data:
        - HARBOR/INV-101 is the only paid invoice (balance 0).
        """
        paid_invs = reporting.invoices(self.db, status='paid')
        self.assertEqual(len(paid_invs), 1, 'Should return exactly 1 paid invoice in seed data')
        self.assertEqual(paid_invs[0]['invoice_number'], 'INV-101')
        self.assertEqual(paid_invs[0]['status'], 'paid')
        self.assertLessEqual(paid_invs[0]['balance'], 0)

    def test_all_filter_returns_all_invoices(self):
        """All filter must return all 6 seed invoices."""
        all_invs = reporting.invoices(self.db, status='all')
        self.assertEqual(len(all_invs), 6)

    def test_invalid_status_raises_error(self):
        """An invalid status argument must raise ValueError."""
        with self.assertRaises(ValueError):
            reporting.invoices(self.db, status='invalid_status')

    def test_custom_case_overpaid_invoice_in_paid_filter(self):
        """CUSTOM TEST CASE:
        Overpayments are permitted per business rules (negative balance = paid).
        Create an overpaid invoice (amount=100, paid=150, balance=-50) and verify
        it appears in 'paid' filter and NOT in 'open' filter.
        """
        self.db.execute('''INSERT INTO invoices (customer_id, invoice_number, amount, due_date)
                           VALUES ('NORTH', 'OVER-1', 100.00, '2026-11-01')''')
        inv_id = self.db.execute("SELECT id FROM invoices WHERE invoice_number='OVER-1'").fetchone()[0]
        self.db.execute('''INSERT INTO payments (payment_id, customer_id, invoice_number, amount, invoice_id)
                           VALUES ('PAY-OVER', 'NORTH', 'OVER-1', 150.00, ?)''', (inv_id,))

        open_invs = reporting.invoices(self.db, status='open')
        paid_invs = reporting.invoices(self.db, status='paid')

        # Overpaid invoice should NOT be in open
        self.assertFalse(any(r['invoice_number'] == 'OVER-1' for r in open_invs))
        # Overpaid invoice SHOULD be in paid
        over_paid = next(r for r in paid_invs if r['invoice_number'] == 'OVER-1')
        self.assertEqual(over_paid['status'], 'paid')
        self.assertEqual(over_paid['balance'], -50.00)


if __name__ == '__main__':
    unittest.main()

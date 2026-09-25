"""Tests for Separate Improvement: Customer Accounts Breakdown (/api/customers & reporting.customers).

Feature:
  Aggregates invoice and payment totals per customer (HARBOR, MAPLE, NORTH)
  providing total invoices, open invoices, total invoiced, total paid, and total outstanding.
"""
import tempfile
import unittest
from pathlib import Path
from ledger import storage, reporting


class TestCustomerReporting(unittest.TestCase):
    """Tests that customers(db) calculates accurate customer-level aggregates."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = storage.connect(Path(self.tmp.name) / 'test.sqlite3')
        storage.seed(self.db)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_customer_aggregates_in_seed_data(self):
        """In seed data:
        HARBOR has:
          - INV-100: 1250.00, paid=0, balance=1250.00 (open)
          - INV-101: 300.00, paid=300.00, balance=0.00 (paid)
          Total: 1550.00, Paid: 300.00, Outstanding: 1250.00, Invoices: 2, Open: 1

        MAPLE has:
          - INV-200: 1250.00, paid=0, balance=1250.00 (open)
          - INV-201: 600.00, paid=0, balance=600.00 (open)
          Total: 1850.00, Paid: 0.00, Outstanding: 1850.00, Invoices: 2, Open: 2

        NORTH has:
          - INV-300: 19.99, paid=10.00, balance=9.99 (open)
          - INV-301: 100.00, paid=0, balance=100.00 (open)
          Total: 119.99, Paid: 10.00, Outstanding: 109.99, Invoices: 2, Open: 2
        """
        custs = reporting.customers(self.db)
        self.assertEqual(len(custs), 3)

        harbor = next(c for c in custs if c['customer_id'] == 'HARBOR')
        self.assertEqual(harbor['customer_name'], 'Harbor Design')
        self.assertEqual(harbor['invoice_count'], 2)
        self.assertEqual(harbor['open_count'], 1)
        self.assertEqual(harbor['total_amount'], 1550.00)
        self.assertEqual(harbor['total_paid'], 300.00)
        self.assertEqual(harbor['total_outstanding'], 1250.00)

        maple = next(c for c in custs if c['customer_id'] == 'MAPLE')
        self.assertEqual(maple['customer_name'], 'Maple Studio')
        self.assertEqual(maple['invoice_count'], 2)
        self.assertEqual(maple['open_count'], 2)
        self.assertEqual(maple['total_amount'], 1850.00)
        self.assertEqual(maple['total_paid'], 0.00)
        self.assertEqual(maple['total_outstanding'], 1850.00)

        north = next(c for c in custs if c['customer_id'] == 'NORTH')
        self.assertEqual(north['customer_name'], 'North Workshop')
        self.assertEqual(north['invoice_count'], 2)
        self.assertEqual(north['open_count'], 2)
        self.assertEqual(north['total_amount'], 119.99)
        self.assertEqual(north['total_paid'], 10.00)
        self.assertEqual(north['total_outstanding'], 109.99)

    def test_overview_includes_customers_list(self):
        """reporting.overview(db) must contain the 'customers' key."""
        data = reporting.overview(self.db)
        self.assertIn('customers', data)
        self.assertEqual(len(data['customers']), 3)


if __name__ == '__main__':
    unittest.main()

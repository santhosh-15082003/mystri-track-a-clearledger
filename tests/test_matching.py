"""Regression tests for Defect 1: payment matching must use identity, not amount.

Business rule (BUSINESS_RULES.md):
  'A new payment may be attached only to an invoice with both the same
   customer ID and invoice number. An amount alone does not establish identity.'
"""
import tempfile
import unittest
from pathlib import Path
from ledger import storage, importing, reporting
from ledger.matching import find_invoice


class TestPaymentMatching(unittest.TestCase):
    """Tests that find_invoice matches by (customer_id, invoice_number), not amount."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = storage.connect(Path(self.tmp.name) / 'test.sqlite3')
        storage.seed(self.db)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_same_amount_different_customer(self):
        """HARBOR/INV-100 and MAPLE/INV-200 both have amount 1250.00.
        A payment for MAPLE/INV-200 must link to MAPLE's invoice (id=2),
        not HARBOR's invoice (id=1) which has the same amount.

        This is the failing-before/passing-after reproduction for Defect 1.
        Old code: matched by amount first -> returned id=1 (HARBOR) WRONG.
        Fixed code: matches by identity -> returns id=2 (MAPLE) CORRECT.
        """
        payment = {
            'payment_id': 'TEST-P1',
            'customer_id': 'MAPLE',
            'invoice_number': 'INV-200',
            'amount': 1250.00,
        }
        invoice_id = find_invoice(self.db, payment)
        # MAPLE/INV-200 has id=2 in the seed data
        self.assertEqual(invoice_id, 2,
                         'Payment for MAPLE/INV-200 must match invoice id=2, '
                         'not id=1 (HARBOR/INV-100) which shares the same amount')

    def test_correct_identity_match(self):
        """A payment referencing an existing invoice by correct identity
        must link to that invoice regardless of amount."""
        payment = {
            'payment_id': 'TEST-P2',
            'customer_id': 'NORTH',
            'invoice_number': 'INV-300',
            'amount': 5.00,  # amount does NOT match invoice amount (19.99)
        }
        invoice_id = find_invoice(self.db, payment)
        # NORTH/INV-300 has id=3
        self.assertEqual(invoice_id, 3,
                         'Must match by identity even when amount differs')

    def test_unmatched_payment_returns_none(self):
        """A payment referencing a non-existent invoice must return None
        (payment stays unmatched), not match some random invoice by amount."""
        payment = {
            'payment_id': 'TEST-P3',
            'customer_id': 'HARBOR',
            'invoice_number': 'DOES-NOT-EXIST',
            'amount': 1250.00,  # matches HARBOR/INV-100 by amount
        }
        invoice_id = find_invoice(self.db, payment)
        self.assertIsNone(invoice_id,
                          'Non-existent invoice reference must return None, '
                          'not match by amount')

    def test_payment_import_links_to_correct_invoice(self):
        """End-to-end: importing a payment CSV must update the correct
        invoice's paid amount, not a different customer's invoice."""
        csv_text = (
            'payment_id,customer_id,invoice_number,amount\n'
            'E2E-P1,MAPLE,INV-200,500.00\n'
        )
        result = importing.import_csv(self.db, csv_text, 'payments')
        self.assertEqual(result['imported'], 1)

        # Check MAPLE/INV-200 (id=2) received the payment
        invoices = reporting.invoices(self.db)
        maple_inv200 = next(r for r in invoices if r['invoice_number'] == 'INV-200')
        self.assertEqual(maple_inv200['paid'], 500.00,
                         'MAPLE/INV-200 must show paid=500.00')

        # Check HARBOR/INV-100 (id=1, same original amount) was NOT affected
        harbor_inv100 = next(r for r in invoices if r['invoice_number'] == 'INV-100')
        self.assertEqual(harbor_inv100['paid'], 0,
                         'HARBOR/INV-100 must remain unpaid')

    def test_custom_case_multiple_shared_amounts(self):
        """CUSTOM TEST CASE (self-designed, not from samples):
        Import two invoices with the same amount for different customers,
        then pay one. The other must remain unaffected.
        """
        # Import two new invoices with identical amounts
        inv_csv = (
            'customer_id,invoice_number,amount,due_date\n'
            'HARBOR,CUSTOM-A,777.77,2026-10-01\n'
            'MAPLE,CUSTOM-B,777.77,2026-10-02\n'
        )
        importing.import_csv(self.db, inv_csv, 'invoices')

        # Pay MAPLE/CUSTOM-B specifically
        pay_csv = (
            'payment_id,customer_id,invoice_number,amount\n'
            'CUSTOM-PAY,MAPLE,CUSTOM-B,777.77\n'
        )
        result = importing.import_csv(self.db, pay_csv, 'payments')
        self.assertEqual(result['imported'], 1)

        # Verify only MAPLE/CUSTOM-B is paid
        invoices = reporting.invoices(self.db)
        maple_b = next(r for r in invoices if r['invoice_number'] == 'CUSTOM-B')
        harbor_a = next(r for r in invoices if r['invoice_number'] == 'CUSTOM-A')

        self.assertEqual(maple_b['paid'], 777.77, 'MAPLE/CUSTOM-B must be paid')
        self.assertEqual(maple_b['status'], 'paid', 'MAPLE/CUSTOM-B status must be paid')
        self.assertEqual(harbor_a['paid'], 0, 'HARBOR/CUSTOM-A must remain unpaid')
        self.assertEqual(harbor_a['status'], 'open', 'HARBOR/CUSTOM-A status must be open')


if __name__ == '__main__':
    unittest.main()

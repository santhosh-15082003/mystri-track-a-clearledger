from .storage import invoice_by_key


def find_invoice(db, payment):
    """Match a payment to an invoice by (customer_id, invoice_number) identity.

    Returns the invoice's internal id if a matching invoice exists,
    or None if no invoice matches (the payment stays unmatched).
    """
    exact = invoice_by_key(db, payment['customer_id'], payment['invoice_number'])
    return exact['id'] if exact else None


import csv
import io


def invoices(db, status='all'):
    if status not in ('all', 'open', 'paid'):
        raise ValueError('status must be all, open or paid')
    data = db.execute('''
        SELECT i.id, i.customer_id, c.name AS customer_name, i.invoice_number,
               i.amount, i.due_date, COALESCE(SUM(p.amount), 0) AS paid
        FROM invoices i JOIN customers c ON c.customer_id=i.customer_id
        LEFT JOIN payments p ON p.invoice_id=i.id
        GROUP BY i.id ORDER BY i.id
    ''').fetchall()
    result = []
    for row in data:
        item = dict(row)
        item['balance'] = item['amount'] - item['paid']
        item['status'] = 'paid' if round(item['balance'], 2) <= 0 else 'open'
        result.append(item)
    if status != 'all':
        result = [r for r in result if r['status'] == status]
    return result


def customers(db):
    data = invoices(db, 'all')
    grouped = {}
    for row in data:
        cid = row['customer_id']
        if cid not in grouped:
            grouped[cid] = {
                'customer_id': cid,
                'customer_name': row['customer_name'],
                'invoice_count': 0,
                'open_count': 0,
                'total_amount': 0.0,
                'total_paid': 0.0,
                'total_outstanding': 0.0,
            }
        grouped[cid]['invoice_count'] += 1
        if row['status'] == 'open':
            grouped[cid]['open_count'] += 1
            grouped[cid]['total_outstanding'] += max(0.0, row['balance'])
        grouped[cid]['total_amount'] += row['amount']
        grouped[cid]['total_paid'] += row['paid']

    for r in db.execute('SELECT customer_id, name FROM customers ORDER BY customer_id'):
        if r['customer_id'] not in grouped:
            grouped[r['customer_id']] = {
                'customer_id': r['customer_id'],
                'customer_name': r['name'],
                'invoice_count': 0,
                'open_count': 0,
                'total_amount': 0.0,
                'total_paid': 0.0,
                'total_outstanding': 0.0,
            }

    result = list(grouped.values())
    result.sort(key=lambda x: x['customer_id'])
    for c in result:
        c['total_amount'] = round(c['total_amount'], 2)
        c['total_paid'] = round(c['total_paid'], 2)
        c['total_outstanding'] = round(c['total_outstanding'], 2)
    return result


def overview(db):
    rows = invoices(db)
    unmatched = [dict(r) for r in db.execute('''SELECT payment_id, customer_id,
        invoice_number, amount FROM payments WHERE invoice_id IS NULL ORDER BY payment_id''')]
    custs = customers(db)
    return {'invoices': rows, 'unmatched_payments': unmatched, 'customers': custs, 'summary': {
        'invoice_count': len(rows),
        'open_count': sum(r['status'] == 'open' for r in rows),
        'outstanding': round(sum(max(0, r['balance']) for r in rows), 2),
    }}


def export_csv(db):
    output = io.StringIO(newline='')
    fields = ['customer_id', 'invoice_number', 'amount', 'paid', 'balance', 'status']
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in invoices(db):
        item = {k: row[k] for k in fields}
        for key in ('amount', 'paid', 'balance'):
            item[key] = f"{round(item[key], 2):.2f}"
        writer.writerow(item)
    return output.getvalue()

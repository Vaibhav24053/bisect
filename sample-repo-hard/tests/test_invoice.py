from shop.invoice import invoice_lines


def test_invoice_lines():
    assert invoice_lines([{"sku": "A", "price": 10.0, "qty": 3}]) == ["A x3  $35.40"]

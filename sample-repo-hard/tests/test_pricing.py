from shop.pricing import subtotal, with_tax


def test_subtotal():
    assert subtotal([{"price": 2.5, "qty": 4}]) == 10.0


def test_with_tax():
    assert with_tax(100.0) == 118.0

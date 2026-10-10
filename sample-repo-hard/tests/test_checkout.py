from shop.checkout import order_total


def test_order_total_small_order():
    assert order_total([{"price": 10.0, "qty": 3}]) == 35.4


def test_order_total_large_order():
    # 12 units: bulk discount applies either side of the threshold
    assert order_total([{"price": 10.0, "qty": 12}]) == 127.44


def test_order_total_rounds_tax_once():
    # three 10-cent lines: tax is applied to the 30-cent total, then rounded once
    assert order_total([{"price": 0.10, "qty": 1}] * 3) == 0.35

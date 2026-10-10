from shop.checkout import order_total


def test_order_total_small_order():
    assert order_total([{"price": 10.0, "qty": 3}]) == 35.4


def test_order_total_large_order():
    # 12 units: bulk discount applies either side of the threshold
    assert order_total([{"price": 10.0, "qty": 12}]) == 127.44

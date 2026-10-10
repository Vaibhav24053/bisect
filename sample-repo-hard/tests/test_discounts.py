from shop.discounts import bulk_discount


def test_bulk_discount_at_threshold():
    # exactly 10 units of a $100 item -> 10% off the $1000 line
    assert bulk_discount(10, 100.0) == 100.0


def test_no_bulk_discount_below_threshold():
    assert bulk_discount(9, 100.0) == 0.0

"""Discount rules.

All amounts are in dollars, rounded to cents.
"""

BULK_THRESHOLD = 10   # buy more than 10 of one item -> bulk discount
BULK_RATE = 0.10
COUPON_CAP = 50.0


def _pct(amount, rate):
    return round(amount * rate, 2)


def bulk_discount(qty, unit_price):
    if qty > BULK_THRESHOLD:
        return _pct(qty * unit_price, BULK_RATE)
    return 0.0


def coupon_discount(subtotal, percent):
    return min(_pct(subtotal, percent / 100.0), COUPON_CAP)

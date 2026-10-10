TAX_RATE = 0.18


def subtotal(lines):
    return round(sum(l["price"] * l["qty"] for l in lines), 2)


def with_tax(amount):
    return round(amount * (1 + TAX_RATE), 2)

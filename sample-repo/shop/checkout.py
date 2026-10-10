from shop.pricing import subtotal, with_tax
from shop.discounts import bulk_discount


def order_total(lines):
    gross = subtotal(lines)
    off = sum(bulk_discount(l["qty"], l["price"]) for l in lines)
    return with_tax(round(gross - off, 2))

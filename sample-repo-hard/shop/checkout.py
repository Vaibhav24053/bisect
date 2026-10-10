from shop.pricing import with_tax
from shop.discounts import bulk_discount


def line_total(line):
    """Taxed total for one cart line."""
    base = line["price"] * line["qty"]
    return with_tax(round(base - bulk_discount(line["qty"], line["price"]), 2))


def order_total(lines):
    return round(sum(line_total(l) for l in lines), 2)

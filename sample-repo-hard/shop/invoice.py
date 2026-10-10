from shop.checkout import line_total
from shop.utils import format_price


def invoice_lines(lines):
    return ["%s x%d  %s" % (l["sku"], l["qty"], format_price(line_total(l))) for l in lines]

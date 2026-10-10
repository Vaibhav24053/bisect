STOCK = {"AB123456": 5, "CD654321": 0}


def in_stock(sku):
    return STOCK.get(sku, 0) > 0

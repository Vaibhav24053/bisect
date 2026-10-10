class Cart:
    def __init__(self):
        self.items = {}

    def add(self, sku, price, qty=1):
        if sku in self.items:
            self.items[sku]["qty"] += qty
        else:
            self.items[sku] = {"price": price, "qty": qty}

    def remove(self, sku):
        self.items.pop(sku, None)

    def lines(self):
        return [dict(sku=k, **v) for k, v in self.items.items()]

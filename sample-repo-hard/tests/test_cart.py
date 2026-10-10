from shop.cart import Cart


def test_add_and_remove():
    c = Cart()
    c.add("A", 5.0, 2)
    c.add("A", 5.0, 1)
    assert c.items["A"]["qty"] == 3
    c.remove("A")
    assert c.lines() == []

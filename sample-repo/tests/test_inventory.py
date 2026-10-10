from shop.inventory import in_stock


def test_in_stock():
    assert in_stock("AB123456")
    assert not in_stock("CD654321")

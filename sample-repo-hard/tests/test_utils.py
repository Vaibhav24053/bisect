from shop.utils import *  # noqa

def test_format_price():
    assert format_price(5) == "$5.00"


def test_slugify():
    assert slugify("Red Shoes XL") == "red-shoes-xl"


def test_clamp():
    assert clamp(15, 0, 10) == 10
    assert clamp(-1, 0, 10) == 0


def test_parse_qty():
    assert parse_qty("4") == 4


def test_truncate():
    assert truncate("abcdef", 4) == "abc~"


def test_is_valid_sku():
    assert is_valid_sku("AB123456")
    assert not is_valid_sku("bad")


def test_chunk():
    assert chunk([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]


def test_unique():
    assert unique([1, 2, 1, 3, 2]) == [1, 2, 3]


def test_flatten():
    assert flatten([[1], [2, 3]]) == [1, 2, 3]


def test_title_case():
    assert title_case("red SHOES") == "Red Shoes"


def test_percent():
    assert percent(1, 4) == 25.0
    assert percent(1, 0) == 0.0


def test_initials():
    assert initials("ada lovelace") == "AL"

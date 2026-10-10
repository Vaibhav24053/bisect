#!/usr/bin/env python3
"""Generates a small Python repo (~40 commits) with ONE planted regression.

Usage:  python3 make_sample_repo.py [target_dir] [--scenario easy|hard]
Then:   cd sample-repo && pip install pytest && python3 -m pytest -q

The failing test is tests/test_discounts.py::test_bulk_discount_at_threshold.
The commit that breaks it is recorded in ../planted_bug.txt (outside the repo,
so Bisect can't "cheat" by reading it).
"""
import os
import subprocess
import sys

import argparse

_ap = argparse.ArgumentParser()
_ap.add_argument("target", nargs="?", default="sample-repo")
_ap.add_argument("--force", action="store_true", help="replace target if it already exists")
_ap.add_argument("--scenario", choices=["easy", "hard"], default="easy",
                 help="easy: one-character regression. hard: one big refactor commit "
                      "hiding TWO regressions, plus a later feature that depends on it.")
_args = _ap.parse_args()
TARGET = _args.target
SCENARIO = _args.scenario
FORCE = _args.force

# ---- small utility functions: (name, code, test) --------------------------
UTILS = {
    "format_price": (
        'def format_price(amount):\n    return "$%.2f" % amount\n',
        'def test_format_price():\n    assert format_price(5) == "$5.00"\n',
    ),
    "slugify": (
        'def slugify(text):\n    return "-".join(text.lower().split())\n',
        'def test_slugify():\n    assert slugify("Red Shoes XL") == "red-shoes-xl"\n',
    ),
    "clamp": (
        'def clamp(x, lo, hi):\n    return max(lo, min(hi, x))\n',
        'def test_clamp():\n    assert clamp(15, 0, 10) == 10\n    assert clamp(-1, 0, 10) == 0\n',
    ),
    "parse_qty": (
        'def parse_qty(s):\n    n = int(s)\n    if n < 0:\n        raise ValueError("negative quantity")\n    return n\n',
        'def test_parse_qty():\n    assert parse_qty("4") == 4\n',
    ),
    "truncate": (
        'def truncate(s, n):\n    return s if len(s) <= n else s[: n - 1] + "~"\n',
        'def test_truncate():\n    assert truncate("abcdef", 4) == "abc~"\n',
    ),
    "is_valid_sku": (
        'def is_valid_sku(s):\n    return len(s) == 8 and s.isalnum()\n',
        'def test_is_valid_sku():\n    assert is_valid_sku("AB123456")\n    assert not is_valid_sku("bad")\n',
    ),
    "chunk": (
        'def chunk(xs, n):\n    return [xs[i : i + n] for i in range(0, len(xs), n)]\n',
        'def test_chunk():\n    assert chunk([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]\n',
    ),
    "unique": (
        'def unique(xs):\n    seen = set()\n    return [x for x in xs if not (x in seen or seen.add(x))]\n',
        'def test_unique():\n    assert unique([1, 2, 1, 3, 2]) == [1, 2, 3]\n',
    ),
    "flatten": (
        'def flatten(xss):\n    return [x for xs in xss for x in xs]\n',
        'def test_flatten():\n    assert flatten([[1], [2, 3]]) == [1, 2, 3]\n',
    ),
    "title_case": (
        'def title_case(s):\n    return " ".join(w.capitalize() for w in s.split())\n',
        'def test_title_case():\n    assert title_case("red SHOES") == "Red Shoes"\n',
    ),
    "percent": (
        'def percent(part, whole):\n    return 0.0 if whole == 0 else round(100.0 * part / whole, 1)\n',
        'def test_percent():\n    assert percent(1, 4) == 25.0\n    assert percent(1, 0) == 0.0\n',
    ),
    "initials": (
        'def initials(name):\n    return "".join(w[0].upper() for w in name.split())\n',
        'def test_initials():\n    assert initials("ada lovelace") == "AL"\n',
    ),
}


def util_commit(name):
    code, test = UTILS[name]
    return (
        "feat(utils): add %s" % name,
        {
            "shop/utils.py": ("a", "\n\n" + code),
            "tests/test_utils.py": ("a", "\n\n" + test),
        },
    )


# ---- fixed file contents ---------------------------------------------------
# Simulates a slow per-commit build/install step. Off by default; turn it on
# with the SIM_BUILD_SECS environment variable when you run the tests.
CONFTEST = '''import os
import time


def pytest_sessionstart(session):
    time.sleep(float(os.environ.get("SIM_BUILD_SECS", "0")))
'''

DISCOUNTS_V1 = '''"""Discount rules."""

BULK_THRESHOLD = 10   # buy 10 or more of one item -> bulk discount
BULK_RATE = 0.10


def bulk_discount(qty, unit_price):
    if qty >= BULK_THRESHOLD:
        return round(qty * unit_price * BULK_RATE, 2)
    return 0.0
'''

# decoy: harmless change that also touches discounts.py
DISCOUNTS_V2 = DISCOUNTS_V1.replace(
    '"""Discount rules."""',
    '"""Discount rules.\n\nAll amounts are in dollars, rounded to cents.\n"""',
)

# THE PLANTED BUG: a "simplifying refactor" that quietly turns >= into >
DISCOUNTS_V3 = '''"""Discount rules.

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
'''

TEST_DISCOUNTS = '''from shop.discounts import bulk_discount


def test_bulk_discount_at_threshold():
    # exactly 10 units of a $100 item -> 10% off the $1000 line
    assert bulk_discount(10, 100.0) == 100.0


def test_no_bulk_discount_below_threshold():
    assert bulk_discount(9, 100.0) == 0.0
'''

CART = '''class Cart:
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
'''

TEST_CART = '''from shop.cart import Cart


def test_add_and_remove():
    c = Cart()
    c.add("A", 5.0, 2)
    c.add("A", 5.0, 1)
    assert c.items["A"]["qty"] == 3
    c.remove("A")
    assert c.lines() == []
'''

PRICING = '''TAX_RATE = 0.18


def subtotal(lines):
    return round(sum(l["price"] * l["qty"] for l in lines), 2)
'''

PRICING_TAX = PRICING + '''

def with_tax(amount):
    return round(amount * (1 + TAX_RATE), 2)
'''

TEST_PRICING = '''from shop.pricing import subtotal


def test_subtotal():
    assert subtotal([{"price": 2.5, "qty": 4}]) == 10.0
'''

TEST_PRICING_TAX = TEST_PRICING.replace(
    "import subtotal", "import subtotal, with_tax"
) + '''

def test_with_tax():
    assert with_tax(100.0) == 118.0
'''

INVENTORY = '''STOCK = {"AB123456": 5, "CD654321": 0}


def in_stock(sku):
    return STOCK.get(sku, 0) > 0
'''

TEST_INVENTORY = '''from shop.inventory import in_stock


def test_in_stock():
    assert in_stock("AB123456")
    assert not in_stock("CD654321")
'''

CHECKOUT = '''from shop.pricing import subtotal, with_tax
from shop.discounts import bulk_discount


def order_total(lines):
    gross = subtotal(lines)
    off = sum(bulk_discount(l["qty"], l["price"]) for l in lines)
    return with_tax(round(gross - off, 2))
'''

TEST_CHECKOUT = '''from shop.checkout import order_total


def test_order_total_small_order():
    assert order_total([{"price": 10.0, "qty": 3}]) == 35.4


def test_order_total_large_order():
    # 12 units: bulk discount applies either side of the threshold
    assert order_total([{"price": 10.0, "qty": 12}]) == 127.44
'''

# ---- commit list (order matters) -------------------------------------------
COMMITS = [
    ("chore: project scaffold", {
        "README.md": ("w", "# Mini Shop\n\nA tiny cart/pricing library.\n"),
        "shop/__init__.py": ("w", ""),
        "tests/__init__.py": ("w", ""),
        "shop/utils.py": ("w", '"""Small helpers."""'),
        "tests/test_utils.py": ("w", "from shop.utils import *  # noqa"),
        "tests/test_smoke.py": ("w", "def test_import():\n    import shop  # noqa\n"),
        "conftest.py": ("w", CONFTEST),
        "pytest.ini": ("w", "[pytest]\ntestpaths = tests\n"),
        ".gitignore": ("w", "__pycache__/\n.pytest_cache/\n.venv/\n"),
    }),
    util_commit("format_price"),
    ("feat: add Cart", {"shop/cart.py": ("w", CART)}),
    ("test: cart add/remove", {"tests/test_cart.py": ("w", TEST_CART)}),
    ("feat: subtotal pricing", {"shop/pricing.py": ("w", PRICING)}),
    ("test: subtotal", {"tests/test_pricing.py": ("w", TEST_PRICING)}),
    util_commit("slugify"),
    util_commit("clamp"),
    ("docs: usage notes", {"README.md": ("a", "\n## Usage\n\nSee tests/ for examples.\n")}),
    ("feat: tax calculation", {"shop/pricing.py": ("w", PRICING_TAX)}),
    ("test: tax", {"tests/test_pricing.py": ("w", TEST_PRICING_TAX)}),
    ("feat: bulk discount", {"shop/discounts.py": ("w", DISCOUNTS_V1)}),
    ("test: bulk discount threshold", {"tests/test_discounts.py": ("w", TEST_DISCOUNTS)}),
    util_commit("parse_qty"),
    ("style: document discount units", {"shop/discounts.py": ("w", DISCOUNTS_V2)}),
    util_commit("truncate"),
    ("feat: inventory", {"shop/inventory.py": ("w", INVENTORY)}),
    ("test: inventory", {"tests/test_inventory.py": ("w", TEST_INVENTORY)}),
    util_commit("is_valid_sku"),
    ("docs: describe modules", {"README.md": ("a", "\nModules: cart, pricing, discounts, inventory.\n")}),
    util_commit("chunk"),
    util_commit("unique"),
    ("feat: checkout order_total", {"shop/checkout.py": ("w", CHECKOUT)}),
    ("test: checkout totals", {"tests/test_checkout.py": ("w", TEST_CHECKOUT)}),
    util_commit("flatten"),
    ("chore: bump version", {"shop/__init__.py": ("w", '__version__ = "0.2.0"\n')}),
    ("refactor: simplify discount helpers", {"shop/discounts.py": ("w", DISCOUNTS_V3)}),  # <-- BUG
    util_commit("title_case"),
    util_commit("percent"),
    ("docs: changelog", {"CHANGELOG.md": ("w", "# Changelog\n\n- 0.2.0 discounts refactor, checkout\n")}),
    util_commit("initials"),
    ("chore: tidy gitignore", {".gitignore": ("a", ".DS_Store\n")}),
    ("docs: contributing", {"CONTRIBUTING.md": ("w", "Run `pytest` before pushing.\n")}),
    ("chore: bump version", {"shop/__init__.py": ("w", '__version__ = "0.2.1"\n')}),
    ("docs: readme badges", {"README.md": ("a", "\n_status: alpha_\n")}),
]
BUG_MESSAGE = "refactor: simplify discount helpers"

# ---- HARD scenario: one refactor commit hiding two regressions -------------
CHECKOUT_V2 = '''from shop.pricing import with_tax
from shop.discounts import bulk_discount


def line_total(line):
    """Taxed total for one cart line."""
    base = line["price"] * line["qty"]
    return with_tax(round(base - bulk_discount(line["qty"], line["price"]), 2))


def order_total(lines):
    return round(sum(line_total(l) for l in lines), 2)
'''

ROUNDING_TEST = '''

def test_order_total_rounds_tax_once():
    # three 10-cent lines: tax is applied to the 30-cent total, then rounded once
    assert order_total([{"price": 0.10, "qty": 1}] * 3) == 0.35
'''

INVOICE = '''from shop.checkout import line_total
from shop.utils import format_price


def invoice_lines(lines):
    return ["%s x%d  %s" % (l["sku"], l["qty"], format_price(line_total(l))) for l in lines]
'''

TEST_INVOICE = '''from shop.invoice import invoice_lines


def test_invoice_lines():
    assert invoice_lines([{"sku": "A", "price": 10.0, "qty": 3}]) == ["A x3  $35.40"]
'''


def apply_scenario(commits):
    global BUG_MESSAGE
    if SCENARIO != "hard":
        return commits
    BUG_MESSAGE = "refactor: per-line totals and simplify discounts"
    out = []
    for msg, files in commits:
        if msg == "refactor: simplify discount helpers":
            out.append((BUG_MESSAGE, {"shop/discounts.py": ("w", DISCOUNTS_V3),
                                      "shop/checkout.py": ("w", CHECKOUT_V2)}))
            continue
        out.append((msg, files))
        if msg == "test: checkout totals":
            out.append(("test: checkout rounding", {"tests/test_checkout.py": ("a", ROUNDING_TEST)}))
        if msg == "feat(utils): add title_case":
            out.append(("feat: invoice lines", {"shop/invoice.py": ("w", INVOICE)}))
            out.append(("test: invoice lines", {"tests/test_invoice.py": ("w", TEST_INVOICE)}))
    return out



def run(*args):
    return subprocess.run(args, cwd=TARGET, check=True, capture_output=True, text=True).stdout.strip()


def main():
    if os.path.exists(TARGET):
        if FORCE:
            import shutil
            shutil.rmtree(TARGET)
        else:
            sys.exit("%s already exists. Delete it or pick another folder." % TARGET)
    os.makedirs(TARGET)
    run("git", "init", "-q")
    run("git", "config", "user.name", "Sample Dev")
    run("git", "config", "user.email", "dev@example.com")
    bug_hash = None
    commits = apply_scenario(COMMITS)
    for i, (msg, files) in enumerate(commits, 1):
        for path, (mode, text) in files.items():
            full = os.path.join(TARGET, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, mode) as f:
                f.write(text)
        run("git", "add", "-A")
        date = "2026-08-%02dT12:00:00" % min(i, 28)
        env = dict(os.environ, GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
        subprocess.run(["git", "commit", "-q", "-m", msg], cwd=TARGET, check=True, env=env)
        if msg == BUG_MESSAGE:
            bug_hash = run("git", "rev-parse", "HEAD")
    first = run("git", "rev-list", "--max-parents=0", "HEAD")
    out = os.path.join(os.path.dirname(os.path.abspath(TARGET)), "planted_bug.txt")
    with open(out, "w") as f:
        f.write("planted bug commit: %s\nmessage: %s\n" % (bug_hash, BUG_MESSAGE))
    print("Created %s (%s scenario) with %d commits." % (TARGET, SCENARIO, len(commits)))
    print("Known good: %s   Known bad: HEAD" % first[:8])
    print("Answer key saved to %s (don't peek until Bisect finds it)" % out)


main()

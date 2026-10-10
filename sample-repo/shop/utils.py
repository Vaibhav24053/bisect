"""Small helpers."""

def format_price(amount):
    return "$%.2f" % amount


def slugify(text):
    return "-".join(text.lower().split())


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def parse_qty(s):
    n = int(s)
    if n < 0:
        raise ValueError("negative quantity")
    return n


def truncate(s, n):
    return s if len(s) <= n else s[: n - 1] + "~"


def is_valid_sku(s):
    return len(s) == 8 and s.isalnum()


def chunk(xs, n):
    return [xs[i : i + n] for i in range(0, len(xs), n)]


def unique(xs):
    seen = set()
    return [x for x in xs if not (x in seen or seen.add(x))]


def flatten(xss):
    return [x for xs in xss for x in xs]


def title_case(s):
    return " ".join(w.capitalize() for w in s.split())


def percent(part, whole):
    return 0.0 if whole == 0 else round(100.0 * part / whole, 1)


def initials(name):
    return "".join(w[0].upper() for w in name.split())

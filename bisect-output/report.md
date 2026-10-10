# Bisect report

- Culprit: `19d27bd refactor: per-line totals and simplify discounts`
- Commits searched: 38 in 2 rounds / 11 test runs (7.0s)
- Classic sequential bisect, same harness: 6 runs (19.9s)
- Diagnosis attempts: 1, tokens by model: {"nvidia/Nemotron-3_5-Lightning": 7577}

## Root cause
Two bugs were introduced in commit 19d27bd:

1. **`shop/discounts.py`**: The bulk discount threshold changed from `qty >= BULK_THRESHOLD` to `qty > BULK_THRESHOLD`, so `bulk_discount(10, 100.0)` now returns 0.0 instead of 100.0, failing `test_bulk_discount_at_threshold`.

2. **`shop/checkout.py`**: `order_total` now applies tax per-line via `line_total` and then sums, rather than applying tax once to the total gross minus discounts. This causes `test_order_total_rounds_tax_once` to fail (0.36 vs expected 0.35) because tax gets rounded three times instead of once.

The fixes are: (a) change `qty > BULK_THRESHOLD` back to `qty >= BULK_THRESHOLD` in `bulk_discount`, and (b) restore the original `order_total` logic that applies `with_tax` once to the subtotal minus total discount.

## Verified fix (model: nvidia/Nemotron-3_5-Lightning)
```diff
diff --git a/shop/checkout.py b/shop/checkout.py
index aa1f7a7..6807cff 100644
--- a/shop/checkout.py
+++ b/shop/checkout.py
@@ -1,4 +1,4 @@
-from shop.pricing import with_tax
+from shop.pricing import subtotal, with_tax
 from shop.discounts import bulk_discount
 
 
@@ -9,4 +9,6 @@ def line_total(line):
 
 
 def order_total(lines):
-    return round(sum(line_total(l) for l in lines), 2)
+    gross = subtotal(lines)
+    off = sum(bulk_discount(l["qty"], l["price"]) for l in lines)
+    return with_tax(round(gross - off, 2))
diff --git a/shop/discounts.py b/shop/discounts.py
index 09bfcf8..53478a1 100644
--- a/shop/discounts.py
+++ b/shop/discounts.py
@@ -13,7 +13,7 @@ def _pct(amount, rate):
 
 
 def bulk_discount(qty, unit_price):
-    if qty > BULK_THRESHOLD:
+    if qty >= BULK_THRESHOLD:
         return _pct(qty * unit_price, BULK_RATE)
     return 0.0
 

```

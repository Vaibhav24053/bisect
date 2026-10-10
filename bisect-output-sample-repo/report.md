# Bisect report

- Culprit: `2dfbf08 refactor: simplify discount helpers`
- Commits searched: 35 in 2 rounds / 10 test runs (1.1s)
- Classic sequential bisect, same harness: 5 runs (1.3s)
- Diagnosis attempts: 1, tokens by model: {"nvidia/Nemotron-3_5-Lightning": 3482}

## Root cause
The commit changed the bulk discount threshold condition from `>=` to `>`, making it "more than 10" instead of "10 or more". The test `test_bulk_discount_at_threshold` expects that exactly 10 units of a $100 item yields a $100 discount (10% of $1000). Restoring the `>=` operator fixes the test while keeping all other behavior intact.

## Verified fix (model: nvidia/Nemotron-3_5-Lightning)
```diff
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

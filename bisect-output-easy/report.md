# Bisect report

- Culprit: `2dfbf08 refactor: simplify discount helpers`
- Attempts used: 1
- Tokens used: 1861  (3.6s)

## Root cause
The commit changed the bulk_discount condition from `qty >= BULK_THRESHOLD` to `qty > BULK_THRESHOLD`, making the threshold exclusive. The test expects a discount when exactly 10 units are purchased, so the condition must be restored to `>=`.

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

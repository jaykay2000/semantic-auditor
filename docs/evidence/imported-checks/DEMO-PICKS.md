# Demo picks, written before their conversion results were seen (2026-10-31)

- **(a) F01 / K1, the free-shipping email:** `C1#04` (C1's F5, "Email (current) shows delivery as $0.00 AND a
  -$15.00 promotion; summary doesn't add up"), the first F01 finding in held-out order. If it does not convert, that
  is reported as is, beside the conversion outcome of every other F01 agent finding in the held-out set
  (C2#00, X1#03, X2#04, M2#01, M2#02, M3#01); no other F01 finding is swapped in silently.
- **(b) intentionally unsupported:** `C2#11` (C2's F11, "fulfilled" email for a mixed order), which needs the store
  operator to fulfil part of an order: there is no adapter verb for that. Expected `adapter_gap`; anything else is
  reported as a converter failure.

Both are held-out findings: the converter (frozen at `b6d672b`) was never developed against them.

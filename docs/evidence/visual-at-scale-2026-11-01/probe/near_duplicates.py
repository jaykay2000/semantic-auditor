"""Group the sent crops into near-duplicates (method fixed before it was computed): two crops are one group when
their sha256 is equal, or when the claimed text is the same and their 64x64 grayscale versions differ by less than
3/255 on average. Prints one row per sent crop with its group id.

    python near_duplicates.py <items.json>     # [{"app", "issue", "quote", "crop": path, "sha256"}, ...]
"""
import json
import sys

from PIL import Image, ImageChops, ImageStat

items = json.load(open(sys.argv[1]))
small = [Image.open(it["crop"]).convert("L").resize((64, 64)) for it in items]
parent = list(range(len(items)))


def root(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


for a in range(len(items)):
    for b in range(a + 1, len(items)):
        A, B = items[a], items[b]
        if A["sha256"] == B["sha256"] or (A["quote"] == B["quote"] and
                                          ImageStat.Stat(ImageChops.difference(small[a], small[b])).mean[0] < 3):
            parent[root(a)] = root(b)
print(json.dumps([{"app": it["app"], "issue": it["issue"], "sha256": it["sha256"], "group": root(k)}
                  for k, it in enumerate(items)], indent=0))

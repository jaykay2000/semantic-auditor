# Can Muse Spark Open read a screenshot? (2026-11-01)

**Result: yes, 3 of 3 exactly right. Cost $0.0048.**

| Seed | Line amount | Subtotal | Tax | Total | Exact | Prompt / completion tokens | Cost |
|---|---|---|---|---|---|---|---|
| 1 | $43.19 | $39.99 | $3.60 | $48.59 | yes | 376 / 315 | $0.00181 |
| 2 | $43.19 | $39.99 | $3.60 | $48.59 | yes | 376 / 233 | $0.00146 |
| 3 | $43.19 | $39.99 | $3.60 | $48.59 | yes | 376 / 260 | $0.00158 |

- **Image:** Ana's order-placed page from the Spree run `spree-scale-2t` (beta3, `ana__S-buy` step s09; the
  path and sha256 are in `result.json`). Cropped to the Order Items card (page px 140,380 to 692,690, the same box
  the v9 frame uses), then fitted inside 512 x 512: 512 x 288, a 20,705-byte PNG. That is `crop.png`, byte for byte what was sent.
- **Path:** SRA's own `Router.complete` with the built-in `baseten` provider, model
  `meta-models/muse-spark-open-1026`, reasoning effort low, a strict JSON schema, seeds 1, 2 and 3, `fresh=True`.
  The image went as an OpenAI-style `image_url` content part with a base64 `data:` URL. `result.json` has the
  request shape with the image elided (its byte count and sha256 kept), every reply and its usage.
- **What the prompt said:** only which four figures to read. No figure appears in the prompt, so every number in a
  reply came from the image.
- **Key:** never printed. The key was checked to be absent from `result.json` and `ledger.jsonl`.
- **Not shown by this:** that the model reads every page this well. One clean crop, one page, three seeds.

Re-run (spends about $0.005): `python docs/evidence/visual-probe-2026-11-01/probe/probe.py <root with .env and a
[roles.vision] baseten entry> <out dir>`.

"""Step 1: can Muse Spark Open read a screenshot? Three seeded calls through SRA's Router (baseten provider)."""
import base64
import hashlib
import io
import json
import os
import pathlib
import sys

from PIL import Image

SRA = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(SRA / "src"))
from semaudit.models.router import Router  # noqa: E402

ROOT, OUT = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
RUN = pathlib.Path(os.environ.get("SPREE_RUN", SRA.parent / "spree-semaudit/runs/spree-scale-2t"))
SHOT = "captures/v6.0.0.beta3/ana__S-buy/v6.0.0.beta3.ana.S-buy.s09.c01.screenshot.png"
BOX = (140, 380, 692, 690)   # extract_v9.ORDER_BOX: the Order Items card
src = Image.open(RUN / SHOT)
crop = src.crop(BOX)
crop.thumbnail((512, 512))
buf = io.BytesIO()
crop.convert("RGB").save(buf, "PNG")
png = buf.getvalue()
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "crop.png").write_bytes(png)
url = "data:image/png;base64," + base64.b64encode(png).decode()
schema = {"type": "object", "additionalProperties": False,
          "required": ["line_amount", "subtotal", "tax", "total"],
          "properties": {k: {"type": "string"} for k in ("line_amount", "subtotal", "tax", "total")}}
q = ("This is a crop of an order confirmation page. Read, exactly as printed, the amount on the item line, "
     "the Subtotal, the Tax and the Total. Answer as JSON with the dollar sign, e.g. \"$1.00\".")
messages = [{"role": "user", "content": [{"type": "text", "text": q}, {"type": "image_url", "image_url": {"url": url}}]}]
want = {"line_amount": "$43.19", "subtotal": "$39.99", "tax": "$3.60", "total": "$48.59"}
r = Router(root=ROOT, max_usd=0.30)
rows = []
for seed in (1, 2, 3):
    try:
        res = r.complete("vision", messages, schema=schema, schema_name="order_summary", seed=seed, fresh=True)
        got = res.parsed
        rows.append({"seed": seed, "ok": True, "reply": got, "exact": got == want, "usage": res.usage,
                     "cost_usd": res.cost_usd, "latency_s": round(res.latency_s, 1),
                     "finish_reason": res.raw["choices"][0].get("finish_reason")})
    except Exception as e:
        rows.append({"seed": seed, "ok": False, "error": str(e)[:600]})
    print(json.dumps(rows[-1]))
shape = json.loads(json.dumps({"model": "meta-models/muse-spark-open-1026", "reasoning_effort": "low",
                               "messages": messages, "response_format": {"type": "json_schema",
                               "json_schema": {"name": "order_summary", "schema": schema, "strict": True}},
                               "seed": "1 | 2 | 3", "max_completion_tokens": 16000}))
shape["messages"][0]["content"][1]["image_url"]["url"] = f"data:image/png;base64,<{len(png)} bytes elided, sha256 {hashlib.sha256(png).hexdigest()}>"
rec = {"date": "2026-11-01", "provider": "baseten (SRA Router, built-in provider)", "endpoint": "POST https://inference.baseten.co/v1/chat/completions",
       "source": {"run": "spree-semaudit/runs/spree-scale-2t", "screenshot": SHOT,
                  "screenshot_sha256": hashlib.sha256((RUN / SHOT).read_bytes()).hexdigest(),
                  "screenshot_size": list(src.size), "crop_box_px": list(BOX), "sent_size": list(crop.size),
                  "sent_png_bytes": len(png), "sent_sha256": hashlib.sha256(png).hexdigest()},
       "request_shape": shape, "expected": want, "replies": rows,
       "exact": sum(1 for x in rows if x.get("exact")), "of": len(rows),
       "cost_usd": round(sum(x.get("cost_usd") or 0 for x in rows), 6),
       "tokens": {"prompt": sum(x.get("usage", {}).get("prompt_tokens", 0) for x in rows),
                  "completion": sum(x.get("usage", {}).get("completion_tokens", 0) for x in rows)}}
(OUT / "result.json").write_text(json.dumps(rec, indent=1) + "\n")
print("EXACT", rec["exact"], "of", rec["of"], "cost", rec["cost_usd"], rec["tokens"])

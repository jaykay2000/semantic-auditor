"""W1: verify Meta Model API capabilities by real calls, not assumptions.

Run from the repo root:  python3 scripts/w1_smoke.py
Writes runs/w1/report.json. Never prints the API key.
"""

from __future__ import annotations

import base64
import io
import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from semaudit.models.router import PROVIDERS, ModelError, Router  # noqa: E402

DIRECTIVE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["message_kind", "decision", "action", "strength", "urgency_cue",
                 "explains_own_tradeoff"],
    "properties": {
        "message_kind": {"type": "string", "enum": ["information", "directive", "retrospective"]},
        "decision": {"type": "string", "enum": ["when_to_book", "fare_type", "none"]},
        "action": {"type": "string", "enum": ["book_now", "lock_fare", "wait_for_drop", "set_alert",
                                               "choose_refundable", "choose_non_refundable",
                                               "upgrade_to_refundable", "none", "other"]},
        "strength": {"type": "string", "enum": ["inform", "suggest", "urge", "require"]},
        "urgency_cue": {"type": "string", "enum": ["U-a", "U-b", "U-c", "none"]},
        "explains_own_tradeoff": {"type": "boolean"},
    },
}

RUBRIC = """Classify one product message shown to a traveller.
strength: 'urge' if ANY cue is present: U-a an immediacy word attached to the action ("now", "today",
"right away", "before it's gone", "don't miss"); U-b a countdown or a deadline of <=24 h attached to the
primary action; U-c scarcity coupled to an imperative in the same sentence. Otherwise 'require' if the
traveller cannot continue without acting; 'suggest' for an optional or conditional offer of an action;
'inform' for a fact with no recommended action. Report the cue you relied on (or 'none').
message_kind: 'retrospective' if it judges a choice already made; 'directive' if it recommends an action;
else 'information'. action: the PRIMARY recommended action. explains_own_tradeoff: true only if the
message itself weighs its own recommendation against an alternative."""

CASES = {  # canonical copy keys -> expected (from examples/northbound/README.md)
    "fl.banner": ("2 seats left at this fare. Lock it for 48 h for €9 total, for your whole booking.",
                  {"action": "lock_fare", "strength": "suggest", "explains_own_tradeoff": False}),
    "fl.banner.urgent": ("Departing soon: only 2 seats left at this fare. Book now, or lock it for 12 h "
                         "for €9 total if your plans might change.",
                         {"action": "book_now", "strength": "urge", "explains_own_tradeoff": True}),
    "fl.banner.urgent_bare": ("Only 2 seats left. Book now.",
                              {"action": "book_now", "strength": "urge", "explains_own_tradeoff": False}),
    "pw.email.after": ("Keep waiting to book. We'll tell you when prices drop.",
                       {"action": "wait_for_drop", "strength": "suggest"}),
    "cg.regret": ("You should have booked a refundable fare.", {"message_kind": "retrospective"}),
}


def check(name, fn, report):
    t0 = time.monotonic()
    try:
        out = fn()
        report[name] = {"ok": True, **out, "seconds": round(time.monotonic() - t0, 2)}
    except (ModelError, httpx.HTTPError, KeyError, ValueError) as e:
        report[name] = {"ok": False, "error": str(e)[:600], "seconds": round(time.monotonic() - t0, 2)}
    print(f"{'PASS' if report[name]['ok'] else 'FAIL'}  {name}")


def main() -> int:
    router = Router(root=ROOT, max_usd=1.50)
    report: dict = {}

    def models():
        r = httpx.get(f"{PROVIDERS['meta']['base_url']}/models",
                      headers={"Authorization": f"Bearer {router._key('meta')}"}, timeout=30)
        r.raise_for_status()
        return {"models": sorted(m.get("id") for m in r.json().get("data", []))}

    def text():
        r = router.complete("smoke", [{"role": "user", "content": "Reply with the single word: ready"}],
                            fresh=True)
        return {"model": r.model, "content": r.content[:80], "usage": r.usage, "cost_usd": r.cost_usd}

    def structured(effort):
        def run():
            rows, cost, out_tokens = {}, 0.0, 0
            for key, (copy, expected) in CASES.items():
                r = router.complete("extractor", [{"role": "system", "content": RUBRIC},
                                                  {"role": "user", "content": copy}],
                                    schema=DIRECTIVE_SCHEMA, schema_name="directive",
                                    reasoning_effort=effort, fresh=True)
                got = r.parsed
                rows[key] = {"got": got, "matches": all(got.get(k) == v for k, v in expected.items())}
                cost += r.cost_usd or 0
                out_tokens += r.usage.get("completion_tokens", 0)
            return {"effort": effort, "all_match": all(v["matches"] for v in rows.values()),
                    "rows": rows, "cost_usd": round(cost, 5), "completion_tokens": out_tokens}
        return run

    def image():
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (900, 120), "white")
        ImageDraw.Draw(img).text((20, 45), "2 seats left at this fare. Lock it for 48 h for EUR 9 total.",
                                 fill="black")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        url = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
        r = router.complete("smoke", [{"role": "user", "content": [
            {"type": "text", "text": "Transcribe the text in this image exactly."},
            {"type": "image_url", "image_url": {"url": url}}]}], fresh=True)
        return {"content": r.content[:200], "usage": r.usage, "cost_usd": r.cost_usd}

    def tools():
        tool = {"type": "function", "function": {
            "name": "get_inventory", "description": "Seats left for a fare",
            "parameters": {"type": "object", "properties": {"fare_id": {"type": "string"}},
                           "required": ["fare_id"], "additionalProperties": False}}}
        r = router.complete("smoke", [{"role": "user",
                                       "content": "How many seats are left on fare LISBER-07? Use the tool."}],
                            tools=[tool], fresh=True)
        calls = r.raw["choices"][0]["message"].get("tool_calls") or []
        return {"tool_calls": [c["function"] for c in calls], "usage": r.usage}

    def second_model():
        r = router.complete("cross_checker_extract",
                            [{"role": "user", "content": "Reply with the single word: ready"}], fresh=True)
        return {"model": r.model, "content": r.content[:80]}

    check("list_models", models, report)
    check("text_minimal_effort", text, report)
    check("structured_low", structured("low"), report)
    check("structured_medium", structured("medium"), report)
    check("image_input", image, report)
    check("tool_calling", tools, report)
    check("second_model_1_2", second_model, report)
    report["spent_usd"] = round(router.spent_usd, 5)

    out = ROOT / "runs" / "w1"
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"spent ${router.spent_usd:.4f}; report at runs/w1/report.json")
    return 0 if all(v.get("ok") for v in report.values() if isinstance(v, dict)) else 1


if __name__ == "__main__":
    sys.exit(main())

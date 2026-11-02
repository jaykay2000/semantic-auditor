"""Mutated controls for `semaudit visual`: the same crop as a real issue, with the claimed value changed to a plausible
wrong one. Written and fixed before any model call of this experiment; no model is called here.

Rule, per eligible issue (`visual.basis_of` is not None and `visual.target` finds a web capture):
1. The figures in the claimed quote, in order: a currency amount (`$43.19`, `€9`) or a bare number (`2`, `12`, `48`).
2. The figures on the same page: every event in the review whose capture has the same screenshot file, in the
   review's persona/event order, figures in reading order.
3. For the first quoted figure that has one: replace it (its first occurrence) with the first same-page figure of the
   same kind (same currency sign, or both bare) whose value differs from it and from every figure in the quote.
   source = "same_page".
4. If no quoted figure has a same-page alternative: the first quoted figure + 1 (whole units, skipping values already
   in the quote). source = "plus_one".
5. If the quote has no figure: no control (source = "none").

    python make_controls.py <review.json> <controls.json>
"""
import json
import re
import sys
from pathlib import Path

from semaudit.verify import visual as V

FIG = re.compile(r"(?:(?P<sign>[$€£])\s?)?(?P<num>\d[\d,]*(?:\.\d+)?)")


def figures(text: str) -> list[dict]:
    out = []
    for m in FIG.finditer(text or ""):
        out.append({"sign": m.group("sign") or "", "num": m.group("num"), "span": m.span(),
                    "value": float(m.group("num").replace(",", ""))})
    return out


def fmt(sign: str, value: float, like: str) -> str:
    if "." in like:
        decimals = len(like.split(".")[1])
        s = f"{value:,.{decimals}f}" if "," in like else f"{value:.{decimals}f}"
    else:
        s = f"{int(value):,}" if "," in like else str(int(value))
    return sign + s


def control_for(issue: dict, events: dict, all_events: list[dict]) -> dict | None:
    found = V.target(issue, events)
    if found is None:
        return None
    e, quote = found
    shot = (e.get("capture") or {}).get("screenshot")
    qf = figures(quote)
    rec = {"issue": issue["id"], "event": e.get("id"), "screenshot": shot, "real_quote": quote}
    if not qf:
        return {**rec, "control_quote": None, "source": "none"}
    quoted_values = {f["value"] for f in qf}
    page = [f for ev in all_events if (ev.get("capture") or {}).get("screenshot") == shot
            for f in figures(ev.get("text") or "")]
    for f in qf:
        for p in page:
            if p["sign"] == f["sign"] and p["value"] not in quoted_values:
                new = quote[:f["span"][0]] + p["sign"] + p["num"] + quote[f["span"][1]:]
                return {**rec, "control_quote": new, "source": "same_page", "replaced": quote[slice(*f["span"])],
                        "with": p["sign"] + p["num"]}
    f = qf[0]
    v = f["value"] + 1
    while v in quoted_values:
        v += 1
    rep = fmt(f["sign"], v, f["num"])
    new = quote[:f["span"][0]] + rep + quote[f["span"][1]:]
    return {**rec, "control_quote": new, "source": "plus_one", "replaced": quote[slice(*f["span"])], "with": rep}


def main(review_path: Path, out: Path) -> None:
    d = json.loads(review_path.read_text())
    all_events = [e for p in d.get("personas") or [] for e in p.get("events") or []]
    events = {(p["id"], e["id"]): e for p in d.get("personas") or [] for e in p.get("events") or []}
    rows = []
    for issue in d.get("issues") or []:
        if V.basis_of(issue) is None:
            continue
        c = control_for(issue, events, all_events)
        if c is not None:
            rows.append(c)
    out.write_text(json.dumps({"review": str(review_path.name), "controls": rows}, indent=1, ensure_ascii=False) + "\n")
    for r in rows:
        print(r["issue"], "|", r.get("replaced"), "->", r.get("with"), f"({r['source']})")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))

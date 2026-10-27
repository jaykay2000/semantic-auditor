"""Dev ground truth for the narrative fixture, from the hand-written expected status vectors.

The vectors in tests/fixtures/stories/*.json were written before the auditor ran on captures (W1b), from the
Northbound design in examples/northbound/README.md. This turns them into the benchmark's truth format so the
matcher and the baseline prompts can be developed on 2.4. Dev only: never a headline number.

  violated            -> an issue item
  excepted            -> a negative control, pattern exception_applies
  passed + explained  -> a negative control, pattern explained_tradeoff
  Theo's post-purchase offer (U3/U4 passed on cg.upgrade) -> negative control, actionable_post_purchase
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from semaudit.bench.findings import Target, Truth, TruthItem  # noqa: E402

OBJECTIVE = {"U1", "U2"}        # oracle-backed rules: claim vs inventory, fee charged vs displayed


def items_for(stem: str, fx: dict) -> list[TruthItem]:
    events = {e["id"]: e for e in fx["story"]["events"]}
    out = []
    for n, x in enumerate(fx["expected"]):
        subj, status, label = x["subject"], x["status"], x.get("label")
        if "@" in subj:
            pair, decision = subj.split("@", 1)
            target = Target(kind="relation", features=pair.split("|"), decision=decision.split(":")[0])
        elif subj == "story":
            target = Target(kind="story")
        else:
            e = events[subj]
            target = Target(kind="event", feature=e["feature"], surface=e["surface"], message_key=e["copy_key"])
        if status == "violated":
            kind, pattern = "issue", None
        elif status == "excepted":
            kind, pattern = "negative_control", "exception_applies"
        elif status == "passed" and label == "explained_tradeoff":
            kind, pattern = "negative_control", "explained_tradeoff"
        elif stem == "theo" and status == "passed" and target.kind == "event" and target.message_key == "cg.upgrade":
            kind, pattern = "negative_control", "actionable_post_purchase"
        else:
            continue
        out.append(TruthItem(id=f"{stem}-{n}", kind=kind, personas=[stem], rule=x["rule"], label=label,
                             target=target, pattern=pattern, objective=x["rule"] in OBJECTIVE))
    return out


def main() -> None:
    fixtures = {p.stem: json.loads(p.read_text()) for p in sorted((ROOT / "tests/fixtures/stories").glob("*.json"))
                if "gold" not in p.stem}
    for release, out_name in (("2.4", "northbound-2.4.truth.json"), ("2.4.1", "northbound-2.4.1.truth.json")):
        chosen = {s: f for s, f in fixtures.items() if f["story"]["release"] == release}
        stems = {s.removesuffix("_241"): f for s, f in chosen.items()}
        items = [i for s, f in sorted(stems.items()) for i in items_for(s, f)]
        t = Truth(release=release, items=items, personas=sorted(stems),
                  source="dev: tests/fixtures/stories expected vectors (hand-written, W1b); not a headline number")
        (ROOT / "bench/dev" / out_name).write_text(json.dumps(t.model_dump(), indent=1) + "\n")
        print(release, len(items), "items;", sum(i.kind == "issue" for i in items), "issues;",
              sorted(stems))


if __name__ == "__main__":
    main()

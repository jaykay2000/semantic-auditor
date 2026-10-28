"""Dev scale pilot (W13b step 4): does accuracy hold as stories grow? DEV ONLY, never a headline number.

Real releases carry far more messages per persona than the narrative fixture's 4-11 events. This pads each
hand-authored Northbound 2.4 story (tests/fixtures/stories, whose expected answers were written in W1b) with
rule-neutral in-app messages, at several scales, and runs both systems on the SAME padded stories:

  semaudit-core  the auditor's semantic core: extraction (deduplicated across stories), code rule evaluation, the
                 P2 interpreter. Its violated entries become findings mechanically. The verifier is not run: on the
                 sealed releases it removed nothing.
  B-judge-1      the frozen one-call baseline (bench/conditions/prompts/judge_one.md), unchanged.

Both are scored by the frozen matcher against the dev truth (bench/dev/northbound-2.4.truth.json). Padding changes no
answer BY CONSTRUCTION. Each pad message is plain information: no claim, no number, no recommendation, no
judgement of a past choice, on an in-app card (not a contact under the load rule), never user-initiated. So
every truth unit stays exactly as it was.

  python3 scripts/w13b_scale_pilot.py --scales 1,4,16 --max-usd 3 [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from semaudit.bench import judge  # noqa: E402
from semaudit.bench.findings import Cited, Finding, Findings, Target, Truth  # noqa: E402
from semaudit.bench.match import score  # noqa: E402
from semaudit.contract.schema import load_contract  # noqa: E402
from semaudit.extract.messages import extract_unique  # noqa: E402
from semaudit.models.router import ModelError, Router  # noqa: E402
from semaudit.relate.interpret import model_interpreter  # noqa: E402
from semaudit.relate.rules import evaluate  # noqa: E402
from semaudit.story.model import Event, Story  # noqa: E402

FIX = ROOT / "tests/fixtures/stories"
TRUTH = ROOT / "bench/dev/northbound-2.4.truth.json"
OUT = ROOT / "runs/w13b-scale-pilot"

# Rule-neutral by construction: information only, no claim, number, recommendation or retrospective judgement.
NEUTRAL = [
    "Trip details refreshed.", "You're viewing your saved trip.", "Your search is saved.",
    "Loading the seat map.", "This page was updated a moment ago.", "Your profile is up to date.",
    "Itinerary view: outbound and return.", "Your trip appears in Trips.", "Signed in.",
    "Display language: English.", "Map view is available on the next screen.", "Your session is active.",
    "Trip notes are private to you.", "Filters are reset.", "Results are sorted by departure time.",
    "Accessibility settings are on.", "This trip is shared with no one.", "Your preferences were loaded.",
    "Help is in the menu.", "Dark mode follows your device.", "Your recent searches are listed below.",
    "Terminal information appears on your boarding pass.", "Your trip timeline is shown in local time.",
    "Page loaded.",
]


def dev_stories(personas: list[str]) -> dict[str, Story]:
    out = {}
    for name in personas:
        raw = json.loads((FIX / f"{name}.json").read_text())["story"]
        out[name] = Story(**{**raw, "persona": name})       # the truth names personas by fixture stem
    return out


def pad(story: Story, k: int, rng: random.Random) -> Story:
    """Events in time order (one fixture lists an event out of order), then k-1 neutral messages inserted after
    each event, spaced before the next one. Scale 1 is the same story in time order, so every scale differs from
    scale 1 by the padding alone."""
    evs = sorted(story.events, key=lambda e: e.at)      # stable: equal times keep their authored order
    if k <= 1:
        return story.model_copy(update={"events": evs})
    events, n = [], 0
    for i, e in enumerate(evs):
        events.append(e)
        nxt = evs[i + 1].at if i + 1 < len(evs) else e.at + timedelta(minutes=10)
        gap = (nxt - e.at) / k
        last = next((x for x in reversed(events) if x.kind == "message"), None)
        for j in range(1, k):
            n += 1
            events.append(Event(id=f"nz{n:04d}", at=e.at + gap * j, kind="message", feature=None,
                                surface=last.surface if last else None, channel="card", component=None,
                                copy_key=f"noise.{n % len(NEUTRAL)}", text=rng.choice(NEUTRAL),
                                user_initiated=False))
    return story.model_copy(update={"events": events})


def core_findings(stories: dict[str, Story], contract, router: Router, rng_seed: str) -> Findings:
    msgs = [{"feature": e.feature, "channel": e.channel, "text": e.text} for s in stories.values() for e in s.messages()]
    ext = extract_unique(msgs, contract, router)
    out, n = [], 0
    for name, s in sorted(stories.items()):
        s = s.model_copy(deep=True)
        for e in s.messages():
            e.extraction = ext[(e.feature or "", e.channel or "", e.text)]
        by_id = {e.id: e for e in s.events}
        for x in evaluate(s, contract, model_interpreter(router, rng=random.Random(f"{rng_seed}:{name}"))):
            if x.status != "violated":
                continue
            n += 1
            if "@" in x.subject:
                pair, decision = x.subject.split("@", 1)
                target = Target(kind="relation", features=pair.split("|"), decision=decision.split(":")[0])
                cited = [i for p in x.meta.get("pairs", []) for i in p]
            elif x.subject == "story":
                target, cited = Target(kind="story"), list(x.meta.get("events", []))
            else:
                e = by_id[x.subject]
                target, cited = Target(kind="event", feature=e.feature, surface=e.surface,
                                       message_key=e.copy_key), [e.id]
            out.append(Finding(id=f"core-{n:03d}", personas=[name], rule=x.rule, label=x.label, target=target,
                               severity=contract.rule(x.rule).severity_for(x.label),
                               cited=[Cited(persona=name, event_id=i, quote=by_id[i].text or "")
                                      for i in dict.fromkeys(cited) if i in by_id]))
    return Findings(system="semaudit-core", release="2.4", findings=out, fresh=False)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scales", default="1,4,16")
    ap.add_argument("--max-usd", type=float, required=True)
    ap.add_argument("--dry-run", action="store_true", help="print sizes only, no model call")
    a = ap.parse_args()
    contract = load_contract(ROOT / "examples/northbound/contract")
    truth = Truth.model_validate(json.loads(TRUTH.read_text()))
    base = dev_stories(truth.personas)
    OUT.mkdir(parents=True, exist_ok=True)
    rows, left = [], a.max_usd
    for k in [int(x) for x in a.scales.split(",")]:
        stories = {n: pad(s, k, random.Random(f"pad:{k}:{n}")) for n, s in base.items()}
        events = sum(len(s.events) for s in stories.values())
        chars = len(json.dumps({"stories": [judge.render_story(s) for s in stories.values()]}, default=str))
        row = {"scale": k, "events": events, "baseline_input_chars": chars}
        print(f"x{k}: {events} events, baseline input {chars:,} chars (~{chars // 4:,} tokens)", flush=True)
        if a.dry_run:
            rows.append(row)
            continue
        for system in ("semaudit-core", "B-judge-1"):
            router = Router(ROOT, max_usd=left)
            router.tag = f"scale-pilot:{system}:x{k}"
            t0 = time.time()
            try:
                if system == "B-judge-1":
                    fs, _ = judge.judge_one(stories, contract, router, release="2.4")
                else:
                    fs = core_findings(stories, contract, router, f"x{k}")
            except ModelError as e:
                row[system] = {"status": f"not measured: {e}"}
                print(f"  {system}: not measured: {e}", flush=True)
                continue
            acc = router.accounting()
            left -= acc["spent_usd"]
            s = score(fs, truth)
            row[system] = {"tp": s["tp"], "fp": s["fp"], "fn": s["fn"], "spent_usd": acc["spent_usd"],
                           "if_fresh_usd": acc["if_fresh_usd"], "calls": acc["calls"], "cached": acc["cached"],
                           "seconds": round(time.time() - t0), "dropped": len(fs.dropped),
                           "unmatched": s["unmatched"], "negative_control_hits": s["negative_control_hits"]}
            print(f"  {system}: tp {s['tp']} fp {s['fp']} fn {s['fn']}  ${acc['if_fresh_usd']:.3f} "
                  f"(spent ${acc['spent_usd']:.3f}, ${left:.2f} left)", flush=True)
        rows.append(row)
    (OUT / f"pilot-{time.strftime('%Y%m%dT%H%M%S')}.json").write_text(json.dumps(rows, indent=1, default=str))


if __name__ == "__main__":
    main()

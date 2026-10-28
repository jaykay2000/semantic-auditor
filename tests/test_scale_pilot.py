"""The dev scale pilot's padding is rule-neutral BY CONSTRUCTION: with gold extractions, the code evaluation of
every padded story gives exactly the violated set of the unpadded one (no model)."""
import importlib.util
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from semaudit.contract.schema import load_contract  # noqa: E402
from semaudit.relate.interpret import stub_always  # noqa: E402
from semaudit.relate.rules import evaluate  # noqa: E402
from semaudit.story.model import Extraction  # noqa: E402

spec = importlib.util.spec_from_file_location("pilot", ROOT / "scripts/w13b_scale_pilot.py")
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)
C = load_contract(ROOT / "examples/northbound/contract")
GOLD = json.loads((ROOT / "tests/fixtures/stories/copy_gold.json").read_text())
NOISE = Extraction(message_kind="information", decision="none", action="none", strength="inform",
                   urgency_cue="none", explains_own_tradeoff=False, claims=[])


def violated(story):
    s = story.model_copy(deep=True)
    for e in s.messages():
        e.extraction = NOISE if e.copy_key.startswith("noise.") else Extraction(**GOLD[e.copy_key])
    return sorted((x.rule, x.subject, x.label or "") for x in evaluate(s, C, stub_always("compatible"))
                  if x.status == "violated")


def test_padding_changes_no_rule_result():
    truth = json.loads(pilot.TRUTH.read_text())
    base = pilot.dev_stories(truth["personas"])
    for name, s in base.items():
        want = violated(s)
        for k in (4, 16):
            padded = pilot.pad(s, k, random.Random(k))
            assert len(padded.events) == len(s.events) * k
            assert [e.at for e in padded.events] == sorted(e.at for e in padded.events), name
            assert violated(padded) == want, (name, k)

"""`semaudit demo`: rebuild committed results from committed inputs, with no model key, no browser and no network.

The inputs are named in a manifest (by default `docs/try-it/demo.json` in the repository):

  reviews: a finished review.json, the run files its page reads (episodes) and the captures it shows. The review is
           staged in a scratch folder at its manifest `run_dir`, and its page is built by the same code as
           `semaudit report` (report.page.build). Paths of the scratch folder and the repository are then written
           relative, as demo/build_sample_review.py does for the hosted page.
  cards:   a saved-checks run and the contract folder its checks come from, rendered by the same code as
           `semaudit checks card` (imported.card).

Each output is compared byte for byte with the committed file it should equal (`expect`). Nothing here creates a
model router, so no model can be called; tests/test_demo.py runs it with every model call made to fail.
Exit 0: every output was built and equals its committed file; 1: one differs; 2: could not run.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / "docs" / "try-it" / "demo.json"


class DemoError(RuntimeError):
    pass


def _relative(text: str, roots: list[Path]) -> str:
    for root in roots:
        r = str(root) + "/"
        text = text.replace(json.dumps(r)[1:-1], "").replace(r, "")
    return text


def build_review(spec: dict, repo: Path, out: Path) -> Path:
    from semaudit.report.page import build
    src = repo / spec["review"]
    review = json.loads(src.read_text())
    m = review.get("manifest") or {}
    stage = out / "stage"
    run_dir = stage / m.get("run_dir", "run")
    run_dir.mkdir(parents=True, exist_ok=True)
    for rel in spec.get("run_files", []):
        shutil.copytree(repo / rel, run_dir / Path(rel).name, dirs_exist_ok=True)
    if spec.get("captures"):
        shutil.copytree(repo / spec["captures"], run_dir / "captures", dirs_exist_ok=True)
    if m.get("run_dir"):
        m["run_dir"] = str(run_dir)
    if m.get("contract") and not Path(m["contract"]["dir"]).is_absolute():
        m["contract"]["dir"] = str(repo / m["contract"]["dir"])
    staged = run_dir / src.name
    staged.write_text(json.dumps(review, ensure_ascii=False, indent=1) + "\n")
    page_dir = out / spec["name"]
    if page_dir.exists():
        shutil.rmtree(page_dir)
    index = build(staged, page_dir)
    index.write_text(_relative(index.read_text(encoding="utf-8"), [stage, repo]), encoding="utf-8")
    shutil.rmtree(stage)
    return index


def build_cards(spec: dict, repo: Path, out: Path) -> Path:
    from semaudit.imported import card
    from semaudit.imported.record import ImportedCheck
    contract = repo / spec["contract"]
    cards = card.from_saved_run(repo / spec["saved"], contract)
    for cid in spec.get("also", []):
        cards.append(card.card_data(ImportedCheck.load(contract, cid), contract))
    return Path(card.render(cards, out / f"{spec['name']}.html", title=spec["title"], label=spec.get("label")))


def run(out: Path, manifest: Path = MANIFEST, echo=print, repo: Path | None = None) -> int:
    if not manifest.is_file():
        raise DemoError(f"{manifest} not found: run from a clone of the repository (pip install -e .)")
    repo = repo or manifest.resolve().parents[2]          # docs/try-it/demo.json -> the repository
    spec = json.loads(manifest.read_text())
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    differ = 0
    for kind, make in (("reviews", build_review), ("cards", build_cards)):
        for item in spec.get(kind, []):
            path = make(item, repo, out)
            expect = repo / item["expect"]
            same = expect.is_file() and path.read_bytes() == expect.read_bytes()
            differ += not same
            echo(f"{item['what']}\n  wrote {path}\n  "
                 + (f"same bytes as the committed {item['expect']}" if same
                    else f"DIFFERS from the committed {item['expect']}"))
    echo("no model was called: nothing in this command creates a model router")
    echo("judge self-check: not run (no key). It runs inside `semaudit review`, which needs a model key; the "
         "recorded review above predates it, so its page says none is recorded")
    return 0 if not differ else 1

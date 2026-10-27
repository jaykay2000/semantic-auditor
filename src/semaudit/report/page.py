"""The Release Story page (W10b): one static HTML file per review, plus the captures it shows.

Everything on the page comes from review.json, plus the owner's decisions made on this exact review (from the
contract's dispositions.yaml, matched by the review's hash), shown beside the recommendation and never changing
it. The page computes layout only; the output folder can be hosted anywhere. `semaudit serve` renders the same
page with working decision buttons; the static page shows the command for each decision instead.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

TEMPLATE = Path(__file__).parent / "templates" / "release_story.html"


def referenced_files(review: dict) -> set[str]:
    out = set()
    for p in review["personas"]:
        for e in p["events"] + p.get("base_events", []):
            cap = e.get("capture") or {}
            if cap.get("screenshot"):
                out.add(cap["screenshot"])
    return out


def owner_data(review_path: Path, review: dict, *, interactive: bool = False, by: str | None = None) -> dict:
    from semaudit.decide.memory import decisions_for
    m = review.get("manifest") or {}
    d = Path(m["contract"]["dir"]) if m.get("contract") else None
    decided = decisions_for(review_path, d) if d and d.is_dir() else {"issues": {}, "release": None}
    return {"review": str(review_path), "interactive": interactive, "by": by, "can_decide": bool(m),
            "issues": decided["issues"], "release": decided["release"]}


def render(review_path: Path, *, interactive: bool = False, by: str | None = None) -> str:
    review = json.loads(review_path.read_text())
    data = json.dumps(review, ensure_ascii=False).replace("</", "<\\/")
    owner = json.dumps(owner_data(review_path, review, interactive=interactive, by=by),
                       ensure_ascii=False, default=str).replace("</", "<\\/")
    title = f"{review['app']['name'] if review.get('app') else ''} {review['release']['base']} → {review['release']['head']}"
    return (TEMPLATE.read_text().replace("__REVIEW_JSON__", data).replace("__OWNER_JSON__", owner)
            .replace("__TITLE__", title))


def build(review_path: Path, out_dir: Path | None = None) -> Path:
    review = json.loads(review_path.read_text())
    run_dir = review_path.parent
    out_dir = out_dir or run_dir / f"report-{review['release']['base']}-{review['release']['head']}"
    out_dir.mkdir(parents=True, exist_ok=True)
    missing = []
    for rel in sorted(referenced_files(review)):
        src = run_dir / rel
        if src.is_file():
            (out_dir / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, out_dir / rel)
        else:
            missing.append(rel)
    (out_dir / "index.html").write_text(render(review_path), encoding="utf-8")
    if missing:
        (out_dir / "MISSING.txt").write_text("\n".join(missing) + "\n")
    return out_dir / "index.html"

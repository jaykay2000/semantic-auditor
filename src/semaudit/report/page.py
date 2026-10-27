"""The Release Story page (W10b): one static HTML file per review, plus the captures it shows.

Everything on the page comes from review.json; the page computes layout only. The output folder can be
hosted anywhere (no server, no build step).
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
    data = json.dumps(review, ensure_ascii=False).replace("</", "<\\/")
    title = f"{review['app']['name'] if review.get('app') else ''} {review['release']['base']} → {review['release']['head']}"
    html = TEMPLATE.read_text().replace("__REVIEW_JSON__", data).replace("__TITLE__", title)
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    if missing:
        (out_dir / "MISSING.txt").write_text("\n".join(missing) + "\n")
    return out_dir / "index.html"

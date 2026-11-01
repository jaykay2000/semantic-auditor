"""The Release Story page (W10b): one static HTML file per review, plus the captures it shows.

Everything on the page comes from review.json, plus the owner's decisions made on this exact review (from the
contract's dispositions.yaml, matched by the review's hash), shown beside the recommendation and never changing
it. The page computes layout only; the output folder can be hosted anywhere. `semaudit serve` renders the same
page with working decision buttons; the static page shows the command for each decision instead.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path, PurePosixPath

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


def _cited(review: dict) -> set[str]:
    return {o["persona"] for k in ("issues", "resolved", "unconfirmed") for i in review.get(k) or []
            for o in i.get("occurrences", [])}


def _base_snapshots(run_dir: Path, base: str, persona: str, contract) -> list[dict] | None:
    """The base release's record snapshots for one persona, read from its episode (review.json carries the head
    release's snapshots only; an issue that is resolved or unconfirmed was seen in base)."""
    from semaudit.story.build import snapshot
    from semaudit.story.episode import Episode
    for f in sorted((run_dir / "episodes" / base).glob(f"{persona}__S-*.json")):
        if f.stem.rsplit("__S-", 1)[0] != persona:
            continue
        ep = Episode.read(f)
        snaps = [snapshot(ep.day0, ep.initial_state, contract)] if ep.initial_state else []
        snaps += [snapshot(st.at, st.state, contract) for st in ep.steps if st.state]
        return [{"at": s["at"].isoformat() if hasattr(s["at"], "isoformat") else s["at"], "truth": s["truth"]}
                for s in snaps]
    return None


def page_extras(review_path: Path, review: dict) -> dict:
    """What the page shows beside review.json, never in place of it: each cited persona's reference values from the
    contract and its base-release record snapshots (so a resolved issue's true value is the base record, not the
    head's), and the draft ticket for each issue (semaudit.report.ticket, the same text `semaudit ticket` writes).
    Anything that cannot be read is left out, and the page then says what it does not know."""
    from semaudit.report.ticket import ticket
    out: dict = {"truth": {}, "tickets": {}}
    m = review.get("manifest") or {}
    contract = None
    if m.get("contract"):
        try:
            from semaudit.contract.schema import load_contract
            contract = load_contract(Path(m["contract"]["dir"]))
        except Exception:                       # a moved contract: the page shows the reader's own statement
            contract = None
    run_dir = Path(m["run_dir"]) if m.get("run_dir") else review_path.parent
    if not (run_dir / "episodes").is_dir():
        run_dir = review_path.parent
    base = review["release"]["base"]
    for pid in sorted(_cited(review)):
        t: dict = {}
        if contract is not None:
            try:
                ref = contract.persona(pid).reference
                if ref:
                    t["reference"] = json.loads(json.dumps(dict(ref), default=str))
            except Exception:
                pass
            try:
                snaps = _base_snapshots(run_dir, base, pid, contract)
                if snaps is not None:
                    t["base_state"] = json.loads(json.dumps(snaps, default=str))
            except Exception:
                pass
        if t:
            out["truth"][pid] = t
    for k in ("issues", "resolved", "unconfirmed"):
        for i in review.get(k) or []:
            for pid in dict.fromkeys(o["persona"] for o in i["occurrences"]):   # one draft per persona shown
                try:
                    out["tickets"].setdefault(i["id"], {})[pid] = ticket(review, i["id"], pid)
                except Exception:
                    pass
    return out


def _blob(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str).replace("</", "<\\/")


def render(review_path: Path, *, interactive: bool = False, by: str | None = None) -> str:
    review = json.loads(review_path.read_text())
    data = json.dumps(review, ensure_ascii=False).replace("</", "<\\/")
    owner = _blob(owner_data(review_path, review, interactive=interactive, by=by))
    title = f"{review['app']['name'] if review.get('app') else ''} {review['release']['base']} → {review['release']['head']}"
    return (TEMPLATE.read_text().replace("__OWNER_JSON__", owner).replace("__EXTRAS_JSON__", _blob(page_extras(review_path, review)))
            .replace("__TITLE__", title).replace("__REVIEW_JSON__", data))


def contained_copy(rel: str, run_dir: Path, out_dir: Path) -> tuple[Path, Path]:
    """(source, destination) for a capture path named in review.json, or ValueError. The path must be relative,
    without "..", and both ends must resolve inside their folder: the source under the review's folder (a symlink
    that leads out of it is refused) and the destination under the output folder."""
    p = PurePosixPath(rel)
    if not rel or p.is_absolute() or Path(rel).is_absolute() or ".." in p.parts or "\\" in rel:
        raise ValueError(f"capture path {rel!r} is not a plain relative path")
    src, dst = run_dir / p, out_dir / p
    if not src.resolve().is_relative_to(run_dir.resolve()):
        raise ValueError(f"capture path {rel!r} leads outside the review's folder")
    if not dst.resolve().is_relative_to(out_dir.resolve()):
        raise ValueError(f"capture path {rel!r} leads outside the output folder")
    return src, dst


def build(review_path: Path, out_dir: Path | None = None) -> Path:
    review = json.loads(review_path.read_text())
    run_dir = review_path.parent
    out_dir = out_dir or run_dir / f"report-{review['release']['base']}-{review['release']['head']}"
    out_dir.mkdir(parents=True, exist_ok=True)
    missing = []
    for rel in sorted(referenced_files(review)):
        try:
            src, dst = contained_copy(rel, run_dir, out_dir)
        except ValueError as e:
            missing.append(f"{rel}  (refused: {e})")
            continue
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        else:
            missing.append(rel)
    (out_dir / "index.html").write_text(render(review_path), encoding="utf-8")
    if missing:
        (out_dir / "MISSING.txt").write_text("\n".join(missing) + "\n")
    return out_dir / "index.html"

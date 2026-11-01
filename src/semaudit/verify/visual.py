"""Visual confirmation (opt-in, off by default): is a flagged value actually on the page the user saw?

`semaudit visual` reads a finished review.json and, for each issue that qualifies, sends the model a crop of the
captured screenshot around the cited element with one question: is the flagged value visible here, and does it say
what the text says? The answer is recorded on the issue as a separate field and nothing else changes:

    "visual": {"result": "confirmed" | "contradicted" | "unreadable", "basis": "verifier" | "evidence_linked", ...}

`basis` says why the issue qualified: `verifier` when its verification status is `verified`; `evidence_linked` when
it is not (an unverified reader issue, say) but its quote was checked against the capture (the evidence_linked step
passed). An issue whose verification failed, or whose evidence did not resolve, is not sent. A visual `confirmed` is
not a verifier confirmation: it never changes a verification status, a verdict, a severity, confidence, the policy
row, the outcome, PASS or fix_confirmed. Everything that is not certain is `unreadable`: no screenshot or element
box, a path outside the review's folder, a box off the image, a model or provider error (including one that refuses
images), a reply that is not the schema, or a reply whose own fields disagree.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import io
import json
import re
from pathlib import Path
from typing import Any

from semaudit.models.router import ModelError, Router
from semaudit.report.page import contained_copy

ROLE = "vision"
MAX_SIDE = 768                      # the crop is fitted inside this many pixels before it is sent
PAD_LEFT, PAD_RIGHT, PAD_Y = 480, 160, 150     # page px of context around the element (its row label sits left)

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["readable", "visible", "reads", "same_as_text"],
    "properties": {
        "readable": {"type": "boolean"},
        "visible": {"type": "boolean"},
        "reads": {"type": "string"},
        "same_as_text": {"type": "boolean"},
    },
}

QUESTION = """This is a crop of a screenshot of the page a user saw. One element is outlined in red.
The text record says that element shows: {quote}
Is that value actually visible to the user on this page, and does it say what the text record says?
- readable: false if you cannot make out the outlined element at all (blurred, cut off, no image); else true.
- visible: true if the outlined element is shown to the user (not covered, not blank).
- reads: the outlined element's text, exactly as printed (empty if not readable).
- same_as_text: true if what is printed says the same as the text record."""


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().casefold()


def basis_of(issue: dict) -> str | None:
    """Why this issue qualifies for a visual check, or None if it does not."""
    v = issue.get("verification") or {}
    if v.get("status") == "failed":
        return None
    if v.get("status") == "verified":
        return "verifier"
    if ((v.get("steps") or {}).get("evidence_linked") or {}).get("result") == "pass":
        return "evidence_linked"
    return None


def target(issue: dict, events: dict[tuple[str, str], dict]) -> tuple[dict, str] | None:
    """(the cited event, the value the text says it shows): the first cited event, in occurrence order, that has a
    web capture. The value is the occurrence's quote when there is one, else the event's text."""
    for occ in issue.get("occurrences") or []:
        for eid in occ.get("events") or []:
            e = events.get((occ.get("persona"), eid))
            if e and (e.get("capture") or {}).get("kind") == "web":
                quote = (occ.get("quotes") or [None])[0] or e.get("text") or ""
                return e, quote
    return None


def crop(shot: Path, bbox: dict) -> tuple[bytes, list[int]]:
    """The PNG to send and the box it was cut from (page px; captures are taken at device scale 1). The element is
    outlined in red. ValueError when the box is not on the image."""
    from PIL import Image, ImageDraw
    img = Image.open(shot).convert("RGB")
    x0, y0 = bbox["x"], bbox["y"]
    x1, y1 = x0 + bbox["width"], y0 + bbox["height"]
    if bbox["width"] <= 0 or bbox["height"] <= 0 or x0 < 0 or y0 < 0 or x1 > img.width or y1 > img.height:
        raise ValueError(f"element box {bbox} is not on the {img.width}x{img.height} screenshot")
    box = [max(0, int(x0 - PAD_LEFT)), max(0, int(y0 - PAD_Y)),
           min(img.width, int(x1 + PAD_RIGHT + 1)), min(img.height, int(y1 + PAD_Y + 1))]
    ImageDraw.Draw(img).rectangle([x0 - 4, y0 - 4, x1 + 4, y1 + 4], outline=(220, 0, 0), width=2)
    out = img.crop(tuple(box))
    out.thumbnail((MAX_SIDE, MAX_SIDE))
    buf = io.BytesIO()
    out.save(buf, "PNG")
    return buf.getvalue(), box


def messages_for(png: bytes, quote: str) -> list[dict]:
    url = "data:image/png;base64," + base64.b64encode(png).decode()
    return [{"role": "user", "content": [{"type": "text", "text": QUESTION.format(quote=json.dumps(quote))},
                                         {"type": "image_url", "image_url": {"url": url}}]}]


def judge(reply: Any, quote: str) -> tuple[str, str]:
    """(result, reason) from the model's reply. The reply's printed text is compared with the quote here, and a
    reply whose own fields disagree with that comparison is unreadable."""
    if not isinstance(reply, dict) or set(reply) != set(SCHEMA["required"]) or not isinstance(reply.get("reads"), str) \
            or not all(isinstance(reply.get(k), bool) for k in ("readable", "visible", "same_as_text")):
        return "unreadable", "reply is not the schema"
    if not reply["readable"]:
        return "unreadable", "the model could not read the element"
    if not reply["visible"]:
        return "contradicted", "the model says the element is not visible to the user"
    shows = _norm(quote) != "" and _norm(quote) in _norm(reply["reads"])
    if shows and reply["same_as_text"]:
        return "confirmed", "the element shows the quoted value"
    if not shows and not reply["same_as_text"]:
        return "contradicted", "the element shows something else"
    return "unreadable", "the reply's fields disagree (printed text vs same_as_text)"


def check_issue(issue: dict, basis: str, events: dict, run_dir: Path, router: Router, *, role: str, seed: int,
                crops_dir: Path | None) -> dict:
    rec: dict[str, Any] = {"basis": basis}
    found = target(issue, events)
    if found is None:
        return {"result": "unreadable", **rec, "reason": "no cited event has a web capture"}
    e, quote = found
    cap = e.get("capture") or {}
    rec.update(event=e.get("id"), screenshot=cap.get("screenshot"), quote=quote)
    if not cap.get("screenshot") or not cap.get("bbox"):
        return {"result": "unreadable", **rec, "reason": "the capture has no screenshot or no element box"}
    try:
        shot, _ = contained_copy(cap["screenshot"], run_dir, run_dir)
        png, box = crop(shot, cap["bbox"])
    except (ValueError, OSError) as exc:
        return {"result": "unreadable", **rec, "reason": f"screenshot not usable: {exc}"}
    rec.update(crop_box=box, sent_sha256=hashlib.sha256(png).hexdigest())
    if crops_dir is not None:
        crops_dir.mkdir(parents=True, exist_ok=True)
        name = re.sub(r"[^A-Za-z0-9._-]", "_", issue["id"])[:120] + ".png"
        (crops_dir / name).write_bytes(png)
        rec["crop"] = name
    try:
        res = router.complete(role, messages_for(png, quote), schema=SCHEMA, schema_name="visual_check", seed=seed)
    except ModelError as exc:
        return {"result": "unreadable", **rec, "reason": f"model call failed: {str(exc)[:300]}"}
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        return {"result": "unreadable", **rec, "reason": f"reply not usable: {type(exc).__name__}"}
    result, reason = judge(res.parsed, quote)
    return {"result": result, **rec, "reason": reason, "reads": (res.parsed or {}).get("reads")
            if isinstance(res.parsed, dict) else None, "model": res.model, "cost_usd": res.cost_usd,
            "cached": res.cached}


def visual_confirm(review_path: Path, out_path: Path, router: Router, *, role: str = ROLE, seed: int = 1,
                   only: set[str] | None = None, crops_dir: Path | None = None) -> dict:
    """Write a copy of the review to `out_path` with `visual` added to each qualifying issue (all of them, or the
    ids in `only`); the review itself is not touched. Returns counts."""
    if role not in router.roles:
        raise ModelError(f"no [roles.{role}] in semaudit.toml: name a provider and a model that accepts images")
    if out_path.resolve() == review_path.resolve():
        raise ValueError("--out must be a new file: the review itself is never rewritten")
    review = json.loads(review_path.read_text())
    out = copy.deepcopy(review)
    events = {(p["id"], e["id"]): e for p in review.get("personas") or [] for e in p.get("events") or []}
    counts = {"confirmed": 0, "contradicted": 0, "unreadable": 0, "not_eligible": 0}
    for issue in out.get("issues") or []:
        if only is not None and issue["id"] not in only:
            continue
        basis = basis_of(issue)
        if basis is None:
            counts["not_eligible"] += 1
            continue
        issue["visual"] = check_issue(issue, basis, events, review_path.parent, router, role=role, seed=seed,
                                      crops_dir=crops_dir)
        counts[issue["visual"]["result"]] += 1
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=1) + "\n")
    return counts

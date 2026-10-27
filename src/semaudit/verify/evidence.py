"""evidence_linked: does every cited event resolve, exactly, to what was captured? Fails closed.

For a message event: its capture exists in the episode, the element is at the recorded index with the same
locator, the element's text equals the event's quoted text byte for byte, every stored artifact still has
the digest recorded at capture time, and the quote is present in the stored artifact itself.
"""

from __future__ import annotations

import hashlib
import html
from pathlib import Path

from semaudit.story.episode import Episode
from semaudit.story.model import Event


def resolve(event: Event, episode: Episode, run_dir: Path) -> tuple[bool, str]:
    ev = event.evidence
    if ev is None:
        return False, "no evidence recorded"
    if ev.episode != episode.id:
        return False, f"evidence points at episode {ev.episode}, not {episode.id}"
    cap = next((c for c in episode.captures() if c.id == ev.capture_id), None)
    if cap is None:
        return False, f"capture {ev.capture_id} not in episode"
    if cap.status != "captured":
        return False, f"capture {cap.id} was not measured"
    if ev.element >= len(cap.elements):
        return False, f"element {ev.element} missing from {cap.id}"
    el = cap.elements[ev.element]
    if el.locator != ev.locator:
        return False, "locator changed"
    if el.text != event.text:
        return False, "quoted text differs from the captured element"
    for role, digest in ev.capture_sha256.items():
        path = run_dir / cap.files.get(role, "")
        if not cap.files.get(role) or not path.is_file():
            return False, f"artifact {role} missing"
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            return False, f"artifact {role} changed since capture"
        if role in ("dom", "raw") and event.text not in html.unescape(path.read_text(encoding="utf-8")):
            return False, f"quote not found in stored {role}"
    return True, "ok"

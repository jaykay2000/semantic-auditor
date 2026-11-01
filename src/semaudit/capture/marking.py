"""Marked messages SRA would lose without a word, found from the stored episodes so `capture` and `review` say so.

Two ways a message the app meant to mark never counts:

  unquotable  an element carries a message key, but its text is not in the stored page (or raw file) as written.
              The usual cause is a marked element that wraps other tags (`<div data-message-key=…><h2>Pro</h2>
              <p>…</p></div>`): the browser's rendered text joins the parts with line breaks the page source does
              not have. Evidence must be found in the stored artifact (verify/evidence.py, the same test as here),
              so an issue on such a message can never be verified and is not raised.
  keyless     an email or push in a sink has no message key header (`X-Message-Key`), so it is not read as a
              message at all (story/episode.py `messages()`).

This only reports; it changes no capture and loosens no check.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from semaudit.story.episode import KEY_ATTRS, Episode
from semaudit.verify.evidence import _quoted_in

SINK_KINDS = ("email", "push")


def _key(attrs: dict) -> str | None:
    return next((attrs[k] for k in KEY_ATTRS if attrs.get(k)), None)


def unquotable(ep: Episode, run_dir: Path) -> list[str]:
    out = []
    for cap in ep.captures():
        if cap.status != "captured" or cap.kind in SINK_KINDS:
            continue
        for role in ("dom", "raw"):
            path = Path(run_dir) / cap.files[role] if cap.files.get(role) else None
            if path is None or not path.is_file():
                continue
            for el in cap.elements:
                key = _key(el.attrs)
                if key and el.text and not _quoted_in(el.text, path):
                    out.append(f"{ep.id} {cap.id} ({cap.url or cap.surface}): marked message {key!r} cannot be "
                               f"quoted as evidence: its text is not in the stored {role} as written (a marked "
                               "element must hold its text directly; see docs/10-add-your-app.md, 'Marking "
                               "messages')")
    return out


def keyless(ep: Episode) -> Counter:
    """(capture kind, surface) -> sink messages with no message key."""
    return Counter((cap.kind, cap.surface) for cap in ep.captures() if cap.kind in SINK_KINDS
                   for el in cap.elements if not _key(el.attrs))


def warnings(episodes: list[Episode], run_dir: Path) -> list[str]:
    """One line per unquotable marked message, one per episode and sink surface with keyless messages."""
    out = []
    for ep in episodes:
        out += unquotable(ep, run_dir)
        for (kind, surface), n in sorted(keyless(ep).items()):
            out.append(f"{ep.id}: {n} {kind} message{'s' if n != 1 else ''} on {surface!r} with no X-Message-Key "
                       "header, not read as messages (see docs/10-add-your-app.md, 'Email and push sinks')")
    return out


def run_warnings(run_dir: Path, releases: list[str]) -> tuple[list[str], int, int]:
    """Warnings for the episodes of these releases in a run folder: (lines, unquotable count, keyless count)."""
    episodes = [Episode.read(p) for rel in releases
                for p in sorted((Path(run_dir) / "episodes" / rel).glob("*.json"))]
    lines = warnings(episodes, run_dir)
    n_unquotable = sum(len(unquotable(ep, run_dir)) for ep in episodes)
    n_keyless = sum(sum(keyless(ep).values()) for ep in episodes)
    return lines, n_unquotable, n_keyless

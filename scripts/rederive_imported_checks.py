"""Re-derive stored imported-check results under the current rules, with no model call and no replay.

    python3 scripts/rederive_imported_checks.py BASE_RESULT.json HEAD_RESULT.json ...   # pairs of recheck results
    python3 scripts/rederive_imported_checks.py --saved saved-checks.json ...            # saved-check runs

Each release's assertion is re-derived from its stored votes and evidence (`recheck.needs_evidence`), and the
base/head memory status from those (`memory.check_status`). Prints old -> new for each; the inputs are not changed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from semaudit.decide.memory import check_status
from semaudit.imported.recheck import needs_evidence


def rederive(r: dict) -> dict:
    """The assertion as voted (undoing an earlier demotion, if any), then the current evidence rule applied."""
    a = r["assertion"]
    voted = {"outcome": a.get("majority", a["outcome"]), "votes": a["votes"],
             **({"why": a["why"]} if "why" in a and "majority" not in a else {})}
    return {**r, "assertion": needs_evidence(voted, r["evidence"]["status"])}


def pair(label: str, base: dict, head: dict) -> list[str]:
    nb, nh = rederive(base), rederive(head)
    old, new = check_status(base, head), check_status(nb, nh)
    lines = []
    for side, o, n in (("base", base, nb), ("head", head, nh)):
        lines.append(f"{label} {side} {o['release']}: votes {o['assertion']['votes']} evidence "
                     f"{o['evidence']['status']}: {o['assertion']['outcome']} -> {n['assertion']['outcome']}"
                     + ("" if o["assertion"]["outcome"] == n["assertion"]["outcome"] else "  CHANGED"))
    lines.append(f"{label} memory: {old[0]} -> {new[0]}" + ("" if old[0] == new[0] else f"  CHANGED ({new[1]})"))
    return lines


def main(argv: list[str]) -> int:
    out = []
    if argv and argv[0] == "--saved":
        for f in argv[1:]:
            run = json.loads(Path(f).read_text())
            for c in run["checks"]:
                out += pair(f"{run['run']} {c['id']}", c["results"][run["base"]], c["results"][run["head"]])
    else:
        for b, h in zip(argv[::2], argv[1::2]):
            base, head = json.loads(Path(b).read_text()), json.loads(Path(h).read_text())
            out += pair(f"{Path(b).stem}+{Path(h).stem} {base['check']}", base, head)
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

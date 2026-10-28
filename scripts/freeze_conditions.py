"""Freeze every file that decides how a sealed benchmark run is executed and scored, by sha256.

  python3 scripts/freeze_conditions.py --out bench/conditions/FROZEN-POSTFIX.md --note "W13c post-fix"
  python3 scripts/freeze_conditions.py --check bench/conditions/FROZEN-POSTFIX.md     # exit 1 on any change

The manifest id is the sha256 of the sorted (path, sha256) table, so any edit, addition or removal changes it.
"""
import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INCLUDE = ("src/semaudit/**/*.py", "src/semaudit/**/*.html", "src/semaudit/**/*.j2", "bench/conditions/**/*",
           "examples/northbound/contract/rubric.md", "scripts/w13c_postfix.py", "scripts/freeze_conditions.py")
EXCLUDE = ("bench/conditions/FROZEN-",)          # the manifests themselves


def files() -> list[Path]:
    out = set()
    for pat in INCLUDE:
        out |= {p for p in ROOT.glob(pat) if p.is_file() and "__pycache__" not in p.parts}
    return sorted(p for p in out if not str(p.relative_to(ROOT)).startswith(EXCLUDE))


def table() -> list[tuple[str, str]]:
    return [(str(p.relative_to(ROOT)), hashlib.sha256(p.read_bytes()).hexdigest()) for p in files()]


def manifest_id(rows) -> str:
    return hashlib.sha256("\n".join(f"{a} {b}" for a, b in rows).encode()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path)
    ap.add_argument("--note", default="")
    ap.add_argument("--check", type=Path)
    a = ap.parse_args()
    rows = table()
    if a.check:
        want = [tuple(l.strip("| ").replace("`", "").split(" | ")) for l in a.check.read_text().splitlines()
                if l.startswith("| `")]
        if want == rows:
            print(f"OK: {len(rows)} files match {a.check.name}")
            return 0
        a_, b_ = dict(want), dict(rows)
        for p in sorted(set(a_) | set(b_)):
            if a_.get(p) != b_.get(p):
                print(f"CHANGED: {p}")
        return 1
    code = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    lines = [f"{a.out.stem} manifest {manifest_id(rows)} at code {code}", "",
             f"# {a.note}", "", "Every file that decides how this sealed run is executed and scored, by sha256. "
             "A change to any file below invalidates the run unless it is re-frozen with a recorded reason. "
             f"Check: `python3 scripts/freeze_conditions.py --check {a.out}`.", "",
             "| file | sha256 |", "|---|---|"] + [f"| `{p}` | `{h}` |" for p, h in rows]
    a.out.write_text("\n".join(lines) + "\n")
    print(lines[0], f"({len(rows)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

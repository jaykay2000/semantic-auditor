"""`semaudit compare-prompts`: one recorded review's verification under an earlier version of the defender's
instructions and under the current one, each run k times.

A prompt change can move verdicts, and a single run cannot tell the change from a model's run-to-run variation. This
re-derives the review's issues from its pinned episodes (the recorded readings, from the model cache), then runs the
second-model check and the defence on every issue the review raised or dropped in verification, k runs per prompt
version, and reports per issue how often each step held (n of k) and the status each version gives.

Only the defender's instructions and schema are swapped. A changed extraction or judging prompt is reported but not
compared: swapping it would change the readings and the issues themselves, not only their verification. The
adjudication code is the current code for both versions, so the comparison isolates the prompt.
"""

from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path

from semaudit.contract.schema import load_contract
from semaudit.decide.issues import build_issues
from semaudit.decide.pipeline import evaluate_release
from semaudit.models.router import Router
from semaudit.verify import steps as S

SRA_ROOT = Path(__file__).resolve().parents[3]
PROMPTS = {"defense": ("src/semaudit/verify/steps.py", ("DEFENSE_INSTRUCTIONS", "DEFENSE_SCHEMA")),
           "interpret": ("src/semaudit/relate/interpret.py", ("INSTRUCTIONS", "LABEL_SCHEMA")),
           "extraction": ("src/semaudit/extract/messages.py", ("PROMPT",))}
COMPARED = ("defense",)
_SAFE = {"list": list, "dict": dict, "set": set, "tuple": tuple, "sorted": sorted, "frozenset": frozenset}


def constants_at(rev: str, path: str, names: tuple[str, ...], repo: Path = SRA_ROOT) -> dict:
    """The module-level UPPER_CASE constants `names` of `path` as committed at `rev`: each top-level constant
    assignment is evaluated in order with no imports and almost no builtins; one that needs anything else is skipped."""
    got = subprocess.run(["git", "-C", str(repo), "show", f"{rev}:{path}"], capture_output=True, text=True)
    if got.returncode != 0:
        raise ValueError(f"cannot read {path} at {rev}: {got.stderr.strip()[:200]}")
    ns: dict = {"__builtins__": _SAFE}
    for node in ast.parse(got.stdout).body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) \
            and node.value is not None else []
        if targets and all(isinstance(t, ast.Name) and t.id.lstrip("_").isupper() for t in targets):
            try:
                exec(compile(ast.Module([node], []), f"{rev}:{path}", "exec"), ns)   # noqa: S102 - this repo's own history
            except Exception:                                                       # noqa: BLE001
                continue
    missing = [n for n in names if n not in ns]
    if missing:
        raise ValueError(f"{path} at {rev} has no {', '.join(missing)}")
    return {n: ns[n] for n in names}


def _current(path: str, names: tuple[str, ...]) -> dict:
    import importlib
    mod = importlib.import_module(path.removeprefix("src/").removesuffix(".py").replace("/", "."))
    return {n: getattr(mod, n) for n in names}


def compare_prompts(review_path: Path, old_rev: str, *, repeats: int, root: Path, max_usd: float) -> dict:
    r = json.loads(review_path.read_text())
    m = r["manifest"]
    run_dir = Path(m["run_dir"])
    if not run_dir.is_absolute() and not (run_dir / "episodes").is_dir():
        run_dir = review_path.parent
    contract = load_contract(Path(m["contract"]["dir"]), memory=(m.get("memory") or {}).get("issues", []))
    router = Router(root=root, max_usd=max_usd)
    router.tag = f"compare-prompts:{old_rev}:{r['release']['base']}-{r['release']['head']}"
    shared = {} if getattr(contract.app, "share_readings", False) else None
    evaluate_release(run_dir, r["release"]["base"], contract, router, readings=shared)
    h = evaluate_release(run_dir, r["release"]["head"], contract, router, readings=shared)
    recorded = {d["id"]: d for d in r["issues"]}
    dropped = {s: x["reason"] for x in r["not_raised"] if x["status"] == "not_raised" for s in x["subjects"]}
    issues = [i for i in build_issues(r["release"]["head"], h.results, contract) if i.id in recorded or i.id in dropped]
    stories = {p: s for p, (s, _) in h.results.items()}

    prompts = {}
    for key, (path, names) in PROMPTS.items():
        same = constants_at(old_rev, path, names) == _current(path, names)
        prompts[key] = "same" if same else ("differs" if key in COMPARED else "differs (not compared)")
    versions = {"old": constants_at(old_rev, *PROMPTS["defense"]), "current": _current(*PROMPTS["defense"])}

    rows = {i.id: {} for i in issues}
    for name, consts in versions.items():
        saved = {k: getattr(S, k) for k in consts}
        try:
            for k, v in consts.items():
                setattr(S, k, v)
            for i in issues:
                cm, df = S.model_steps(i, stories, contract, router, fresh=False, repeats=repeats)
                rec = recorded.get(i.id, {}).get("verification", {}).get("steps", {})
                # the code steps as the review recorded them; an issue dropped as disputed had passed reproduction
                # and evidence (that is the only way to reach "disputed")
                code = {k: rec.get(k, {"result": "pass" if dropped.get(i.id, "").endswith("disputed")
                                       else "not_run"}) for k in ("reproduced", "evidence_linked")}
                steps = {**code, "cross_model": cm, "defended": df,
                         "oracle_checked": rec.get("oracle_checked") or S.step_oracle(i, stories, contract)}
                held = lambda st: f"{st['samples']['passed']}/{st['samples']['k']}" if "samples" in st \
                    else ("1/1" if st["result"] == "pass" else "0/1")                      # noqa: E731
                v = S.verification_status(steps)
                rows[i.id][name] = {"cross_model": held(cm), "defended": held(df),
                                    "status": v["status"] + (f": {v['reason']}" if v["reason"] else "")}
        finally:
            for k, v in saved.items():
                setattr(S, k, v)
    return {"review": str(review_path), "old_rev": old_rev, "repeats": repeats, "prompts": prompts,
            "issues": [{"id": iid, "in_review": "raised" if iid in recorded else f"dropped ({dropped[iid]})", **v}
                       for iid, v in rows.items()],
            "spend": router.accounting()}

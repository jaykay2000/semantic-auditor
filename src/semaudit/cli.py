"""semaudit command line. Exit codes: 0 ok, 1 problems that need a decision, 2 could not measure."""

from __future__ import annotations

from pathlib import Path

import typer

from .contract.approve import approve as _approve
from .contract.approve import items, load_approvals, status_of
from .contract.review import serve, write
from .contract.schema import load_contract
from .contract.validate import validate

app = typer.Typer(no_args_is_help=True, add_completion=False)
contract = typer.Typer(no_args_is_help=True, help="Check, review and approve a product contract.")
app.add_typer(contract, name="contract")


@contract.command("check")
def check(directory: Path = typer.Argument(..., exists=True, file_okay=False)):
    """Validate cross-references and the release policy; report approval status."""
    c = load_contract(directory)
    problems = validate(c)
    for p in problems:
        typer.echo(f"problem: {p}")
    approvals = load_approvals(directory)
    pending = [i.key for i in items(c) if status_of(i, approvals) != "approved"]
    typer.echo(f"{len(problems)} problem(s); {len(pending)} item(s) not approved at current content")
    for k in pending:
        typer.echo(f"  pending: {k}")
    raise typer.Exit(1 if problems or pending else 0)


@contract.command("review")
def review(directory: Path = typer.Argument(..., exists=True, file_okay=False),
           out: Path = typer.Option(None, help="write a static, read-only page here"),
           port: int = typer.Option(8790, help="serve with working Approve buttons on this port"),
           by: str = typer.Option("owner", help="who the approvals are recorded as")):
    """Render the contract for the owner. Without --out, serve it locally with Approve buttons."""
    if out:
        typer.echo(f"wrote {write(directory, out)}")
        return
    serve(directory, port=port, by=by)


@contract.command("approve")
def approve_cmd(directory: Path = typer.Argument(..., exists=True, file_okay=False),
                key: list[str] = typer.Option(..., "--item", help="item key, e.g. rule:P2 (repeatable)"),
                by: str = typer.Option(..., help="who approves")):
    """Approve items at their current content (pinned by hash)."""
    c = load_contract(directory)
    for k in _approve(directory, c, key, by=by):
        typer.echo(f"approved {k}")


@app.command("capture")
def capture_cmd(contract_dir: Path = typer.Option(..., "--contract", exists=True, file_okay=False,
                                                  help="the product contract directory"),
                release: str = typer.Option(..., "--release", help="release to run, e.g. 2.4"),
                persona: list[str] = typer.Option(None, "--persona", help="persona id (repeatable); default all"),
                run_id: str = typer.Option(None, "--run-id", help="default capture-<UTC time>"),
                runs_dir: Path = typer.Option(Path("runs"), "--runs-dir"),
                seed: int = typer.Option(0, "--seed")):
    """Run each persona's scenarios against a release and write episodes (steps, captures, state) under runs/.

    Exit 0: every step ran. Exit 2: a release would not boot, or a step failed or a surface could not be
    measured; the episodes are still written and the failures are listed.
    """
    from .capture import LaunchError, Runner

    problems: list[str] = []
    try:
        with Runner(contract_dir, runs_dir=runs_dir, run_id=run_id, seed=seed) as r:
            episodes = r.capture(release, persona or None)
            run_dir = r.run_dir
    except (LaunchError, FileNotFoundError, AttributeError) as exc:
        typer.echo(f"cannot measure: {exc}", err=True)
        raise typer.Exit(2)
    for ep in episodes:
        counts = {k: sum(1 for st in ep.steps if st.status == k) for k in ("done", "skipped_not_offered", "failed")}
        ncap = len(ep.captures())
        typer.echo(f"{ep.id}: {counts['done']} done, {counts['skipped_not_offered']} skipped, "
                   f"{counts['failed']} failed; {ncap} captures")
        problems += [f"{ep.id} step {st.seq} ({st.do}): {st.error}" for st in ep.steps if st.status == "failed"]
        problems += [f"{ep.id} {c.id}: {c.error}" for c in ep.captures() if c.status == "not_measured"]
        problems += [f"{ep.id} {n.surface}: not measured, {n.reason}" for n in ep.not_measured]
    typer.echo(f"episodes in {run_dir / 'episodes' / release}")
    for p in problems:
        typer.echo(f"  not measured: {p}")
    raise typer.Exit(2 if problems else 0)


@app.command("review")
def review_cmd(contract_dir: Path = typer.Option(..., "--contract", exists=True, file_okay=False),
               base: str = typer.Option(..., "--base"), head: str = typer.Option(..., "--head"),
               max_usd: float = typer.Option(..., "--max-usd", help="spend cap for every model call in this review"),
               run_id: str = typer.Option(None, "--run-id"), runs_dir: Path = typer.Option(Path("runs"), "--runs-dir"),
               reuse: bool = typer.Option(False, "--reuse", help="reuse captures already in the run directory"),
               fresh: bool = typer.Option(False, "--fresh", help="ignore the model cache")):
    """Review a release against its base: issues, verification, recommendation. Writes review-<base>-<head>.json.

    Exit 0: a decided Ship (complete measurement, approved contract); 1: anything that needs the owner,
    including a provisional recommendation from an unapproved contract; 2: could not measure.
    """
    import json
    import time
    from .decide.run import run_review
    from .models.router import ModelError
    run_id = run_id or f"review-{time.strftime('%Y%m%dT%H%M%S')}"
    try:
        path = run_review(contract_dir, base, head, run_id=run_id, runs_dir=runs_dir, max_usd=max_usd,
                          reuse=reuse, fresh=fresh)
    except ModelError as e:
        typer.echo(f"cannot measure: {e}", err=True)
        raise typer.Exit(2)
    r = json.loads(path.read_text())
    out = r["outcome"]
    typer.echo(f"{base} -> {head}: {out['recommendation'].upper()}"
               + (f"  (policy row {r['policy']['row']}: {r['policy']['rule_fired']})" if out["status"] == "decided"
                  else f"  ({out['reason']}; policy would say {r['policy']['recommendation']})"))
    for side in ("base", "head"):
        for p, probs in r["measurement"][side].items():
            typer.echo(f"  not measured ({side}) {p}: {'; '.join(probs)}")
    for i in r["issues"]:
        v = i["verification"]["status"]
        typer.echo(f"  {i['id']:52} {i['severity']['level']:8} conf {i['confidence']['level']:6} {v:18} "
                   f"{i['delta']:12} {', '.join(i['personas'])}")
    for i in r["resolved"]:
        m = i.get("memory") or {}
        typer.echo(f"  resolved: {i['id']}" + (f"  ({m['status'].replace('_', ' ')}, {m['decision']})" if m else ""))
    for x in r["not_raised"]:
        if x["status"] == "owner_set_aside":
            typer.echo(f"  set aside by owner: {x['subjects'][0]} ({x['memory']['decision']})")
    for i in r["unconfirmed"]:
        typer.echo(f"  NOT CONFIRMED resolved: {i['id']} ({i['delta_basis']})")
    from .report.page import build
    page = build(path)
    typer.echo(f"not raised: {len(r['not_raised'])} · spent ${r['cost_usd']:.3f} · {path}")
    typer.echo(f"Release Story: {page}")
    if out["status"] == "not_measurable":
        raise typer.Exit(2)
    raise typer.Exit(0 if out["status"] == "decided" and out["recommendation"] == "ship" else 1)


@app.command("report")
def report_cmd(review: Path = typer.Argument(..., exists=True, dir_okay=False),
               out: Path = typer.Option(None, "--out", help="output folder (default: beside the review)")):
    """Build the static Release Story page from a review JSON."""
    from .report.page import build
    typer.echo(f"wrote {build(review, out)}")


@app.command("repro")
def repro_cmd(issue_id: str = typer.Argument(..., help="an issue id from the review, e.g. I-2.4-P2-…"),
              review: Path = typer.Option(..., "--review", exists=True, dir_okay=False, help="the review JSON"),
              max_usd: float = typer.Option(..., "--max-usd", help="spend cap (unchanged messages hit the cache)"),
              runs_dir: Path = typer.Option(None, "--runs-dir", help="where the replay run goes (default: beside the review)"),
              fresh: bool = typer.Option(False, "--fresh", help="ignore the model cache")):
    """Replay one finding from scratch: re-capture, check every cited moment, re-derive the issue.

    Uses the contract, adapter and prompts the review's manifest pins; refuses if they changed.
    Exit 0: reproduced; 1: ran but did not reproduce; 2: could not measure.
    """
    from .capture import LaunchError
    from .decide.repro import CannotReplay, replay
    from .models.router import ModelError
    try:
        res = replay(review, issue_id, max_usd=max_usd, runs_dir=runs_dir, fresh=fresh)
    except (CannotReplay, LaunchError, ModelError) as e:
        typer.echo(f"cannot measure: {e}", err=True)
        raise typer.Exit(2)
    typer.echo(f"{issue_id} ({res.kind}) · replay run {res.run_dir}")
    for c in res.checks:
        typer.echo(f"  {c.name}: {'ok' if c.ok else 'FAILED'}")
        for line in c.lines:
            typer.echo(f"    {line}")
    typer.echo("REPRODUCED" if res.ok else "NOT REPRODUCED")
    raise typer.Exit(0 if res.ok else 1)


@app.command("decide")
def decide_cmd(issue_id: str = typer.Argument(..., help="an open issue id from the review"),
               kind: str = typer.Argument(..., help="fix | not-an-issue | accept"),
               review: Path = typer.Option(..., "--review", exists=True, dir_okay=False, help="the review JSON"),
               by: str = typer.Option(..., "--by", help="who decides (recorded with the decision)"),
               reason: str = typer.Option(None, "--reason", help="required for not-an-issue"),
               expires: str = typer.Option(None, "--expires", help="accept: when the exception ends (YYYY-MM-DD)")):
    """Record an owner decision on one issue; the next review applies it.

    fix: the next review must show it resolved, else it is raised as still_open. not-an-issue: that exact
    signature, with the same personas and messages, is set aside; any variant is raised. accept: a new exception,
    narrowed to exactly this issue's features, components and surfaces (conditional rules, scope-only failures).
    Exit 0: recorded; 1: refused (the reason is printed).
    """
    from .decide.memory import DecisionError, decide_issue
    from .report.page import build
    k = kind.replace("-", "_")
    if k in ("rule", "expect"):
        typer.echo(f"{kind}: deterministic-check and semantic-expectation decisions are planned, not built; "
                   "use fix, not-an-issue or accept", err=True)
        raise typer.Exit(1)
    try:
        d = decide_issue(review, issue_id, k, by=by, reason=reason, expires=expires)
    except DecisionError as e:
        typer.echo(f"not recorded: {e}", err=True)
        raise typer.Exit(1)
    typer.echo(f"recorded {d['id']}: {issue_id} {d['kind']} by {d['by']} on {d['date']}"
               + (f" (supersedes {', '.join(d['supersedes'])})" if d.get("supersedes") else ""))
    for x in d.get("exceptions", []):
        typer.echo(f"  exception {x['id']}: scope {x['scope']}, conditions "
                   f"{', '.join(c['id'] for c in x['conditions'])}, expires {x['approved']['expires']} (approved)")
    typer.echo(f"Release Story: {build(review)}")


@app.command("decide-release")
def decide_release_cmd(decision: str = typer.Argument(..., help="ship | ship-with-notes | hold"),
                       review: Path = typer.Option(..., "--review", exists=True, dir_okay=False),
                       by: str = typer.Option(..., "--by", help="who decides"),
                       note: str = typer.Option(None, "--note")):
    """Record the owner's release decision beside the review's recommendation (it never changes it)."""
    from .decide.memory import DecisionError, decide_release
    from .report.page import build
    try:
        d = decide_release(review, decision.replace("-", "_"), by=by, note=note)
    except DecisionError as e:
        typer.echo(f"not recorded: {e}", err=True)
        raise typer.Exit(1)
    said = d["review_said"]
    typer.echo(f"recorded: {d['head']} {d['decision']} by {d['by']} on {d['date']} "
               f"(review said {said['recommendation']}; policy {said['policy']})")
    typer.echo(f"Release Story: {build(review)}")


@app.command("serve")
def serve_cmd(review: Path = typer.Option(..., "--review", exists=True, dir_okay=False),
              by: str = typer.Option(..., "--by", help="who the decisions are recorded as"),
              port: int = typer.Option(8791, "--port")):
    """Serve the Release Story locally with working decision buttons."""
    from .report.serve import serve
    serve(review, by=by, port=port)


@app.command("verify-report")
def verify_report_cmd(review: Path = typer.Argument(..., exists=True, dir_okay=False)):
    """Check a review.json against the inputs its manifest pins, offline (model cache only, no spend).

    Exit 0: the review is what its inputs produce; 1: it is not (each difference is listed); 2: cannot check.
    """
    from .verify.report import CannotVerify, verify_report
    try:
        problems = verify_report(review)
    except CannotVerify as e:
        typer.echo(f"cannot verify: {e}", err=True)
        raise typer.Exit(2)
    for p in problems:
        typer.echo(f"  ✗ {p}")
    typer.echo("CONSISTENT: the review is what its pinned inputs produce" if not problems
               else f"NOT CONSISTENT: {len(problems)} difference(s)")
    raise typer.Exit(0 if not problems else 1)


if __name__ == "__main__":
    app()

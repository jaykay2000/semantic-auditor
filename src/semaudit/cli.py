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

    Exit 0: recommendation is ship; 1: anything else needs the owner; 2: could not measure.
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
    typer.echo(f"{base} -> {head}: {r['policy']['recommendation'].upper()}  ({r['policy']['rule_fired']})")
    for i in r["issues"]:
        v = i["verification"]["status"]
        typer.echo(f"  {i['id']:52} {i['severity']['level']:8} conf {i['confidence']['level']:6} {v:18} "
                   f"{i['delta']:12} {', '.join(i['personas'])}")
    for i in r["resolved"]:
        typer.echo(f"  resolved: {i['id']}")
    from .report.page import build
    page = build(path)
    typer.echo(f"not raised: {len(r['not_raised'])} · spent ${r['cost_usd']:.3f} · {path}")
    typer.echo(f"Release Story: {page}")
    raise typer.Exit(0 if r["policy"]["recommendation"] == "ship" else 1)


@app.command("report")
def report_cmd(review: Path = typer.Argument(..., exists=True, dir_okay=False),
               out: Path = typer.Option(None, "--out", help="output folder (default: beside the review)")):
    """Build the static Release Story page from a review JSON."""
    from .report.page import build
    typer.echo(f"wrote {build(review, out)}")


@app.command("repro")
def repro_cmd(issue_id: str = typer.Argument(..., help="e.g. I-2.4-P2-fare-lock-price-watch-unexplained-tradeoff"),
              review: Path = typer.Option(None, "--review", help="review JSON (default: the newest under runs/)"),
              contract_dir: Path = typer.Option(Path("examples/northbound/contract"), "--contract"),
              runs_dir: Path = typer.Option(Path("runs"), "--runs-dir")):
    """Re-capture the issue's personas on the head release and check every cited moment appears again.

    Exit 0: reproduced; 1: an event did not come back (or came back different); 2: could not measure.
    """
    import json
    import time
    from .capture import LaunchError, Runner
    from .contract.schema import load_contract
    from .story.build import story_from_episode
    review = review or max(runs_dir.glob("*/review-*.json"), key=lambda p: p.stat().st_mtime, default=None)
    if review is None or not review.exists():
        typer.echo("no review found", err=True)
        raise typer.Exit(2)
    r = json.loads(review.read_text())
    issue = next((i for i in r["issues"] + r["resolved"] if i["id"] == issue_id), None)
    if issue is None:
        typer.echo(f"{issue_id} not in {review}", err=True)
        raise typer.Exit(2)
    head = r["release"]["base"] if issue in r["resolved"] else r["release"]["head"]
    views = {p["id"]: {e["id"]: e for e in p["events"]} for p in r["personas"]}
    contract = load_contract(contract_dir)
    personas = sorted({o["persona"] for o in issue["occurrences"]})
    typer.echo(f"{issue_id}: re-capturing {', '.join(personas)} on {head}")
    try:
        with Runner(contract_dir, runs_dir=runs_dir, run_id=f"repro-{time.strftime('%Y%m%dT%H%M%S')}") as run:
            fresh = {ep.persona: story_from_episode(ep, contract) for ep in run.capture(head, personas)}
    except LaunchError as e:
        typer.echo(f"cannot measure: {e}", err=True)
        raise typer.Exit(2)
    ok = True
    for o in issue["occurrences"]:
        for eid in o["events"]:
            want = views.get(o["persona"], {}).get(eid)
            if want is None or want["kind"] != "message":
                continue
            got = [e for e in fresh[o["persona"]].messages()
                   if e.copy_key == want["message_key"] and e.feature == want["feature"]
                   and e.text == want["text"] and e.at.isoformat() == want["at"]]
            ok &= bool(got)
            typer.echo(f"  {'✓' if got else '✗'} {o['persona']} {want['at'][11:19]} {want['feature']}: "
                       f"\"{want['text'][:70]}\"")
    typer.echo("REPRODUCED" if ok else "NOT REPRODUCED")
    raise typer.Exit(0 if ok else 1)


if __name__ == "__main__":
    app()

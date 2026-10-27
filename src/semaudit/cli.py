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


if __name__ == "__main__":
    app()

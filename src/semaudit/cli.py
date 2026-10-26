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


if __name__ == "__main__":
    app()

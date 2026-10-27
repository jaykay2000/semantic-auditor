"""Start the app under audit for one release, on a free port, and tear down the process we started."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from ..contract.schema import App


class LaunchError(RuntimeError):
    """The release would not boot (or no launch config exists). The audit cannot measure it: exit code 2."""


@dataclass
class RunningApp:
    release: str
    base_url: str
    sink_root: Path | None
    scratch: Path | None = None
    proc: subprocess.Popen | None = field(default=None, repr=False)
    log_path: Path | None = None

    def stop(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=10)
        self.proc = None
        if self.scratch is not None:
            shutil.rmtree(self.scratch, ignore_errors=True)
            self.scratch = None

    def __enter__(self) -> "RunningApp":
        return self

    def __exit__(self, *exc) -> None:
        self.stop()


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def launch(app: App, contract_dir: Path, release: str) -> RunningApp:
    """Start `app` at `release` per `app.launch`; wait for health. Without `app.launch` the app is assumed running."""
    if app.launch is None:
        raise LaunchError(f"{app.name}: the contract has no app.launch; start the app yourself and pass its URL")
    spec = app.launch
    scratch = Path(tempfile.mkdtemp(prefix="semaudit-app-"))
    port = _free_port()
    fmt = {"python": sys.executable, "port": str(port), "release": release, "scratch": str(scratch)}
    cwd = (Path(contract_dir) / spec.cwd).resolve()
    sink_root = Path(spec.sink_root.format(**fmt)) if spec.sink_root else cwd
    env = dict(os.environ)
    env.update({k: v.format(**fmt) for k, v in spec.env.items()})
    if app.release_env:
        env[app.release_env] = release
    log_path = scratch / "app.log"
    log = open(log_path, "wb")
    try:
        proc = subprocess.Popen([c.format(**fmt) for c in spec.cmd], cwd=cwd, env=env, stdout=log, stderr=log,
                                start_new_session=True)
    except OSError as exc:
        log.close()
        shutil.rmtree(scratch, ignore_errors=True)
        raise LaunchError(f"{app.name} {release}: cannot start {spec.cmd[0]!r}: {exc}") from exc
    finally:
        log.close()
    running = RunningApp(release, f"http://127.0.0.1:{port}", sink_root, scratch, proc, log_path)
    deadline = time.monotonic() + spec.startup_timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            tail = log_path.read_text(errors="replace")[-1500:]
            running.stop()
            raise LaunchError(f"{app.name} {release}: exited with {proc.returncode} while starting:\n{tail}")
        try:
            if httpx.get(running.base_url + spec.health, timeout=2).status_code < 500:
                return running
        except httpx.HTTPError:
            pass
        time.sleep(0.1)
    tail = log_path.read_text(errors="replace")[-1500:]
    running.stop()
    raise LaunchError(f"{app.name} {release}: not healthy after {spec.startup_timeout:g}s:\n{tail}")

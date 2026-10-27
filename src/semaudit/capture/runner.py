"""The scenario runner: drives each persona's scenario against one release and records an Episode.

Per persona x scenario: reset the app, create the persona (adapter-built body), seed the world; then for each
step: set the simulated clock (which runs due jobs, so emails and pushes sent between steps exist), let the
adapter perform the verb in the browser, capture the page the step landed on, capture every new email/push in
the sinks, and snapshot every oracle. Nothing here knows an app; the adapter does.
"""

from __future__ import annotations

import hashlib
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from ..adapters.base import Session, StepResult, load_adapter
from ..adapters.hooks import HookClient, HookError, OracleClient
from ..contract.schema import Contract, Persona, Scenario, Step, Surface, load_contract, resolve_time
from ..story.episode import (Capture, Element, Episode, NotMeasured, OracleReading, StepRecord, BBox,
                             episode_path)
from . import sinks
from .dom import find_elements
from .launcher import LaunchError, RunningApp, launch

VIEWPORT = {"width": 1280, "height": 900}


@dataclass
class _StepCtx:
    seq: int
    at: datetime
    rec: StepRecord
    n: int = 0
    phase: str = "step"


@dataclass
class _EpisodeCtx:
    release: str
    persona: Persona
    scenario: Scenario
    app: RunningApp
    out_dir: Path                         # captures/<release>/<persona>__<scenario>, under the run dir
    seen: dict[str, set[str]] = field(default_factory=dict)
    step: _StepCtx | None = None


class Runner:
    def __init__(self, contract_dir: Path, contract: Contract | None = None, *, runs_dir: Path = Path("runs"),
                 run_id: str | None = None, seed: int = 0, adapter: Any = None, sink_root: Path | None = None,
                 base_url: str | None = None, step_timeout_ms: int = 8000, headless: bool = True,
                 browser: Any = None):
        self.contract_dir = Path(contract_dir)
        self.contract = contract or load_contract(self.contract_dir)
        if self.contract.app is None:
            raise LaunchError("the contract has no app.yaml")
        self.runs_dir = Path(runs_dir)
        self.run_id = run_id or "capture-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.seed = seed
        self._adapter = adapter
        self.sink_root = sink_root
        self.base_url = base_url
        self.step_timeout_ms = step_timeout_ms
        self.headless = headless
        self._apps: dict[str, RunningApp] = {}
        self._pw = None
        self._browser = browser                 # a Playwright browser to share; ours to close only if we start it
        self._own_browser = browser is None

    # ---- lifecycle
    @property
    def run_dir(self) -> Path:
        return self.runs_dir / self.run_id

    @property
    def adapter(self) -> Any:
        if self._adapter is None:
            spec = self.contract.app.adapter
            if not spec:
                raise LaunchError("the contract names no app.adapter; scenario verbs cannot be mapped to the app")
            self._adapter = load_adapter(spec, self.contract_dir)
        return self._adapter

    def __enter__(self) -> "Runner":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        if self._browser is not None and self._own_browser:
            self._browser.close()
            self._browser = None
        if self._pw is not None:
            self._pw.stop()
            self._pw = None
        for app in self._apps.values():
            app.stop()
        self._apps.clear()

    def _browser_(self):
        if self._browser is None:
            from playwright.sync_api import sync_playwright
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=self.headless)
        return self._browser

    def _app(self, release: str) -> RunningApp:
        if release not in self._apps:
            if self.contract.app.launch is None:
                self._apps[release] = RunningApp(release, self.base_url or self.contract.app.base_url, self.sink_root)
            else:
                self._apps[release] = launch(self.contract.app, self.contract_dir, release)
        return self._apps[release]

    # ---- public
    def capture(self, release: str, personas: list[str] | None = None) -> list[Episode]:
        wanted = personas or [p.id for p in self.contract.personas]
        out: list[Episode] = []
        for pid in wanted:
            persona = self.contract.persona(pid)
            for scenario in self.contract.scenario_for(pid):
                ep = self.run_episode(release, persona, scenario)
                ep.write(episode_path(self.runs_dir, self.run_id, release, persona.id, scenario.id))
                out.append(ep)
        return out

    def run_episode(self, release: str, persona: Persona, scenario: Scenario) -> Episode:
        contract, adapter = self.contract, self.adapter
        app = self._app(release)
        http = httpx.Client(timeout=15.0)
        hooks = HookClient(app.base_url, contract.app.hooks, http)
        oracles = OracleClient(app.base_url, contract.oracles, http)

        reset = hooks.reset()
        build = adapter.app_build(reset) if hasattr(adapter, "app_build") else release
        persona_resp = hooks.persona(adapter.persona_body(persona, scenario.day0))
        if persona.world and hooks.has("world"):
            hooks.world(adapter.world_body(persona) if hasattr(adapter, "world_body") else persona.world)

        ep = Episode(release=release, persona=persona.id, scenario=scenario.id, seed=self.seed, app_build=build,
                     started_wall=datetime.now(timezone.utc).isoformat(), day0=scenario.day0,
                     clock_measured=hooks.has("clock"))
        out_dir = self.run_dir / "captures" / release / f"{persona.id}__{scenario.id}"
        if out_dir.exists():
            shutil.rmtree(out_dir)
        ectx = _EpisodeCtx(release, persona, scenario, app, out_dir)
        sink_surfaces = [s for s in contract.surfaces if s.sink and s.kind in ("email", "push")]
        for s in sink_surfaces:
            d = self._sink_dir(ectx, s)
            ectx.seen[s.id] = {p.name for p in d.glob("*.json")} if d and d.exists() else set()
            if not hooks.has("clock"):
                ep.not_measured.append(NotMeasured(surface=s.id, reason="no clock hook: time-triggered sends are not driven"))
            if d is None:
                ep.not_measured.append(NotMeasured(surface=s.id, reason="sink location unknown (no app.launch / sink_root)"))

        context = self._browser_().new_context(viewport=VIEWPORT, device_scale_factor=1, locale="en-US",
                                               timezone_id="UTC", reduced_motion="reduce", color_scheme="light",
                                               accept_downloads=True, base_url=app.base_url)
        page = context.new_page()
        page.set_default_timeout(self.step_timeout_ms)
        sess = Session(release, app.base_url, persona, scenario, page, http, self.seed, persona_resp)
        sess._capture = lambda surface: self._capture_page(ectx, sess, surface)
        try:
            if hasattr(adapter, "start_session"):
                adapter.start_session(sess, persona_resp)
            ep.initial_state = oracles.snapshot(adapter.oracle_params(persona, sess))
            for seq, step in enumerate(scenario.steps, 1):
                ep.steps.append(self._run_step(ectx, sess, hooks, oracles, ep, seq, step))
            if ep.steps:
                last = ectx.step
                last.phase = "final_drain"
                last.rec.captures.extend(self._drain(ectx, sink_surfaces, last))
        finally:
            context.close()
            http.close()
        return ep

    # ---- one step
    def _run_step(self, ectx: _EpisodeCtx, sess: Session, hooks: HookClient, oracles: OracleClient, ep: Episode,
                  seq: int, step: Step) -> StepRecord:
        adapter = self.adapter
        at = resolve_time(step.at, ectx.scenario.day0)
        rec = StepRecord(seq=seq, at=at, do=step.do, params=step.params, when_offered=step.when_offered,
                         status="done")
        sctx = _StepCtx(seq, at, rec)
        ectx.step = sctx
        error: str | None = None

        if hooks.has("clock"):
            body = adapter.clock_body(at) if hasattr(adapter, "clock_body") else {"set": at.isoformat()}
            try:
                rec.clock = {"sent": body, "answer": self._set_clock(hooks, body)}
            except HookError as exc:
                error = f"clock hook failed: {exc}"

        result: StepResult | None = None
        if error is None:
            try:
                result = adapter.run_step(step, sess)
            except Exception as exc:  # noqa: BLE001 - any adapter failure is recorded, never swallowed
                error = f"{type(exc).__name__}: {exc}"
        if result is not None:
            if not result.offered:
                if step.when_offered:
                    rec.status = "skipped_not_offered"
                else:
                    error = f"{step.do!r} is not offered here"
            elif result.error:
                error = result.error

        if result is not None and result.offered:
            if result.landed:
                self._capture_page(ectx, sess, result.landed, chat=result.chat)
            if result.pdf is not None:
                self._capture_pdf(ectx, result.pdf)
        sink_surfaces = [s for s in self.contract.surfaces if s.sink and s.kind in ("email", "push")]
        rec.captures.extend(self._drain(ectx, sink_surfaces, sctx))
        rec.state = oracles.snapshot(adapter.oracle_params(sess.persona, sess))
        if error is not None:
            rec.status, rec.error = "failed", error
        return rec

    @staticmethod
    def _set_clock(hooks: HookClient, body: dict[str, Any]) -> Any:
        return hooks.clock(body)

    # ---- captures
    def _new_id(self, ectx: _EpisodeCtx, sctx: _StepCtx) -> str:
        sctx.n += 1
        return f"{ectx.release}.{ectx.persona.id}.{ectx.scenario.id}.s{sctx.seq:02d}.c{sctx.n:02d}"

    @staticmethod
    def _rel(ectx: _EpisodeCtx, url: str) -> str:
        """Capture urls are relative to the app (the launched port is random, so an absolute url is not reproducible)."""
        return url[len(ectx.app.base_url):] if url.startswith(ectx.app.base_url) else url

    def _write(self, ectx: _EpisodeCtx, cid: str, role: str, ext: str, data: bytes, cap: Capture, hashed=True) -> None:
        ectx.out_dir.mkdir(parents=True, exist_ok=True)
        path = ectx.out_dir / f"{cid}.{role}.{ext}"
        path.write_bytes(data)
        cap.files[role] = str(path.relative_to(self.run_dir))
        if hashed:
            cap.sha256[role] = hashlib.sha256(data).hexdigest()

    def _capture_page(self, ectx: _EpisodeCtx, sess: Session, surface_id: str, chat=None) -> None:
        sctx = ectx.step
        surface = next((s for s in self.contract.surfaces if s.id == surface_id), None)
        cid = self._new_id(ectx, sctx)
        page = sess.page
        kind = surface.kind if surface and surface.kind in ("web", "chat") else "web"
        cap = Capture(id=cid, kind=kind, surface=surface_id, at=sctx.at, url=self._rel(ectx, page.url), phase=sctx.phase)
        errors: list[str] = []
        if surface is None:
            errors.append(f"surface {surface_id!r} is not in the contract")
        try:
            self._write(ectx, cid, "dom", "html", page.content().encode("utf-8"), cap)
            self._write(ectx, cid, "screenshot", "png", page.screenshot(full_page=True, animations="disabled",
                                                                       caret="hide"), cap, hashed=False)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"page artifacts: {type(exc).__name__}: {exc}")
        if surface is not None and kind == "chat":
            if chat is None:
                errors.append("the adapter gave no chat transcript")
            else:
                raw = "\n".join(f"{t.who}: {t.text}" for t in chat)
                self._write(ectx, cid, "raw", "txt", raw.encode("utf-8"), cap)
                cap.elements = [Element(locator={"kind": "chat_turn", "turn": i, "span": [0, len(t.text)]},
                                        text=t.text, attrs={"who": t.who, **t.attrs}) for i, t in enumerate(chat)]
        elif surface is not None:
            if not surface.message_selector:
                cap.meta["note"] = "surface has no message_selector; no elements located"
            else:
                try:
                    cap.elements = [Element(locator={"kind": "css", "css": e["css"], "span": [0, len(e["text"])]},
                                            text=e["text"], attrs=e["attrs"], bbox=BBox(**e["bbox"]))
                                    for e in find_elements(page, surface.message_selector)]
                except Exception as exc:  # noqa: BLE001 - e.g. an invalid selector
                    errors.append(f"message_selector {surface.message_selector!r}: {type(exc).__name__}: "
                                  f"{str(exc).splitlines()[0]}")
        if errors:
            cap.status, cap.error = "not_measured", "; ".join(errors)
        sctx.rec.captures.append(cap)

    def _capture_pdf(self, ectx: _EpisodeCtx, pdf) -> None:
        sctx = ectx.step
        cid = self._new_id(ectx, sctx)
        cap = Capture(id=cid, kind="pdf", surface=pdf.surface, at=sctx.at, url=self._rel(ectx, pdf.url), phase=sctx.phase,
                      meta={"filename": pdf.filename})
        self._write(ectx, cid, "pdf", "pdf", pdf.data, cap)
        try:
            cap.elements, extra = sinks.pdf_elements(pdf.data)
            cap.meta.update(extra)
        except Exception as exc:  # noqa: BLE001
            cap.status, cap.error = "not_measured", f"text layer: {type(exc).__name__}: {exc}"
        sctx.rec.captures.append(cap)

    def _sink_dir(self, ectx: _EpisodeCtx, surface: Surface) -> Path | None:
        root = ectx.app.sink_root
        return None if root is None else Path(root) / surface.sink

    def _drain(self, ectx: _EpisodeCtx, surfaces: list[Surface], sctx: _StepCtx) -> list[Capture]:
        """Capture every email/push that is new since the last drain (in message-file order)."""
        out: list[Capture] = []
        for s in surfaces:
            d = self._sink_dir(ectx, s)
            if d is None or not d.exists():
                continue
            seen = ectx.seen.setdefault(s.id, set())
            for path in sorted(d.glob("*.json")):
                if path.name in seen:
                    continue
                seen.add(path.name)
                cid = self._new_id(ectx, sctx)
                try:
                    doc = sinks.read_message(path)
                except (OSError, ValueError) as exc:
                    out.append(Capture(id=cid, kind=s.kind, surface=s.id, at=sctx.at, phase=sctx.phase,
                                       status="not_measured", error=f"{path.name}: {exc}"))
                    continue
                cap = Capture(id=cid, kind=s.kind, surface=s.id, at=sinks.sent_at(doc) or sctx.at, phase=sctx.phase,
                              meta={"sink_file": path.name})
                self._write(ectx, cid, "raw", "json", path.read_bytes(), cap)
                cap.elements = [sinks.sink_element(s.kind, doc, path.stem)]
                out.append(cap)
        return out


def capture_release(contract_dir: Path, release: str, personas: list[str] | None = None, *,
                    runs_dir: Path = Path("runs"), run_id: str | None = None, seed: int = 0) -> list[Episode]:
    """Launch the app for `release`, capture every (or the listed) persona's scenarios, tear the app down."""
    with Runner(contract_dir, runs_dir=runs_dir, run_id=run_id, seed=seed) as r:
        return r.capture(release, personas)

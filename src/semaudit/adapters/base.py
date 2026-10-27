"""The adapter contract: how a scenario verb becomes clicks and requests on one particular app.

The core runner (`semaudit.capture`) is generic. Everything that knows an app (which button a verb presses, how
a Persona becomes the app's persona-hook body, which params fill the oracle templates) lives in an adapter that
the contract names in `app.adapter`. An adapter is a class called `Adapter` with no-argument construction:

    persona_body(persona, day0) -> dict        body of the persona hook
    run_step(step, session) -> StepResult      perform one scenario verb in the browser
    oracle_params(persona, session) -> dict    values for the oracle endpoint templates
  optional:
    world_body(persona) -> dict                body of the world hook (default: persona.world)
    clock_body(at) -> dict                     body of the clock hook (default: {"set": <iso time>})
    start_session(session, persona_response)   e.g. set the cookie that identifies the traveller
    app_build(reset_response) -> str           a build id for the episode (default: the release name)

Drive through the browser wherever a user would; use HTTP only for hooks and oracles.
"""

from __future__ import annotations

import importlib
import importlib.util
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Protocol

from ..contract.schema import Persona, Scenario, Step


class StepFailed(Exception):
    """Raised by an adapter when a verb cannot be performed (unknown verb, broken selector, HTTP error)."""


@dataclass
class ChatTurn:
    who: str                              # "traveller" | the product's side ("concierge")
    text: str
    attrs: dict[str, str] = field(default_factory=dict)   # the marked element's attributes, if the turn carries one


@dataclass
class PdfDownload:
    surface: str                          # contract surface id, e.g. "itinerary"
    url: str
    filename: str
    data: bytes


@dataclass
class StepResult:
    offered: bool = True                  # False: the app does not offer this action here (see Step.when_offered)
    landed: str | None = None             # surface id of the page the step ended on; the runner captures it
    error: str | None = None              # set when the verb ran but the app answered with a failure
    chat: list[ChatTurn] | None = None    # the transcript, when `landed` is a chat surface
    pdf: PdfDownload | None = None        # a document the step downloaded


@dataclass
class Session:
    """What an adapter gets while it runs a step."""
    release: str
    base_url: str
    persona: Persona
    scenario: Scenario
    page: Any                             # a Playwright sync Page, one browser context per episode
    http: Any                             # an httpx.Client on the app's base URL (hooks and oracles only)
    seed: int = 0
    persona_response: Any = None
    scratch: dict[str, Any] = field(default_factory=dict)         # the adapter's own memory across steps
    _capture: Callable[[str], None] | None = None

    def capture(self, surface: str) -> None:
        """Capture the current page now as `surface`, for a page the user saw on the way (e.g. a checkout page)."""
        if self._capture is None:
            raise RuntimeError("this session cannot capture")
        self._capture(surface)


class Adapter(Protocol):
    def persona_body(self, persona: Persona, day0: datetime) -> dict[str, Any]: ...
    def run_step(self, step: Step, session: Session) -> StepResult: ...
    def oracle_params(self, persona: Persona, session: Session) -> dict[str, Any]: ...


def load_adapter(spec: str, contract_dir: Path) -> Any:
    """`spec` is a .py path relative to the contract directory, or a dotted module path. Returns an instance."""
    if spec.endswith(".py") or "/" in spec:
        path = (Path(contract_dir) / spec).resolve()
        if not path.exists():
            raise FileNotFoundError(f"adapter {spec!r}: no such file {path}")
        name = "semaudit_adapter_" + hashlib.sha1(str(path).encode()).hexdigest()[:10]
        mod_spec = importlib.util.spec_from_file_location(name, path)
        assert mod_spec and mod_spec.loader
        mod = importlib.util.module_from_spec(mod_spec)
        mod_spec.loader.exec_module(mod)
    else:
        mod = importlib.import_module(spec)
    cls = getattr(mod, "Adapter", None)
    if cls is None:
        raise AttributeError(f"adapter module {spec!r} defines no class Adapter")
    return cls()

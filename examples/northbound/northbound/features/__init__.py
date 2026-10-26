"""Feature plugin interface.

A feature is a module (northbound/features/<id>.py, or any importable dotted path) that exposes a class
`Feature(BaseFeature)`. A release (northbound/releases/*.py) lists the feature ids it enables, in order, plus
per-feature settings. The runtime never branches on the release name: behaviour differences are either
settings read by a feature, or a different set of feature modules.

Hooks (all optional; ctx is a northbound.runtime.Ctx):

  messages_for(surface, ctx) -> list[Message]
      Messages to show on a page surface: search_results | fare_detail | checkout | confirmation | chat.
      Build them with self.msg(ctx, key, surface, channel, slot=..., action=..., **params). Every message is
      rendered by ONE template macro, which stamps data-feature / data-message-key / data-shown-at.
  on_action(action, ctx, data) -> dict | None
      Reacts to a user action ("search", "open_fare", "opt_in", "book", "upgrade", ...). May schedule or cancel
      jobs, send email/push, change per-feature state. Return {"error": "..."} to refuse an action; return
      None otherwise. Features run in release order, core first.
  on_job(job, ctx)
      Runs a due job this feature scheduled, with the simulated clock set to the job's due time.
  concierge_reply(question, ctx) -> Message | None
      A chat answer, or None to pass. The first feature to answer wins.
  routes(app, env)
      Mount extra HTTP routes (a new page surface, a purchase endpoint). `app` is the FastAPI app; `env` is
      northbound.app.AppEnv with: rt (the Runtime), templates, ctx_for(request, **kw) -> Ctx (401 without a
      traveller), and page(request, template, ctx, surface, status=200, **extra) which collects every feature's
      messages_for(surface) and renders them through the ONE message macro. A new surface needs a template that
      extends base.html and prints slots with the `slot` macro, plus messages_for(surface, ctx) in the features
      that speak there. Called once, after the core routes, in release order.
  oracle_extras(ctx) -> dict | None
      Extra content for GET /api/oracle/booking: "charges" (list of Charge.as_dict() rows, appended as their
      own lines; total_cents is recomputed) and any other keys (merged in).

Ctx helpers a feature may use: ctx.experiment(name) (the traveller's experiment arm), ctx.send_chat(feature, key)
(an in-app chat message, logged and added to the chat history), plus the ones listed in the README.

Class attributes: id (matches examples/northbound/contract/features.yaml), DEFAULTS (settings defaults, overridden
by Release.settings[id]), COPY (extra copy keys this feature needs; merged into the copy table).

Rules: no `if release == ...`; a feature reads self.settings. Sinks: ctx.send_email / ctx.send_push.
Time: only ctx.now (the simulated clock); never datetime.now().
"""
from __future__ import annotations

import importlib
from typing import Any

from ..models import Message


class BaseFeature:
    id: str = ""
    DEFAULTS: dict[str, Any] = {}
    COPY: dict[str, str] = {}

    def __init__(self, settings: dict[str, Any] | None = None):
        self.settings: dict[str, Any] = {**self.DEFAULTS, **(settings or {})}

    def msg(self, ctx, key: str, surface: str, channel: str, **kw) -> Message:
        return ctx.message(self.id, key, surface, channel, **kw)

    def messages_for(self, surface: str, ctx) -> list[Message]:
        return []

    def on_action(self, action: str, ctx, data: dict[str, Any]) -> dict[str, Any] | None:
        return None

    def on_job(self, job, ctx) -> None:
        return None

    def concierge_reply(self, question: str, ctx) -> Message | None:
        return None

    def routes(self, app, env) -> None:
        return None

    def oracle_extras(self, ctx) -> dict[str, Any] | None:
        return None


def load_feature(spec: str, release_settings: dict[str, dict[str, Any]] | None = None) -> BaseFeature:
    """spec is a feature id ("price_watch" -> northbound.features.price_watch) or a dotted module path.
    The feature gets release_settings[Feature.id]."""
    module = importlib.import_module(spec if "." in spec else f"{__name__}.{spec}")
    return module.Feature((release_settings or {}).get(module.Feature.id, {}))

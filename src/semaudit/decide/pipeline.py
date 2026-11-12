"""Evaluate one release of a capture run: episodes -> stories -> extraction -> rules (W9 plumbing)."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path

from semaudit.contract.schema import Contract
from semaudit.extract.messages import extract_unique, message_key, observed_temporal
from semaudit.models.router import Router
from semaudit.relate.interpret import model_interpreter
from semaudit.relate.rules import Entry, evaluate
from semaudit.story.build import story_from_episode
from semaudit.story.episode import Episode
from semaudit.story.model import Story


@dataclass
class ReleaseEval:
    release: str
    episodes: dict[str, Episode]                      # persona -> episode
    results: dict[str, tuple[Story, list[Entry]]]     # persona -> (story, entries), measured personas only
    not_measured: dict[str, list[str]]                # persona -> reasons (failed steps, unreadable surfaces)
    partly: dict[str, list[str]] = field(default_factory=dict)   # persona -> steps never reached because the app
                                                                 # failed an earlier one (evaluated up to there)

    @property
    def complete(self) -> bool:
        return not self.not_measured      # a partly measured persona was evaluated; `partly` says what it missed


def measurement_problems(ep: Episode) -> list[str]:
    """Everything that stops this episode from being a faithful measurement. Any problem excludes the persona
    from the release's results: a story with a hole in it is not evaluated, it is reported as not measured. A step the
    APP failed is not a hole but a finding, and the steps it blocked are reported by `blocked_steps`."""
    out = [f"step {s.seq} ({s.do}): {s.error}" for s in ep.steps if s.status == "failed"]
    out += [f"{c.id}: {c.error}" for c in ep.captures() if c.status == "not_measured"]
    out += [f"{n.surface}: {n.reason}" for n in ep.not_measured]
    out += [f"oracle {name} before the scenario: {r.error or 'not measured'}"
            for name, r in ep.initial_state.items() if r.status == "not_measured"]
    out += [f"oracle {name} after step {s.seq} ({s.do}): {r.error or 'not measured'}"
            for s in ep.steps for name, r in s.state.items() if r.status == "not_measured"]
    return out


def blocked_steps(ep: Episode) -> list[str]:
    """Steps never reached because the app failed an earlier one: the story is evaluated up to there."""
    return [f"step {s.seq} ({s.do}): {s.error}" for s in ep.steps if s.status == "blocked"]


def load_release(run_dir: Path, release: str, contract: Contract, personas: set[str] | None = None
                 ) -> tuple[dict[str, Episode], dict[str, list[str]], dict[str, Story]]:
    """A release's episodes, what could not be measured (and why), and the stories of the measured personas.
    `personas`: the personas this run was meant to capture (default: every persona the contract schedules)."""
    episodes = {}
    for p in sorted((run_dir / "episodes" / release).glob("*.json")):
        ep = Episode.read(p)
        episodes[ep.persona] = ep
    not_measured = {p: probs for p, ep in episodes.items() if (probs := measurement_problems(ep))}
    for sc in contract.scenarios:                          # a persona the contract schedules but nobody captured
        for pid in sc.personas:
            if personas is not None and pid not in personas:
                continue
            ep = episodes.get(pid)
            if ep is None or ep.scenario != sc.id:
                not_measured.setdefault(pid, []).append(f"no {release} episode for scenario {sc.id}")
    stories = {p: story_from_episode(ep, contract) for p, ep in episodes.items() if p not in not_measured}
    return episodes, not_measured, stories


def evaluate_release(run_dir: Path, release: str, contract: Contract, router: Router, *,
                     fresh: bool = False, seed: str = "0", personas: set[str] | None = None,
                     generator=None, readings: dict | None = None) -> ReleaseEval:
    """`personas`: the personas this run was meant to capture (default: every persona the contract schedules).
    `generator`: replaces the code candidate generators and rule evaluation with a function story -> entries
    (the no-generators ablation); extraction still runs, so verification sees the same readings.
    `readings`: a message-key -> extraction map shared with the other release's evaluation; only messages not
    in it are extracted, and the new answers are added to it."""
    episodes, not_measured, stories = load_release(run_dir, release, contract, personas)
    partly = {p: b for p, ep in episodes.items() if p in stories and (b := blocked_steps(ep))}
    msgs = [e for s in stories.values() for e in s.messages()]
    if readings is not None:
        msgs = [m for m in msgs if message_key(m) not in readings]
    ext = extract_unique(msgs, contract, router, fresh=fresh,
                         observed=observed_temporal(stories.values())) if msgs else {}
    if readings is not None:
        readings.update(ext)
        ext = readings
    results = {}
    for persona, s in stories.items():
        for e in s.messages():
            e.extraction = ext[message_key(e)]
        interp = model_interpreter(router, fresh=fresh, rng=random.Random(f"{seed}:{release}:{persona}"))
        results[persona] = (s, generator(s) if generator else evaluate(s, contract, interp))
    return ReleaseEval(release, episodes, results, not_measured, partly)

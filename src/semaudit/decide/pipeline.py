"""Evaluate one release of a capture run: episodes -> stories -> extraction -> rules (W9 plumbing)."""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

from semaudit.contract.schema import Contract
from semaudit.extract.messages import extract_unique
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

    @property
    def complete(self) -> bool:
        return not self.not_measured


def measurement_problems(ep: Episode) -> list[str]:
    """Everything that stops this episode from being a faithful measurement. Any problem excludes the persona
    from the release's results: a story with a hole in it is not evaluated, it is reported as not measured."""
    out = [f"step {s.seq} ({s.do}): {s.error}" for s in ep.steps if s.status == "failed"]
    out += [f"{c.id}: {c.error}" for c in ep.captures() if c.status == "not_measured"]
    out += [f"{n.surface}: {n.reason}" for n in ep.not_measured]
    out += [f"oracle {name} before the scenario: {r.error or 'not measured'}"
            for name, r in ep.initial_state.items() if r.status == "not_measured"]
    out += [f"oracle {name} after step {s.seq} ({s.do}): {r.error or 'not measured'}"
            for s in ep.steps for name, r in s.state.items() if r.status == "not_measured"]
    return out


def evaluate_release(run_dir: Path, release: str, contract: Contract, router: Router, *,
                     fresh: bool = False, seed: str = "0") -> ReleaseEval:
    episodes = {}
    for p in sorted((run_dir / "episodes" / release).glob("*.json")):
        ep = Episode.read(p)
        episodes[ep.persona] = ep
    not_measured = {p: probs for p, ep in episodes.items() if (probs := measurement_problems(ep))}
    for sc in contract.scenarios:                          # a persona the contract schedules but nobody captured
        for pid in sc.personas:
            ep = episodes.get(pid)
            if ep is None or ep.scenario != sc.id:
                not_measured.setdefault(pid, []).append(f"no {release} episode for scenario {sc.id}")
    stories = {p: story_from_episode(ep, contract) for p, ep in episodes.items() if p not in not_measured}
    msgs = [{"feature": e.feature, "channel": e.channel, "text": e.text} for s in stories.values() for e in s.messages()]
    ext = extract_unique(msgs, contract, router, fresh=fresh) if msgs else {}
    results = {}
    for persona, s in stories.items():
        for e in s.messages():
            e.extraction = ext[(e.feature or "", e.channel or "", e.text)]
        interp = model_interpreter(router, fresh=fresh, rng=random.Random(f"{seed}:{release}:{persona}"))
        results[persona] = (s, evaluate(s, contract, interp))
    return ReleaseEval(release, episodes, results, not_measured)

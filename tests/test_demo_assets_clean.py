"""The demo assets name no local path, no coding agent and no non-Meta model (re-audit R2-03).

Every text file under demo/video-assets/ (binaries skipped) is scanned for an absolute home or temp path and for
the name of a coding agent or a non-Meta model. The frames say "no coding agent and no non-Meta model is named on any
frame"; this makes that a check rather than a promise.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "demo" / "video-assets"

LOCAL_PATH = re.compile(r"/Users/|/home/[a-z]|/private/tmp|(?<![\w.])/tmp/|[A-Za-z]:\\Users\\")
NAMES = re.compile(r"\b(?:codex|claude|anthropic|openai|chatgpt|gpt-?\d\w*|gemini|copilot|cursor|opus|sonnet|haiku|"
                   r"llama|mistral|mixtral|grok|qwen|deepseek|devin|windsurf|aider)\b", re.I)

# Lines allowed to match, with the reason. Nothing is allowed today; add (path, substring, reason) only with a reason.
ALLOWED: list[tuple[str, str, str]] = []


def _text_files():
    for p in sorted(ASSETS.rglob("*")):
        if not p.is_file():
            continue
        data = p.read_bytes()
        if b"\0" in data[:8192]:
            continue                                   # binary (images, video, fonts)
        try:
            yield p, data.decode("utf-8")
        except UnicodeDecodeError:
            continue


def _hits(pattern):
    out = []
    for p, text in _text_files():
        rel = str(p.relative_to(ROOT))
        for n, line in enumerate(text.splitlines(), 1):
            if pattern.search(line) and not any(rel == a and s in line for a, s, _ in ALLOWED):
                out.append(f"{rel}:{n}: {line.strip()[:120]}")
    return out


def test_the_scan_sees_the_assets():
    assert sum(1 for _ in _text_files()) > 10            # the guard is not vacuous


def test_no_absolute_home_or_temp_path():
    hits = _hits(LOCAL_PATH)
    assert not hits, "local paths in demo/video-assets:\n" + "\n".join(hits)


def test_no_coding_agent_or_non_meta_model_name():
    hits = _hits(NAMES)
    assert not hits, "agent or non-Meta model names in demo/video-assets:\n" + "\n".join(hits)


def test_the_patterns_bite():
    for line in ("built into /private/tmp/x/page-design", "see /Users/someone/src", "Claude Opus alone, run 1",
                 "GPT-4o baseline", "made with Cursor"):
        assert LOCAL_PATH.search(line) or NAMES.search(line), line
    for line in ("Muse Spark Open (on Baseten)", "meta-models/muse-spark-open-1026", "spree-plain-agent-protocol",
                 "runs/recording-2026-11-01/shots"):
        assert not (LOCAL_PATH.search(line) or NAMES.search(line)), line

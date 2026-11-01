"""Record what the built-in providers send, so a router change can be proven byte-identical for them.

    python3 scripts/router_golden.py          # writes tests/fixtures/router_golden.json (offline; no model call)

For meta, baseten and anthropic, one schema call and one plain call: the URL (or SDK), the request body, the auth
header with the key replaced by its env-var name, and the cache digest. tests/test_router_config_providers.py
compares a fresh capture against this file.
"""

import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import httpx  # noqa: E402

from semaudit.models import router as R  # noqa: E402

OUT = ROOT / "tests" / "fixtures" / "router_golden.json"
KEYS = {"META_MODEL_API_KEY": "key-meta", "BASETEN_API_KEY": "key-baseten", "ANTHROPIC_API_KEY": "key-anthropic"}
SCHEMA = {"type": "object", "properties": {"ok": {"type": ["string", "null"]}}, "required": ["ok"],
          "additionalProperties": False}
MSGS = [{"role": "system", "content": "S"}, {"role": "user", "content": "U"}]
CASES = [("meta", "muse-spark-1.3"), ("baseten", "meta-models/muse-spark-open-1026"), ("anthropic", "claude-opus-5-5")]


def redact(s):
    for env, k in KEYS.items():
        s = s.replace(k, f"<{env}>")
    return s


def capture() -> dict:
    import os
    os.environ.update(KEYS)
    seen: list = []

    def post(url, json=None, headers=None, timeout=None):
        seen.append({"url": url, "headers": {k: redact(v) for k, v in (headers or {}).items()}, "json": json,
                     "timeout": timeout})
        return SimpleNamespace(status_code=200, json=lambda: {"choices": [{"message": {"content": '{"ok": "y"}'},
                                                                           "finish_reason": "stop"}],
                                                              "usage": {"prompt_tokens": 1, "completion_tokens": 1}})

    class Stream:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get_final_message(self):
            return SimpleNamespace(model_dump=lambda: {"id": "m", "model": "claude-opus-5-5", "stop_reason": "end_turn",
                                                       "content": [{"type": "text", "text": '{"ok": "y"}'}],
                                                       "usage": {"input_tokens": 1, "output_tokens": 1}})

    class Client:
        def __init__(self, api_key=None, timeout=None, max_retries=None):
            seen.append({"sdk": "anthropic", "api_key": redact(api_key), "timeout": timeout,
                         "max_retries": max_retries})
            self.messages = SimpleNamespace(stream=lambda **p: (seen.append({"params": p}), Stream())[1])

    import anthropic
    orig_post, orig_client = httpx.post, anthropic.Anthropic
    httpx.post, anthropic.Anthropic = post, Client
    out = {}
    try:
        with tempfile.TemporaryDirectory() as d:
            r = R.Router(root=Path(d))
            for provider, model in CASES:
                for kind in ("schema", "plain"):
                    seen.clear()
                    r.roles["g"] = {"provider": provider, "model": model, "reasoning_effort": "low"}
                    kw = {"schema": SCHEMA, "schema_name": "g", "seed": 3} if kind == "schema" else {}
                    r.complete("g", MSGS, fresh=True, **kw)
                    digests = sorted(p.stem for p in (Path(d) / ".semaudit-cache").glob("*.json"))
                    out[f"{provider}/{kind}"] = {"requests": list(seen), "cache_files": digests}
                    for p in (Path(d) / ".semaudit-cache").glob("*.json"):
                        p.unlink()
    finally:
        httpx.post, anthropic.Anthropic = orig_post, orig_client
    return json.loads(json.dumps(out, sort_keys=True))


if __name__ == "__main__":
    OUT.write_text(json.dumps(capture(), indent=1, sort_keys=True) + "\n")
    print(f"wrote {OUT}")

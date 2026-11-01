"""An email's own send time is used only when the app runs on the simulated clock; otherwise the message is placed
at the step that received it (Spree: Mailpit's wall-clock Date was 4 days before every simulated step)."""
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from semaudit.capture import runner as R

STEP = datetime(2026, 11, 2, 10, 10, tzinfo=UTC)
WALL = "2026-10-29T03:22:16+00:00"


def _drain(tmp_path, clock):
    d = tmp_path / "order_email_html"
    d.mkdir()
    (d / "m1.json").write_text(json.dumps({"message_id": "m1", "sent_at": WALL, "headers": {}, "text": "Shipping $0.00"}))
    r = R.Runner.__new__(R.Runner)
    r._sink_dir = lambda ectx, s: d
    r._new_id = lambda ectx, sctx: "c1"
    r._write = lambda *a, **k: None
    ectx = SimpleNamespace(seen={}, clock=clock)
    sctx = SimpleNamespace(at=STEP, phase="step")
    surface = SimpleNamespace(id="order_email_html", kind="email")
    return r._drain(ectx, [surface], sctx)[0]


def test_wall_clock_send_time_is_not_the_message_time_without_a_clock_hook(tmp_path):
    cap = _drain(tmp_path, clock=False)
    assert cap.at == STEP
    assert cap.meta["sent_at_wall"] == WALL


def test_send_time_is_used_when_the_app_runs_on_the_simulated_clock(tmp_path):
    cap = _drain(tmp_path, clock=True)
    assert cap.at == datetime.fromisoformat(WALL)
    assert "sent_at_wall" not in cap.meta


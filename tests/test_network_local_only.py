"""app.network: local_only — the capture browser reaches only the app under audit (loopback). Every other request
is aborted before it leaves the machine and counted per host in the episode; loopback requests still work."""

import http.server
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from semaudit.capture.runner import _local_only  # noqa: E402


@pytest.fixture(scope="module")
def local_server():
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = b"<html><body><p id=ok>local page</p>" \
                   b"<script src='https://cdn.example-tracker.test/sdk.js'></script>" \
                   b"<link rel=stylesheet href='https://fonts.example.test/css'>" \
                   b"<img src='https://pixel.example.test/p.gif'>" \
                   b"<script>fetch('https://api.example.test/json').catch(()=>{});" \
                   b"fetch('/local.json').then(r=>r.text()).then(t=>document.body.dataset.local=t)</script></body></html>"
            if self.path == "/local.json":
                body = b"reached"
            self.send_response(200)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_only_loopback_is_reached_and_every_blocked_host_is_counted(local_server):
    pw = pytest.importorskip("playwright.sync_api")
    reached = []
    with pw.sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(service_workers="block")
        blocked: dict = {}
        ctx.route("**/*", lambda route: _local_only(route, blocked))
        page = ctx.new_page()
        page.on("requestfinished", lambda r: reached.append(r.url))
        page.goto(local_server + "/")
        page.wait_for_function("document.body.dataset.local === 'reached'", timeout=5000)
        page.wait_for_timeout(300)
        b.close()
    assert set(blocked) == {"cdn.example-tracker.test", "fonts.example.test", "pixel.example.test", "api.example.test"}
    assert all(u.startswith(local_server) for u in reached)          # nothing non-local finished


def test_the_runner_applies_the_policy_and_records_it_on_the_episode(tmp_path):
    pytest.importorskip("playwright.sync_api")
    from semaudit.capture.runner import Runner
    from semaudit.contract.schema import load_contract
    contract_dir = ROOT / "examples" / "northbound" / "contract"
    c = load_contract(contract_dir)
    c.app = c.app.model_copy(update={"network": "local_only"})
    with Runner(contract_dir, contract=c, runs_dir=tmp_path, run_id="net") as r:
        persona = c.personas[0]
        ep = r.run_episode(c.app.releases[-1], persona, c.scenario_for(persona.id)[0])
    assert ep.network == {"policy": "local_only", "blocked": {}}       # Northbound loads nothing external
    assert all(s.status != "failed" for s in ep.steps)

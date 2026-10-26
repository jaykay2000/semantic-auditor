"""Northbound tests. Run from the repo root:  python3 -m pytest examples/northbound/tests"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

APP_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from northbound.app import create_app  # noqa: E402
from northbound.config import Config  # noqa: E402


@pytest.fixture
def make_client(tmp_path):
    """Factory: a fresh app + TestClient on a temp outbox. make_client(release=<name | Release>)."""
    def make(release=None):
        cfg = Config(release="2.3", outbox_dir=tmp_path / "outbox", test_hooks=True)
        app = create_app(cfg, release)
        client = TestClient(app)
        client.rt, client.outbox = app.state.rt, tmp_path / "outbox"
        return client
    return make


@pytest.fixture
def client(make_client):
    return make_client()

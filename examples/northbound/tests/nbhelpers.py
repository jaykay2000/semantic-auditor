"""Small helpers shared by the Northbound tests."""
import json
from html.parser import HTMLParser

MAYA_DEPARTURE = "2026-12-14T08:00:00Z"  # D0 + 42 d - 2 h


def persona(client, pid="maya", party=1, departure=MAYA_DEPARTURE, origin="LIS", destination="BER", flexible=True,
            experiments=None, stay=None):
    body = {"id": pid, "name": pid.title(), "travellers": party, "flexible": flexible,
            "trip": {"origin": origin, "destination": destination, "departure_at": departure}}
    if experiments:
        body["experiments"] = experiments
    if stay:
        body["stay"] = stay
    r = client.post("/api/test/personas", json=body)
    assert r.status_code == 200, r.text
    return {"X-Traveller": pid}


def set_clock(client, iso):
    r = client.post("/api/test/clock", json={"set": iso})
    assert r.status_code == 200, r.text
    return r.json()


def advance(client, delta):
    r = client.post("/api/test/clock", json={"advance": delta})
    assert r.status_code == 200, r.text
    return r.json()


def log(client, traveller=None):
    return client.get("/api/test/messages", params={"traveller": traveller} if traveller else {}).json()["messages"]


def log_tuple(row):
    return (row["shown_at"], row["feature"], row["surface"], row["channel"], row["message_key"])


def outbox(client, kind="email"):
    return [json.loads(p.read_text()) for p in sorted((client.outbox / kind).glob("*.json"))]


class Marked(HTMLParser):
    """Walks a page; records marker elements and visible text nodes inside <main> with their ancestry."""

    def __init__(self):
        super().__init__()
        self.stack, self.markers, self.text_nodes, self.msg_class_elements = [], [], [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag not in ("input", "br", "meta", "link", "img"):
            self.stack.append((tag, a))
        if any(k in a for k in ("data-feature", "data-message-key", "data-shown-at")):
            self.markers.append((tag, a))
        if "msg" in (a.get("class") or "").split():
            self.msg_class_elements.append((tag, a))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        if data.strip() and any(t == "main" for t, _ in self.stack):
            self.text_nodes.append((data.strip(), list(self.stack)))


def parse(html):
    p = Marked()
    p.feed(html)
    return p

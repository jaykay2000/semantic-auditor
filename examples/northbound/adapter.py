"""Northbound's scenario-verb adapter: how each verb in contract/scenarios.yaml becomes clicks and forms.

Everything here knows Northbound (its pages, buttons, cookie, hook bodies). The core runner (semaudit.capture)
does not. Verbs drive the browser like a traveller would; HTTP is used only by the runner, for hooks and oracles.

Loaded by the runner from `app.adapter` in contract/app.yaml (a .py path relative to the contract directory).
"""

from __future__ import annotations

import re
from typing import Any

from semaudit.adapters.base import ChatTurn, PdfDownload, Session, StepFailed, StepResult
from semaudit.contract.schema import Persona, Step

_PRICE = re.compile(r"€\s*([\d,]+(?:\.\d+)?)")


def _fare_id(url: str) -> str | None:
    m = re.search(r"/(?:fare|checkout)/([A-Z]{3}-[A-Z]{3}-[A-Z]{2})", url)
    return m.group(1) if m else None


def _http_error(resp: Any, what: str) -> str | None:
    if resp is not None and resp.status >= 400:
        return f"HTTP {resp.status} for {what}"
    return None


class Adapter:
    # ---- hooks
    def persona_body(self, persona: Persona, context: dict[str, Any]) -> dict[str, Any]:
        """`context` is Northbound's subject.context (contract/subject.yaml), defaults filled, times exact."""
        departure = context["departure_at"].isoformat()
        if context["component"] == "hotel":
            city = (context["hotel"] or "LIS-H1").split("-")[0]
            origin, destination = city, "BER" if city != "BER" else "LIS"   # the app wants a trip for every traveller
        else:
            origin, destination = (context["route"] or "LIS-BER").split("-")
        body: dict[str, Any] = {"id": persona.id, "name": persona.name, "travellers": context["party"],
                                "flexible": context["flexible"],
                                "trip": {"origin": origin, "destination": destination, "departure_at": departure}}
        if persona.experiments:
            body["experiments"] = persona.experiments
        if context["component"] == "hotel":
            body["stay"] = {"hotel": context["hotel"], "check_in_at": departure, "nights": 2, "rooms": 1}
        return body

    def app_build(self, reset_response: Any) -> str:
        return f"northbound@{(reset_response or {}).get('release', 'unknown')}"

    def start_session(self, session: Session, persona_response: Any) -> None:
        """Sign the browser in as the traveller: the persona hook says which cookie identifies them."""
        name, _, value = persona_response["auth"]["cookie"].partition("=")
        session.page.context.add_cookies([{"name": name, "value": value, "url": session.base_url}])

    def oracle_params(self, persona: Persona, session: Session) -> dict[str, Any]:
        route = session.context.get("route")
        return {"traveller": persona.id, "route": route, "fare": f"{route}-NR" if route else None,
                "hotel": session.context.get("hotel")}

    # ---- verbs
    def run_step(self, step: Step, session: Session) -> StepResult:
        fn = getattr(self, f"verb_{step.do}", None)
        if fn is None:
            raise StepFailed(f"unknown verb {step.do!r}")
        return fn(step, session)

    def verb_search(self, step: Step, s: Session) -> StepResult:
        route = step.params.get("route") or s.context.get("route") or "LIS-BER"
        origin, destination = route.split("-")
        resp = s.page.goto(f"/search?origin={origin}&destination={destination}")
        return StepResult(landed="search_results", error=_http_error(resp, "search"))

    def verb_opt_in_price_watch(self, step: Step, s: Session) -> StepResult:
        button = s.page.locator("form[action='/action/opt_in'] button")
        if button.count() == 0:
            return StepResult(offered=False)
        with s.page.expect_navigation() as nav:
            button.first.click()
        return StepResult(landed="search_results", error=_http_error(nav.value, "opt-in"))

    def verb_check_inbox(self, step: Step, s: Session) -> StepResult:
        return StepResult()                  # the runner reads the email sink after every step

    def verb_check_device(self, step: Step, s: Session) -> StepResult:
        return StepResult()                  # the runner reads the push sink after every step

    def verb_leave(self, step: Step, s: Session) -> StepResult:
        return StepResult()

    def verb_open_fare(self, step: Step, s: Session) -> StepResult:
        page = s.page
        if step.params.get("direct") or step.params.get("fare"):
            fare = step.params.get("fare") or f"{s.context.get('route')}-NR"
            resp = page.goto(f"/fare/{fare}")
            return StepResult(landed="fare_detail", error=_http_error(resp, f"fare {fare}"))
        rows = page.locator(".msg-wrap").filter(has=page.locator("a[href^='/fare/']"))
        if rows.count() == 0:
            return StepResult(offered=False)
        priced = []
        for i in range(rows.count()):
            m = _PRICE.search(rows.nth(i).inner_text())
            if m:
                priced.append((float(m.group(1).replace(",", "")), i))
        if not priced:
            raise StepFailed("no fare row shows a price")
        pick = step.params.get("pick", "cheapest")
        _, i = min(priced) if pick == "cheapest" else max(priced)
        with page.expect_navigation() as nav:
            rows.nth(i).locator("a[href^='/fare/']").click()
        return StepResult(landed="fare_detail", error=_http_error(nav.value, "fare"))

    def verb_book(self, step: Step, s: Session) -> StepResult:
        page = s.page
        fare = _fare_id(page.url)
        if fare is None:
            return StepResult(offered=False)
        want = "NR" if step.params.get("fare_type", "non_refundable") == "non_refundable" else "RF"
        if not fare.endswith(want):
            fare = fare[:-2] + want
            resp = page.goto(f"/fare/{fare}")
            if (err := _http_error(resp, f"fare {fare}")):
                return StepResult(landed="fare_detail", error=err)
        link = page.locator(f"a[href='/checkout/{fare}']")
        if link.count() == 0:
            return StepResult(offered=False)
        with page.expect_navigation():
            link.first.click()
        s.capture("checkout")                # the checkout page the traveller reads before paying
        with page.expect_navigation() as nav:
            page.get_by_role("button", name="Book this fare").click()
        return StepResult(landed="confirmation", error=_http_error(nav.value, "booking"))

    def verb_buy_lock(self, step: Step, s: Session) -> StepResult:
        button = s.page.locator("form[action$='/lock'] button")
        if button.count() == 0:
            return StepResult(offered=False)
        with s.page.expect_navigation() as nav:
            button.first.click()
        return StepResult(landed="checkout", error=_http_error(nav.value, "fare lock"))

    def verb_view_itinerary(self, step: Step, s: Session) -> StepResult:
        link = s.page.locator("a[href$='itinerary.pdf']")
        if link.count() == 0:
            return StepResult(offered=False)
        url = s.base_url + link.first.get_attribute("href")
        with s.page.expect_download() as dl:
            link.first.click()
        with open(dl.value.path(), "rb") as f:
            data = f.read()
        return StepResult(pdf=PdfDownload("itinerary", url, dl.value.suggested_filename, data))

    def verb_open_hotel(self, step: Step, s: Session) -> StepResult:
        hotel = step.params.get("hotel") or s.context.get("hotel")
        resp = s.page.goto(f"/hotel/{hotel}")
        if resp is not None and resp.status == 404:        # the release has no hotel pages: not offered
            return StepResult(offered=False)
        return StepResult(landed="hotel_detail", error=_http_error(resp, f"hotel {hotel}"))

    def _open_chat(self, s: Session) -> str | None:
        page = s.page
        if page.url.rstrip("/").endswith("/concierge"):
            return None
        link = page.locator("header a[href='/concierge']")
        if link.count():
            with page.expect_navigation() as nav:
                link.first.click()
        else:
            nav_resp = page.goto("/concierge")
            return _http_error(nav_resp, "concierge")
        return _http_error(nav.value, "concierge")

    def _read_chat(self, s: Session) -> list[ChatTurn]:
        rows = s.page.evaluate("""() => Array.from(document.querySelectorAll('main > .user-turn, main > .msg-wrap')).map(el => {
            if (el.classList.contains('user-turn')) return {who: 'traveller', text: el.innerText.trim(), attrs: {}};
            const m = el.querySelector('.msg'); const attrs = {};
            if (m) for (const a of m.attributes) attrs[a.name] = a.value;
            return {who: 'concierge', text: (m || el).innerText.trim(), attrs};
        })""")
        return [ChatTurn(r["who"], r["text"], r["attrs"]) for r in rows]

    def verb_ask_concierge(self, step: Step, s: Session) -> StepResult:
        if (err := self._open_chat(s)):
            return StepResult(landed="chat", error=err)
        page = s.page
        page.fill("input[name=text]", step.params["question"])
        with page.expect_navigation() as nav:
            page.get_by_role("button", name="Ask").click()
        return StepResult(landed="chat", chat=self._read_chat(s), error=_http_error(nav.value, "concierge"))

    def verb_check_chat(self, step: Step, s: Session) -> StepResult:
        if (err := self._open_chat(s)):
            return StepResult(landed="chat", error=err)
        return StepResult(landed="chat", chat=self._read_chat(s))

"""FastAPI app. `uvicorn northbound.app:app` (from examples/northbound/).

Pages are plain Jinja (no JS needed). Every message goes through the `item` macro in templates/macros.html.
Traveller identity: cookie `nb_traveller=<id>`, or header `X-Traveller`, or query `?traveller=` (header wins).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from . import pdf as pdf_mod
from .catalogue import fare_by_id, fares_for
from .clock import iso, parse_duration, parse_instant
from .config import Config
from .models import Trip
from .releases import Release
from .runtime import Ctx, DuplicateTraveller, Runtime

HERE = Path(__file__).parent
SLOTS = ("summary", "fare_row", "line", "total", "notice")


def create_app(cfg: Config | None = None, release: Release | str | None = None) -> FastAPI:
    cfg = cfg or Config.from_env()
    rt = Runtime(cfg, release)
    app = FastAPI(title=f"Northbound {rt.release.name}", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.rt = rt
    templates = Jinja2Templates(directory=str(HERE / "templates"))

    # ---- helpers ---------------------------------------------------------------------------------------
    def traveller_id(request: Request) -> str | None:
        return (request.headers.get("x-traveller") or request.query_params.get("traveller")
                or request.cookies.get("nb_traveller"))

    def ctx_for(request: Request, **kw: Any) -> Ctx:
        tid = traveller_id(request)
        t = rt.travellers.get(tid) if tid else None
        if t is None:
            raise HTTPException(401, "No traveller. Create one with POST /api/test/personas and send the cookie "
                                     "nb_traveller=<id> (or header X-Traveller).")
        return rt.ctx(t, **kw)

    def page(request: Request, name: str, ctx: Ctx, surface: str, status: int = 200, **extra: Any) -> HTMLResponse:
        msgs = rt.collect(surface, ctx)
        slots = {s: [m for m in msgs if m.slot == s] for s in SLOTS}
        unknown = [m for m in msgs if m.slot not in SLOTS]
        slots["notice"] += unknown
        resp = templates.TemplateResponse(request, name, {"traveller": ctx.traveller, "booking": ctx.booking,
                                                          "slots": slots, "fare": ctx.fare, **extra},
                                          status_code=status)
        resp.headers["Cache-Control"] = "no-store"
        return resp

    def need_fare(fare_id: str):
        fare = fare_by_id(fare_id)
        if fare is None:
            raise HTTPException(404, f"No such fare {fare_id!r}")
        return fare

    @app.exception_handler(HTTPException)
    async def plain_errors(request: Request, exc: HTTPException):  # harness errors, not product messages
        if request.url.path.startswith("/api/"):
            return JSONResponse({"error": exc.detail}, status_code=exc.status_code)
        return HTMLResponse(f"<!doctype html><title>Northbound</title><p>{exc.detail}</p>", status_code=exc.status_code)

    # ---- pages -----------------------------------------------------------------------------------------
    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        return templates.TemplateResponse(request, "home.html", {"traveller": rt.travellers.get(traveller_id(request) or ""),
                                                                 "booking": None, "release": rt.release.name})

    @app.get("/search", response_class=HTMLResponse)
    def search(request: Request, origin: str | None = None, destination: str | None = None, date: str | None = None):
        ctx = ctx_for(request)
        t = ctx.traveller
        o, d = (origin or t.trip.origin).upper(), (destination or t.trip.destination).upper()
        ctx.fares = fares_for(o, d)
        rt.dispatch_action("search", ctx, {"origin": o, "destination": d})
        return page(request, "search.html", ctx, "search_results", origin=o, destination=d,
                    date=date or t.trip.departure_at.date().isoformat())

    @app.get("/fare/{fare_id}", response_class=HTMLResponse)
    def fare_detail(request: Request, fare_id: str):
        ctx = ctx_for(request, fare=need_fare(fare_id))
        rt.dispatch_action("open_fare", ctx, {"fare_id": fare_id})
        return page(request, "fare.html", ctx, "fare_detail")

    @app.get("/checkout/{fare_id}", response_class=HTMLResponse)
    def checkout(request: Request, fare_id: str):
        ctx = ctx_for(request, fare=need_fare(fare_id))
        return page(request, "checkout.html", ctx, "checkout", blocked=rt.blocked_reason(ctx, ctx.fare))

    @app.post("/checkout/{fare_id}")
    def book(request: Request, fare_id: str):
        ctx = ctx_for(request, fare=need_fare(fare_id))
        reason = rt.blocked_reason(ctx, ctx.fare)
        if reason:
            return page(request, "checkout.html", ctx, "checkout", status=409, blocked=reason)
        booking = rt.create_booking(ctx, ctx.fare)
        return RedirectResponse(f"/booking/{booking.id}", status_code=303)

    def own_booking(request: Request, booking_id: str) -> Ctx:
        ctx = ctx_for(request)
        if ctx.booking is None or ctx.booking.id != booking_id:
            raise HTTPException(404, "No such booking for this traveller")
        return ctx

    @app.get("/booking/{booking_id}", response_class=HTMLResponse)
    def confirmation(request: Request, booking_id: str):
        ctx = own_booking(request, booking_id)
        return page(request, "booking.html", ctx, "confirmation")

    @app.post("/booking/{booking_id}/upgrade")
    def upgrade(request: Request, booking_id: str):
        ctx = own_booking(request, booking_id)
        error = rt.upgrade_booking(ctx)
        if error:
            return page(request, "booking.html", ctx, "confirmation", status=409)
        return RedirectResponse(f"/booking/{booking_id}", status_code=303)

    @app.get("/booking/{booking_id}/itinerary.pdf")
    def itinerary(request: Request, booking_id: str):
        ctx = own_booking(request, booking_id)
        msgs = pdf_mod.itinerary_messages(ctx, ctx.booking)
        rt.record(msgs)
        return Response(pdf_mod.render_itinerary(msgs, rt.now), media_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="{booking_id}-itinerary.pdf"'})

    @app.post("/action/{name}")
    def action(request: Request, name: str, next: str = Form("/search")):
        ctx = ctx_for(request)
        outcome = rt.dispatch_action(name, ctx, {})
        if outcome is None:
            raise HTTPException(404, f"No feature handles action {name!r} in release {rt.release.name}")
        if "error" in outcome:
            raise HTTPException(409, outcome["error"])
        return RedirectResponse(next if next.startswith("/") else "/search", status_code=303)

    # ---- concierge -------------------------------------------------------------------------------------
    def ask(ctx: Ctx, text: str):
        history = rt.chats.setdefault(ctx.traveller.id, [])
        history.append({"who": "traveller", "text": text, "message": None})
        for f in rt.features:
            reply = f.concierge_reply(text, ctx)
            if reply is not None:
                rt.record([reply])
                history.append({"who": "concierge", "text": reply.text, "message": reply})
                return reply
        raise HTTPException(404, f"Release {rt.release.name} has no concierge")

    def chat_page(request: Request, ctx: Ctx):
        if not any(f.id == "concierge" for f in rt.features):
            raise HTTPException(404, f"Release {rt.release.name} has no concierge")
        return page(request, "concierge.html", ctx, "chat", history=rt.chats.get(ctx.traveller.id, []))

    @app.get("/concierge", response_class=HTMLResponse)
    def concierge_get(request: Request):
        return chat_page(request, ctx_for(request))

    @app.post("/concierge", response_class=HTMLResponse)
    def concierge_post(request: Request, text: str = Form(...)):
        ctx = ctx_for(request)
        ask(ctx, text)
        return chat_page(request, ctx)

    @app.post("/api/concierge")
    def concierge_api(request: Request, body: dict = Body(...)):
        ctx = ctx_for(request)
        text = str(body.get("text", "")).strip()
        if not text:
            raise HTTPException(422, "text is required")
        r = ask(ctx, text)
        return {"message_key": r.key, "feature": r.feature, "text": r.text, "shown_at": r.shown_at_iso,
                "message_id": r.id}

    # ---- oracles (read-only JSON) ----------------------------------------------------------------------
    def need_known_traveller(request: Request, tid: str | None = None) -> str:
        tid = tid or traveller_id(request)
        if tid not in rt.travellers:
            raise HTTPException(404, f"Unknown traveller {tid!r}")
        return tid

    @app.get("/api/oracle/booking")
    def oracle_booking(request: Request, traveller: str | None = None):
        return rt.oracle_booking(need_known_traveller(request, traveller))

    @app.get("/api/oracle/inventory")
    def oracle_inventory(fare: str):
        f = need_fare(fare)
        return {"fare": f.id, "seats_left": rt.world.seats_left(f.id)}

    @app.get("/api/oracle/forecast")
    def oracle_forecast(route: str):
        return rt.world.forecast(route.upper())

    # ---- test hooks ------------------------------------------------------------------------------------
    if cfg.test_hooks:
        @app.get("/api/test/clock")
        def clock_get():
            return {"now": iso(rt.now), "pending_jobs": [j.summary() for j in rt.jobs.pending()]}

        @app.post("/api/test/clock")
        def clock_post(body: dict = Body(...)):
            try:
                if "advance" in body:
                    ran = rt.advance(parse_duration(str(body["advance"])))
                elif "set" in body:
                    ran = rt.run_until(parse_instant(str(body["set"])))
                else:
                    raise ValueError('send {"advance": "2h"} or {"set": "<iso time>"}')
            except ValueError as exc:
                raise HTTPException(422, str(exc))
            return {"now": iso(rt.now), "jobs_run": [j.summary() for j in ran]}

        @app.post("/api/test/personas")
        def personas(body: dict = Body(...)):
            try:
                tid, trip = str(body["id"]), body["trip"]
                party = int(body.get("travellers", 1))
                if party not in (1, 2, 4):
                    raise ValueError("travellers must be 1, 2 or 4")
                t = rt.create_traveller(tid, str(body.get("name", tid)), party, bool(body.get("flexible", True)),
                                        Trip(str(trip["origin"]).upper(), str(trip["destination"]).upper(),
                                             parse_instant(str(trip["departure_at"]))))
            except DuplicateTraveller as exc:
                raise HTTPException(409, f"traveller {exc} already exists; POST /api/test/reset first")
            except KeyError as exc:
                raise HTTPException(422, f"missing field {exc}")
            except (ValueError, TypeError) as exc:
                raise HTTPException(422, str(exc))
            return {"traveller_id": t.id, "email": t.email, "departure_at": iso(t.trip.departure_at),
                    "auth": {"cookie": f"nb_traveller={t.id}", "header": f"X-Traveller: {t.id}"}}

        @app.post("/api/test/world")
        def world(body: dict = Body(...)):
            for fid, n in (body.get("seats") or {}).items():
                rt.world.seats[need_fare(fid).id] = int(n)
            for route, f in (body.get("forecast") or {}).items():
                rt.world.forecasts[route.upper()] = {"drop": bool(f.get("drop", True)),
                                                     "window_days": int(f.get("window_days", 14))}
            return {"seats": rt.world.seats, "forecasts": rt.world.forecasts}

        @app.post("/api/test/reset")
        def reset():
            rt.reset()
            return {"now": iso(rt.now), "release": rt.release.name}

        @app.get("/api/test/messages")
        def messages(traveller: str | None = None):
            rows = [r for r in rt.log if traveller is None or r["traveller"] == traveller]
            return {"debug_only": True, "note": "server-side message log; debug only, not an oracle",
                    "messages": rows}

    return app


app = create_app()

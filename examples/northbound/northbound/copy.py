"""The copy table: message key -> text. The only place user-facing strings live.

Texts for the canonical keys (pw.*, cg.*) are exactly the strings in the Northbound README and in
tests/fixtures/stories/build.py, so the auditor sees the wording the owner approved. Placeholders use
str.format ({booking_id}, {total} ...). A release can override a key or add keys (Release.copy); a feature
module can add keys with a module-level COPY dict. Tone for 2.3: calm and factual, no urgency, no competing
directives.

Key families:  core.*  (booking flow, confirmation, email, PDF)  .  pw.*  (Price Watch)  .  cg.*  (Concierge)
A key "<key>.subject" is the email subject / push title for key "<key>".
"""
from __future__ import annotations

PW_FORECAST = ("Prices on your dates are likely to drop over the next two weeks. "
               "We suggest waiting; we'll tell you when to book.")
PW_NODROP = "Our forecast: prices on this trip are unlikely to drop before departure."

COPY: dict[str, str] = {
    # --- core: search results, fare detail, checkout ---
    "core.results": "{n} fares from {origin_city} ({origin}) to {destination_city} ({destination}) for {party}.",
    "core.results.fare": "{fare_name}: {total} for {party}, taxes and fees included.",
    "core.fare.summary": "{fare_name}: {total} for {party}, taxes and fees included. Departs {departure}.",
    "core.fare.policy.non_refundable": ("Non-refundable. After you book, you can switch to a refundable fare "
                                        "for {upgrade_fee} during the first 24 hours."),
    "core.fare.policy.refundable": "Refundable. You can cancel any time before departure for a full refund.",
    "core.checkout.fare": "{fare_name} x {travellers}: {amount}",
    "core.checkout.taxes": "Taxes and fees: {amount}",
    "core.checkout.total": "Total to pay today: {amount}",
    "core.checkout.already": "You already have a booking for this trip.",
    "core.checkout.soldout": "This fare is sold out for {party}.",
    # --- core: confirmation, upgrade, email, PDF ---
    "core.confirmed": ("Booked. Your booking {booking_id} from {origin_city} ({origin}) to "
                       "{destination_city} ({destination}) departs {departure}."),
    "core.confirmed.charge": "{label}: {amount}",
    "core.confirmed.total": "Total charged: {total}",
    "core.confirmed.fare_window": ("Fare type: non-refundable. Switching to a refundable fare costs "
                                   "{upgrade_fee} and is available until {until}."),
    "core.confirmed.fare_closed": "Fare type: non-refundable. The 24-hour change window has ended.",
    "core.confirmed.fare_refundable": "Fare type: refundable.",
    "core.email.confirmation": ("Booked. Your booking {booking_id} from {origin_city} ({origin}) to "
                                "{destination_city} ({destination}) departs {departure}. Total charged: {total}."),
    "core.email.confirmation.subject": "Booking confirmed: {booking_id}",
    "core.pdf.itinerary": ("Itinerary. Booked: {booking_id}. {origin_city} ({origin}) to "
                           "{destination_city} ({destination}), departs {departure}. Fare: {fare_name}."),
    "core.pdf.charge": "{label}: {amount}",
    "core.pdf.total": "Total charged: {total}",
    # --- Price Watch ---
    "pw.card": PW_FORECAST,  # canonical wording (shown as a card from 2.4; in 2.3 it is the alert email's text)
    "pw.card.nodrop": PW_NODROP,
    "pw.card.optin": ("Price Watch can email you a price forecast for this trip. "
                      "It stays off unless you turn it on."),
    "pw.card.watching": "Price Watch is on for this trip. We'll email you a forecast shortly.",
    "pw.email.forecast": PW_FORECAST,
    "pw.email.forecast.subject": "Price Watch: forecast for {origin} to {destination}",
    "pw.email.forecast.nodrop": PW_NODROP,
    "pw.email.forecast.nodrop.subject": "Price Watch: forecast for {origin} to {destination}",
    # --- Concierge 1.0: answers only, never proactive ---
    "cg.greeting": "Hi, I'm Concierge. Ask me about your booking, fares, refunds or Price Watch.",
    "cg.answer.status.none": "You don't have a booking yet.",
    "cg.answer.status.booked": "Your booking {booking_id} is confirmed. It departs {departure}.",
    "cg.answer.refund": ("Non-refundable fares can't be cancelled for a refund. In the first 24 hours after "
                         "booking you can switch to a refundable fare for {upgrade_fee}. Refundable fares "
                         "can be cancelled any time before departure."),
    "cg.answer.deal.booked": "I can't say whether a price is a good deal. I can tell you what you were charged: {total}.",
    "cg.answer.deal.none": "I can't say whether a price is a good deal. The fares for your trip are on the search page.",
    "cg.answer.when": "I can't recommend when to book. The fares for your trip are on the search page.",
    "cg.answer.price_watch": ("Price Watch is optional. If you turn it on from the search page, we email you one "
                              "price forecast for the trip. It stops when you book."),
    "cg.answer.fallback": ("I can answer questions about your booking, fares, refunds and Price Watch. "
                           "Try asking: What is my booking status?"),
}


def render(table: dict[str, str], key: str, **params: object) -> str:
    """Text for `key`. A missing key is a bug, not a blank: it raises KeyError."""
    return table[key].format_map(params)

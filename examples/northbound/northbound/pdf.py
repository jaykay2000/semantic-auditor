"""Itinerary PDF (fpdf2). Text stays extractable; the message keys it contains go in the PDF keywords."""
from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

from .catalogue import fare_by_id, money
from .models import Message

FONT = Path(__file__).parent / "fonts" / "DejaVuSans.ttf"


def itinerary_messages(ctx, booking) -> list[Message]:
    fare = fare_by_id(booking.fare_id)
    msgs = [ctx.message("core", "core.pdf.itinerary", "itinerary", "pdf", booking_id=booking.id,
                        fare_name=fare.name, **ctx.common_params())]
    for c in booking.charges:
        msgs.append(ctx.message("core", "core.pdf.charge", "itinerary", "pdf", label=c.label,
                                amount=money(c.amount_cents)))
    msgs.append(ctx.message("core", "core.pdf.total", "itinerary", "pdf", total=money(booking.total_cents)))
    return msgs


def render_itinerary(msgs: list[Message], now) -> bytes:
    pdf = FPDF()
    pdf.add_font("DejaVu", fname=str(FONT))
    pdf.set_creation_date(now)  # simulated time: the same run produces the same metadata
    pdf.set_title("Northbound itinerary")
    pdf.set_author("Northbound")
    pdf.set_creator("Northbound")
    pdf.set_keywords(", ".join(dict.fromkeys(m.key for m in msgs)))
    pdf.set_subject(", ".join(dict.fromkeys(m.feature for m in msgs)))
    pdf.add_page()
    pdf.set_font("DejaVu", size=16)
    pdf.cell(0, 12, "Northbound", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", size=11)
    for m in msgs:
        pdf.multi_cell(0, 7, m.text, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)
    return bytes(pdf.output())

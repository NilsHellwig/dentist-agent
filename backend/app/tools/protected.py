from datetime import datetime

from pydantic import BaseModel
from pydantic_ai import RunContext
from sqlalchemy import select

from app import booking
from app.booking import Treatment
from app.db.models import Appointment, AppointmentStatus, Invoice
from app.deps import CallSession, PendingChange
from app.tools.public import MONTHS, WEEKDAYS

NOT_VERIFIED = "Nicht verifiziert: zuerst verify_customer mit Kundennummer und Geburtsdatum aufrufen."


class AppointmentInfo(BaseModel):
    id: int
    starts_at: datetime
    weekday: str  # computed in code; small models get weekdays wrong otherwise
    treatment: str


class InvoiceInfo(BaseModel):
    description: str
    amount_eur: float
    status: str


def get_appointments(ctx: RunContext[CallSession]) -> list[AppointmentInfo] | str:
    """Lists the upcoming appointments of the verified customer."""
    s = ctx.deps
    if s.customer_id is None:
        return NOT_VERIFIED
    with s.db_factory() as db:
        rows = db.scalars(
            select(Appointment)
            .where(
                Appointment.customer_id == s.customer_id,
                Appointment.status == AppointmentStatus.SCHEDULED,
                Appointment.starts_at > datetime.now(),
            )
            .order_by(Appointment.starts_at)
        )
        return [AppointmentInfo(id=a.id, starts_at=a.starts_at, weekday=WEEKDAYS[a.starts_at.weekday()], treatment=a.treatment) for a in rows]


def _when(starts_at: datetime) -> str:
    # "4. November" instead of "04.11.2026": the model misreads leading zeros (said "vierzehnten" for 04.11.)
    year = f" {starts_at.year}" if starts_at.year != datetime.now().year else ""
    return f"{WEEKDAYS[starts_at.weekday()]}, {starts_at.day}. {MONTHS[starts_at.month - 1]}{year} um {starts_at:%H:%M} Uhr"


def _propose(s: CallSession, change: PendingChange) -> str:
    s.pending = change
    # a ready-made question: left to itself, the model announced proposals as done ("Ich habe ... verschoben")
    return (
        f"Vorgemerkt, aber noch NICHT ausgeführt. Sage nicht, dass etwas erledigt ist. Stelle dem Kunden jetzt genau diese Frage: "
        f"\"{change.question}\" Rufe confirm_change erst auf, wenn er in seiner nächsten Antwort klar zustimmt."
    )


def propose_booking(ctx: RunContext[CallSession], starts_at: datetime, treatment: Treatment) -> str:
    """Proposes a booking for the verified customer and returns the question to ask; nothing is booked until confirm_change. Check the time with free_slots first.

    Args:
        starts_at: Start as YYYY-MM-DDTHH:MM.
        treatment: Treatment, exactly one of the listed names.
    """
    s = ctx.deps
    if s.customer_id is None:
        return NOT_VERIFIED
    with s.db_factory() as db:
        try:
            booking.check_slot(db, starts_at)
        except booking.BookingError as e:
            return str(e)
    return _propose(
        s, PendingChange("book", s.turn, f"Soll ich Ihnen einen Termin für {treatment} am {_when(starts_at)} buchen?", starts_at=starts_at, treatment=treatment)
    )


def _own_appointment(db, s: CallSession, appointment_id: int) -> Appointment | None:
    appt = db.get(Appointment, appointment_id)
    if appt is None or appt.customer_id != s.customer_id or appt.status != AppointmentStatus.SCHEDULED:
        return None
    return appt


def propose_reschedule(ctx: RunContext[CallSession], appointment_id: int, new_starts_at: datetime) -> str:
    """Proposes moving one of the customer's own appointments and returns the question to ask; nothing changes until confirm_change. Check the new time with free_slots first.

    Args:
        appointment_id: ID from get_appointments.
        new_starts_at: New start as YYYY-MM-DDTHH:MM.
    """
    s = ctx.deps
    if s.customer_id is None:
        return NOT_VERIFIED
    with s.db_factory() as db:
        appt = _own_appointment(db, s, appointment_id)
        if appt is None:
            return "Termin nicht gefunden."
        try:
            booking.check_slot(db, new_starts_at, ignore_id=appt.id)
        except booking.BookingError as e:
            return str(e)
        question = f"Soll ich Ihren Termin für {appt.treatment} von {_when(appt.starts_at)} auf {_when(new_starts_at)} verschieben?"
    return _propose(s, PendingChange("reschedule", s.turn, question, starts_at=new_starts_at, appointment_id=appointment_id))


def propose_cancellation(ctx: RunContext[CallSession], appointment_id: int) -> str:
    """Proposes cancelling one of the customer's own appointments and returns the question to ask; nothing changes until confirm_change.

    Args:
        appointment_id: ID from get_appointments.
    """
    s = ctx.deps
    if s.customer_id is None:
        return NOT_VERIFIED
    with s.db_factory() as db:
        appt = _own_appointment(db, s, appointment_id)
        if appt is None:
            return "Termin nicht gefunden."
        question = f"Soll ich Ihren Termin für {appt.treatment} am {_when(appt.starts_at)} wirklich stornieren?"
    return _propose(s, PendingChange("cancel", s.turn, question, appointment_id=appointment_id))


def confirm_change(ctx: RunContext[CallSession]) -> str:
    """Carries out the proposed booking, reschedule or cancellation. Only call this after the customer explicitly said yes to it."""
    s = ctx.deps
    change = s.pending
    if s.customer_id is None:
        return NOT_VERIFIED
    if change is None or s.turn > change.turn + 1:
        s.pending = None
        return "Es gibt keine offene Änderung. Schlage sie erneut vor und lass sie bestätigen."
    if s.turn == change.turn:
        # enforced in code: the customer must have answered the question first
        return f"Noch nicht bestätigt. Frage den Kunden zuerst: \"{change.question}\""
    s.pending = None
    with s.db_factory() as db:
        try:
            if change.action == "book":
                appt = booking.book(db, s.customer_id, change.starts_at, change.treatment)
                return f"Gebucht: {change.treatment} am {_when(appt.starts_at)}."
            appt = _own_appointment(db, s, change.appointment_id)
            if appt is None:
                return "Termin nicht gefunden."
            if change.action == "reschedule":
                booking.reschedule(db, appt, change.starts_at)
                return f"Verschoben auf {_when(change.starts_at)}."
            booking.cancel(db, appt)
            return "Termin storniert."
        except booking.BookingError as e:
            return str(e)


def get_invoices(ctx: RunContext[CallSession]) -> list[InvoiceInfo] | str:
    """Lists the verified customer's invoices with status (open/paid)."""
    s = ctx.deps
    if s.customer_id is None:
        return NOT_VERIFIED
    with s.db_factory() as db:
        rows = db.scalars(select(Invoice).where(Invoice.customer_id == s.customer_id).order_by(Invoice.issued_on.desc()))
        return [InvoiceInfo(description=i.description, amount_eur=float(i.amount_eur), status=i.status) for i in rows]

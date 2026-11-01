from datetime import datetime

from pydantic import BaseModel
from pydantic_ai import RunContext
from sqlalchemy import select

from app import booking
from app.db.models import Appointment, AppointmentStatus, Invoice
from app.deps import CallSession
from app.tools.public import WEEKDAYS

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


def book_appointment(ctx: RunContext[CallSession], starts_at: datetime, treatment: str) -> str:
    """Books an appointment for the verified customer. Check the time with free_slots first.

    Args:
        starts_at: Start as YYYY-MM-DDTHH:MM.
        treatment: Treatment in German, e.g. 'Kontrolluntersuchung'.
    """
    s = ctx.deps
    if s.customer_id is None:
        return NOT_VERIFIED
    with s.db_factory() as db:
        try:
            appt = booking.book(db, s.customer_id, starts_at, treatment)
        except booking.BookingError as e:
            return str(e)
        return f"Gebucht: {treatment} am {WEEKDAYS[starts_at.weekday()]}, {starts_at:%d.%m.%Y um %H:%M} Uhr (Termin-ID {appt.id})."


def _own_appointment(db, s: CallSession, appointment_id: int) -> Appointment | None:
    appt = db.get(Appointment, appointment_id)
    if appt is None or appt.customer_id != s.customer_id or appt.status != AppointmentStatus.SCHEDULED:
        return None
    return appt


def reschedule_appointment(ctx: RunContext[CallSession], appointment_id: int, new_starts_at: datetime) -> str:
    """Moves one of the customer's own appointments. Check the new time with free_slots first.

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
            booking.reschedule(db, appt, new_starts_at)
        except booking.BookingError as e:
            return str(e)
        return f"Verschoben auf {WEEKDAYS[new_starts_at.weekday()]}, {new_starts_at:%d.%m.%Y um %H:%M} Uhr."


def cancel_appointment(ctx: RunContext[CallSession], appointment_id: int) -> str:
    """Cancels one of the customer's own appointments. Have the customer confirm first.

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
        booking.cancel(db, appt)
        return "Termin storniert."


def get_invoices(ctx: RunContext[CallSession]) -> list[InvoiceInfo] | str:
    """Lists the verified customer's invoices with status (open/paid)."""
    s = ctx.deps
    if s.customer_id is None:
        return NOT_VERIFIED
    with s.db_factory() as db:
        rows = db.scalars(select(Invoice).where(Invoice.customer_id == s.customer_id).order_by(Invoice.issued_on.desc()))
        return [InvoiceInfo(description=i.description, amount_eur=float(i.amount_eur), status=i.status) for i in rows]

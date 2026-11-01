from datetime import datetime

from pydantic import BaseModel
from pydantic_ai import RunContext
from sqlalchemy import select

from app.db.models import Appointment, Invoice
from app.deps import CallSession
from app.tools.public import OPENING_HOURS, SLOT_MINUTES, WEEKDAYS

NOT_VERIFIED = "Nicht verifiziert: zuerst verify_customer mit Kundennummer und Geburtsdatum aufrufen."


class AppointmentInfo(BaseModel):
    id: int
    starts_at: datetime
    weekday: str  # vom Code berechnet, kleine Modelle raten Wochentage sonst falsch
    treatment: str


class InvoiceInfo(BaseModel):
    description: str
    amount_eur: float
    status: str


def _check_slot(starts_at: datetime, db, ignore_id: int | None = None) -> str | None:
    if starts_at <= datetime.now():
        return "Der Zeitpunkt liegt in der Vergangenheit."
    hours = OPENING_HOURS.get(starts_at.weekday())
    if hours is None or not (hours[0] <= starts_at.hour < hours[1]) or starts_at.minute % SLOT_MINUTES:
        return "Außerhalb der Öffnungszeiten oder nicht im 30-Minuten-Raster."
    clash = db.scalar(
        select(Appointment.id).where(
            Appointment.starts_at == starts_at, Appointment.status == "geplant", Appointment.id != (ignore_id or 0)
        )
    )
    return "Dieser Termin ist bereits vergeben." if clash else None


def get_appointments(ctx: RunContext[CallSession]) -> list[AppointmentInfo] | str:
    """Zeigt die kommenden Termine des verifizierten Kunden."""
    s = ctx.deps
    if s.customer_id is None:
        return NOT_VERIFIED
    with s.db_factory() as db:
        rows = db.scalars(
            select(Appointment)
            .where(Appointment.customer_id == s.customer_id, Appointment.status == "geplant", Appointment.starts_at > datetime.now())
            .order_by(Appointment.starts_at)
        )
        return [AppointmentInfo(id=a.id, starts_at=a.starts_at, weekday=WEEKDAYS[a.starts_at.weekday()], treatment=a.treatment) for a in rows]


def book_appointment(ctx: RunContext[CallSession], starts_at: datetime, treatment: str) -> str:
    """Bucht einen Termin für den verifizierten Kunden. Zeit vorher mit free_slots prüfen.

    Args:
        starts_at: Beginn als YYYY-MM-DDTHH:MM.
        treatment: Behandlung, z.B. 'Kontrolluntersuchung'.
    """
    s = ctx.deps
    if s.customer_id is None:
        return NOT_VERIFIED
    with s.db_factory() as db:
        if error := _check_slot(starts_at, db):
            return error
        appt = Appointment(customer_id=s.customer_id, starts_at=starts_at, treatment=treatment)
        db.add(appt)
        db.commit()
        return f"Gebucht: {treatment} am {WEEKDAYS[starts_at.weekday()]}, {starts_at:%d.%m.%Y um %H:%M} Uhr (Termin-ID {appt.id})."


def _own_appointment(db, s: CallSession, appointment_id: int) -> Appointment | None:
    appt = db.get(Appointment, appointment_id)
    if appt is None or appt.customer_id != s.customer_id or appt.status != "geplant":
        return None
    return appt


def reschedule_appointment(ctx: RunContext[CallSession], appointment_id: int, new_starts_at: datetime) -> str:
    """Verschiebt einen eigenen Termin. Neue Zeit vorher mit free_slots prüfen.

    Args:
        appointment_id: ID aus get_appointments.
        new_starts_at: Neuer Beginn als YYYY-MM-DDTHH:MM.
    """
    s = ctx.deps
    if s.customer_id is None:
        return NOT_VERIFIED
    with s.db_factory() as db:
        appt = _own_appointment(db, s, appointment_id)
        if appt is None:
            return "Termin nicht gefunden."
        if error := _check_slot(new_starts_at, db, ignore_id=appt.id):
            return error
        appt.starts_at = new_starts_at
        db.commit()
        return f"Verschoben auf {WEEKDAYS[new_starts_at.weekday()]}, {new_starts_at:%d.%m.%Y um %H:%M} Uhr."


def cancel_appointment(ctx: RunContext[CallSession], appointment_id: int) -> str:
    """Storniert einen eigenen Termin. Vorher beim Kunden bestätigen lassen.

    Args:
        appointment_id: ID aus get_appointments.
    """
    s = ctx.deps
    if s.customer_id is None:
        return NOT_VERIFIED
    with s.db_factory() as db:
        appt = _own_appointment(db, s, appointment_id)
        if appt is None:
            return "Termin nicht gefunden."
        appt.status = "storniert"
        db.commit()
        return "Termin storniert."


def get_invoices(ctx: RunContext[CallSession]) -> list[InvoiceInfo] | str:
    """Zeigt Rechnungen des verifizierten Kunden mit Status (offen/bezahlt)."""
    s = ctx.deps
    if s.customer_id is None:
        return NOT_VERIFIED
    with s.db_factory() as db:
        rows = db.scalars(select(Invoice).where(Invoice.customer_id == s.customer_id).order_by(Invoice.issued_on.desc()))
        return [InvoiceInfo(description=i.description, amount_eur=float(i.amount_eur), status=i.status) for i in rows]

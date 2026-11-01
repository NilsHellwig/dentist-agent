"""Booking rules shared by the agent tools and the admin dashboard.

Error messages are German because both the voice agent and the admin UI pass them on verbatim.
"""

from datetime import date, datetime, time, timedelta
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Appointment, AppointmentStatus

# Opening hours per weekday (0 = Monday); must match knowledge/allgemein/oeffnungszeiten.md
OPENING_HOURS = {0: (8, 17), 1: (8, 17), 2: (8, 17), 3: (8, 17), 4: (8, 13)}
SLOT_MINUTES = 30


class Treatment(StrEnum):
    """Bookable treatments. Values are the German names the agent speaks and the database stores."""

    CHECKUP = "Kontrolluntersuchung"
    PROFESSIONAL_CLEANING = "Professionelle Zahnreinigung"
    CHILD_CHECKUP = "Kinder-Kontrolle"
    FLUORIDATION = "Fluoridierung"
    CONSULTATION = "Beratung"


class BookingError(Exception):
    pass


def check_slot(db: Session, starts_at: datetime, ignore_id: int | None = None) -> None:
    """Raises BookingError if the slot can't be booked. `ignore_id` lets an appointment keep its own slot when rescheduled."""
    if starts_at <= datetime.now():
        raise BookingError("Der Zeitpunkt liegt in der Vergangenheit.")
    hours = OPENING_HOURS.get(starts_at.weekday())
    # closed days have no entry; slots must start on the grid and before closing time
    if hours is None or not (hours[0] <= starts_at.hour < hours[1]) or starts_at.minute % SLOT_MINUTES:
        raise BookingError("Außerhalb der Öffnungszeiten oder nicht im 30-Minuten-Raster.")
    # cancelled appointments free their slot
    clash = db.scalar(
        select(Appointment.id).where(
            Appointment.starts_at == starts_at,
            Appointment.status == AppointmentStatus.SCHEDULED,
            Appointment.id != (ignore_id or 0),
        )
    )
    if clash:
        raise BookingError("Dieser Termin ist bereits vergeben.")


def free_slots(db: Session, day: date) -> list[datetime]:
    """All bookable start times on `day` that are in the future and not taken."""
    hours = OPENING_HOURS.get(day.weekday())
    if hours is None:
        return []
    start, end = datetime.combine(day, time(hours[0])), datetime.combine(day, time(hours[1]))
    taken = set(
        db.scalars(
            select(Appointment.starts_at).where(
                Appointment.status == AppointmentStatus.SCHEDULED, Appointment.starts_at >= start, Appointment.starts_at < end
            )
        )
    )
    now = datetime.now()
    slots, t = [], start
    while t < end:
        if t > now and t not in taken:
            slots.append(t)
        t += timedelta(minutes=SLOT_MINUTES)
    return slots


def book(db: Session, customer_id: int, starts_at: datetime, treatment: Treatment) -> Appointment:
    check_slot(db, starts_at)
    appt = Appointment(customer_id=customer_id, starts_at=starts_at, treatment=treatment)
    db.add(appt)
    db.commit()
    return appt


def reschedule(db: Session, appt: Appointment, new_starts_at: datetime) -> None:
    if appt.status != AppointmentStatus.SCHEDULED:
        raise BookingError("Stornierte Termine können nicht verschoben werden.")
    check_slot(db, new_starts_at, ignore_id=appt.id)
    appt.starts_at = new_starts_at
    db.commit()


def cancel(db: Session, appt: Appointment) -> None:
    # appointments are never deleted, so the admin dashboard keeps the history
    appt.status = AppointmentStatus.CANCELLED
    db.commit()

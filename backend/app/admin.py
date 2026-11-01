"""Admin dashboard API: one shared login from .env, session in a signed cookie.

The frontend proxies /admin/api/* here, so the cookie is same-origin with the dashboard.
"""

import asyncio
import hashlib
import hmac
import secrets
import time
from collections.abc import Iterator
from datetime import date, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app import booking
from app.booking import Treatment
from app.config import settings
from app.db.models import Appointment, AppointmentStatus, Customer, Invoice, InvoiceStatus, SessionLocal

COOKIE_NAME = "admin_session"
COOKIE_PATH = "/admin"
SESSION_SECONDS = 8 * 3600
FAILED_LOGIN_DELAY_S = 1.0
FIRST_CUSTOMER_NUMBER = 10001


def _sign(payload: str) -> str:
    return hmac.new(settings.admin_session_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def _session_token() -> str:
    expires = str(int(time.time()) + SESSION_SECONDS)
    return f"{expires}.{_sign(expires)}"


def _valid_token(token: str | None) -> bool:
    expires, _, sig = (token or "").partition(".")
    return expires.isdigit() and hmac.compare_digest(sig, _sign(expires)) and int(expires) > time.time()


def require_enabled() -> None:
    if not settings.admin_enabled:
        raise HTTPException(503, "Admin-Bereich ist nicht konfiguriert.")


def require_admin(admin_session: Annotated[str | None, Cookie()] = None) -> None:
    if not _valid_token(admin_session):
        raise HTTPException(401, "Nicht angemeldet.")


def get_db() -> Iterator[Session]:
    with SessionLocal() as db:
        yield db


DB = Annotated[Session, Depends(get_db)]

router = APIRouter(prefix="/admin/api", dependencies=[Depends(require_enabled)])
protected = APIRouter(dependencies=[Depends(require_admin)])


class Credentials(BaseModel):
    username: str
    password: str


@router.post("/login", status_code=204)
async def login(creds: Credentials, response: Response) -> None:
    # evaluate both comparisons so timing doesn't reveal which field was wrong
    user_ok = secrets.compare_digest(creds.username.encode(), settings.admin_username.encode())
    password_ok = secrets.compare_digest(creds.password.encode(), settings.admin_password.encode())
    if not (user_ok and password_ok):
        await asyncio.sleep(FAILED_LOGIN_DELAY_S)
        raise HTTPException(401, "Benutzername oder Passwort falsch.")
    response.set_cookie(
        COOKIE_NAME,
        _session_token(),
        max_age=SESSION_SECONDS,
        path=COOKIE_PATH,
        httponly=True,
        samesite="strict",
        secure=settings.admin_cookie_secure,
    )


@router.post("/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path=COOKIE_PATH, httponly=True, samesite="strict", secure=settings.admin_cookie_secure)


class CustomerRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_number: str
    first_name: str
    last_name: str


class CustomerOut(CustomerRef):
    birth_date: date


class AppointmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    starts_at: datetime
    treatment: str
    status: AppointmentStatus
    customer: CustomerRef


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    issued_on: date
    description: str
    amount_eur: float
    status: InvoiceStatus
    customer: CustomerRef


class CustomerDetail(CustomerOut):
    appointments: list[AppointmentOut]
    invoices: list[InvoiceOut]


class CustomerIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=64)
    last_name: str = Field(min_length=1, max_length=64)
    birth_date: date


class AppointmentIn(BaseModel):
    customer_id: int
    starts_at: datetime
    treatment: Treatment


class RescheduleIn(BaseModel):
    starts_at: datetime


class InvoiceStatusIn(BaseModel):
    status: InvoiceStatus


def _matches(q: str):
    pattern = f"%{q.strip()}%"
    return or_(
        Customer.customer_number.ilike(pattern),
        Customer.first_name.ilike(pattern),
        Customer.last_name.ilike(pattern),
        (Customer.first_name + " " + Customer.last_name).ilike(pattern),
    )


def _get_or_404(db: Session, model, id_: int):
    obj = db.get(model, id_)
    if obj is None:
        raise HTTPException(404, "Nicht gefunden.")
    return obj


def _book_or_409(fn, *args):
    try:
        return fn(*args)
    except booking.BookingError as e:
        raise HTTPException(409, str(e)) from e


@protected.get("/appointments")
def list_appointments(
    db: DB,
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: date | None = None,
    status: AppointmentStatus | None = None,
    q: str = "",
) -> list[AppointmentOut]:
    stmt = select(Appointment).join(Appointment.customer).options(joinedload(Appointment.customer)).order_by(Appointment.starts_at)
    if from_:
        stmt = stmt.where(Appointment.starts_at >= datetime.combine(from_, datetime.min.time()))
    if to:
        stmt = stmt.where(Appointment.starts_at < datetime.combine(to + timedelta(days=1), datetime.min.time()))
    if status:
        stmt = stmt.where(Appointment.status == status)
    if q.strip():
        stmt = stmt.where(_matches(q))
    return list(db.scalars(stmt))


@protected.post("/appointments", status_code=201)
def create_appointment(body: AppointmentIn, db: DB) -> AppointmentOut:
    _get_or_404(db, Customer, body.customer_id)
    appt = _book_or_409(booking.book, db, body.customer_id, body.starts_at, body.treatment)
    db.refresh(appt)
    return appt


@protected.patch("/appointments/{appointment_id}")
def reschedule_appointment(appointment_id: int, body: RescheduleIn, db: DB) -> AppointmentOut:
    appt = _get_or_404(db, Appointment, appointment_id)
    _book_or_409(booking.reschedule, db, appt, body.starts_at)
    return appt


@protected.post("/appointments/{appointment_id}/cancel")
def cancel_appointment(appointment_id: int, db: DB) -> AppointmentOut:
    appt = _get_or_404(db, Appointment, appointment_id)
    booking.cancel(db, appt)
    return appt


@protected.get("/treatments")
def list_treatments() -> list[Treatment]:
    return list(Treatment)


@protected.get("/free-slots")
def free_slots(day: date, db: DB) -> list[datetime]:
    return booking.free_slots(db, day)


@protected.get("/customers")
def list_customers(db: DB, q: str = "") -> list[CustomerOut]:
    stmt = select(Customer).order_by(Customer.last_name, Customer.first_name)
    if q.strip():
        stmt = stmt.where(_matches(q))
    return list(db.scalars(stmt))


@protected.post("/customers", status_code=201)
def create_customer(body: CustomerIn, db: DB) -> CustomerOut:
    # numbers have equal length, so the string max is the numeric max
    highest = db.scalar(select(func.max(Customer.customer_number)))
    number = int(highest) + 1 if highest else FIRST_CUSTOMER_NUMBER
    customer = Customer(customer_number=str(number), **body.model_dump())
    db.add(customer)
    db.commit()
    return customer


@protected.get("/customers/{customer_id}")
def get_customer(customer_id: int, db: DB) -> CustomerDetail:
    customer = _get_or_404(db, Customer, customer_id)
    return CustomerDetail(
        **CustomerOut.model_validate(customer).model_dump(),
        appointments=sorted(customer.appointments, key=lambda a: a.starts_at, reverse=True),
        invoices=sorted(customer.invoices, key=lambda i: i.issued_on, reverse=True),
    )


@protected.patch("/customers/{customer_id}")
def update_customer(customer_id: int, body: CustomerIn, db: DB) -> CustomerOut:
    customer = _get_or_404(db, Customer, customer_id)
    for key, value in body.model_dump().items():
        setattr(customer, key, value)
    db.commit()
    return customer


@protected.get("/invoices")
def list_invoices(db: DB, status: InvoiceStatus | None = None) -> list[InvoiceOut]:
    stmt = select(Invoice).options(joinedload(Invoice.customer)).order_by(Invoice.issued_on.desc())
    if status:
        stmt = stmt.where(Invoice.status == status)
    return list(db.scalars(stmt))


@protected.patch("/invoices/{invoice_id}")
def set_invoice_status(invoice_id: int, body: InvoiceStatusIn, db: DB) -> InvoiceOut:
    invoice = _get_or_404(db, Invoice, invoice_id)
    invoice.status = body.status
    db.commit()
    return invoice


router.include_router(protected)

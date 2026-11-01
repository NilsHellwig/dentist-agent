from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Appointment, Base, Customer
from app.deps import CallEnded, CallSession
from app.tools import auth, call, protected, public


def next_weekday(weekday: int) -> date:
    d = date.today() + timedelta(days=1)
    while d.weekday() != weekday:
        d += timedelta(days=1)
    return d


@pytest.fixture
def ctx():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        anna = Customer(customer_number="10001", first_name="Anna", last_name="Berg", birth_date=date(1988, 4, 12))
        ben = Customer(customer_number="10002", first_name="Ben", last_name="Roth", birth_date=date(1990, 1, 1))
        db.add_all([anna, ben])
        db.flush()
        db.add(Appointment(customer_id=ben.id, starts_at=datetime.combine(next_weekday(0), datetime.min.time()).replace(hour=10), treatment="Kontrolle"))
        db.commit()
    return SimpleNamespace(deps=CallSession(db_factory=factory))


def verify(ctx, number="10001", birth=date(1988, 4, 12)):
    return auth.verify_customer(ctx, number, birth)


def test_protected_tools_require_verification(ctx):
    start = datetime.combine(next_weekday(1), datetime.min.time()).replace(hour=9)
    for result in (
        protected.get_appointments(ctx),
        protected.book_appointment(ctx, start, "Kontrolle"),
        protected.reschedule_appointment(ctx, 1, start),
        protected.cancel_appointment(ctx, 1),
        protected.get_invoices(ctx),
    ):
        assert result == protected.NOT_VERIFIED


def test_wrong_birth_date_rejected_and_message_is_generic(ctx):
    wrong_date = verify(ctx, birth=date(1988, 4, 13))
    wrong_number = verify(ctx, number="99999")
    assert wrong_date == wrong_number
    assert ctx.deps.customer_id is None


def test_malformed_number_costs_no_attempt(ctx):
    for bad in ("1001", "1000-01", "abcde", ""):
        assert "5 Ziffern" in verify(ctx, number=bad)
    assert ctx.deps.failed_attempts == 0
    assert verify(ctx).startswith("Verifiziert")


def test_number_with_spoken_separators_is_accepted(ctx):
    assert verify(ctx, number="1 0 0 0 1").startswith("Verifiziert")


def test_lockout_after_max_attempts(ctx):
    for _ in range(3):
        verify(ctx, birth=date(2000, 1, 1))
    assert ctx.deps.locked
    assert "gesperrt" in verify(ctx)  # correct data doesn't help after the lock
    assert ctx.deps.customer_id is None


def test_cannot_touch_foreign_appointment(ctx):
    verify(ctx)
    assert protected.cancel_appointment(ctx, 1) == "Termin nicht gefunden."
    assert protected.reschedule_appointment(ctx, 1, datetime.now() + timedelta(days=3)) == "Termin nicht gefunden."
    assert protected.get_appointments(ctx) == []


def test_book_and_cancel_roundtrip(ctx):
    verify(ctx)
    start = datetime.combine(next_weekday(1), datetime.min.time()).replace(hour=9)
    assert protected.book_appointment(ctx, start, "Kontrolle").startswith("Gebucht")
    assert [a.treatment for a in protected.get_appointments(ctx)] == ["Kontrolle"]
    assert "bereits vergeben" in protected.book_appointment(ctx, start, "Zahnreinigung")
    appt_id = protected.get_appointments(ctx)[0].id
    assert protected.cancel_appointment(ctx, appt_id) == "Termin storniert."
    assert protected.get_appointments(ctx) == []


def test_booking_rules(ctx):
    verify(ctx)
    day = datetime.min.time()
    assert "Vergangenheit" in protected.book_appointment(ctx, datetime.now() - timedelta(days=1), "x")
    assert "Öffnungszeiten" in protected.book_appointment(ctx, datetime.combine(next_weekday(5), day).replace(hour=10), "x")
    assert "Öffnungszeiten" in protected.book_appointment(ctx, datetime.combine(next_weekday(4), day).replace(hour=14), "x")
    assert "Raster" in protected.book_appointment(ctx, datetime.combine(next_weekday(1), day).replace(hour=9, minute=10), "x")


def test_free_slots_respect_booked_and_weekend(ctx):
    monday = next_weekday(0)
    slots = public.free_slots(ctx, monday)
    assert "10:00" not in slots and "08:00" in slots and "16:30" in slots and "17:00" not in slots
    assert public.free_slots(ctx, next_weekday(6)) == []
    assert public.free_slots(ctx, next_weekday(4))[-1] == "12:30"


def test_knowledge_blocks_path_traversal(ctx):
    assert public.read_knowledge(ctx, "../backend/app/config.py") == "Dokument nicht gefunden."
    assert public.read_knowledge(ctx, "/etc/passwd") == "Dokument nicht gefunden."
    assert "Kinder" in public.read_knowledge(ctx, "sonderregelungen/kinder.md")
    assert "sonderregelungen/kinder.md" in public.list_knowledge(ctx)
    assert any("kinder.md" in h for h in public.search_knowledge(ctx, "Kinder"))


def test_end_call_sets_flag_and_aborts_run(ctx):
    with pytest.raises(CallEnded):
        call.end_call(ctx)
    assert ctx.deps.ended

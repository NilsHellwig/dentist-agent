from datetime import date, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app import admin
from app.config import settings
from app.db.models import Appointment, Base, Customer, Invoice


def next_weekday(weekday: int) -> date:
    d = date.today() + timedelta(days=1)
    while d.weekday() != weekday:
        d += timedelta(days=1)
    return d


def at(day: date, hour: int, minute: int = 0) -> str:
    return datetime.combine(day, datetime.min.time()).replace(hour=hour, minute=minute).isoformat()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "admin_username", "admin")
    monkeypatch.setattr(settings, "admin_password", "geheim")
    monkeypatch.setattr(settings, "admin_session_secret", "test-secret")
    monkeypatch.setattr(admin, "FAILED_LOGIN_DELAY_S", 0)
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        anna = Customer(customer_number="10001", first_name="Anna", last_name="Berg", birth_date=date(1988, 4, 12))
        db.add(anna)
        db.flush()
        db.add(Appointment(customer_id=anna.id, starts_at=datetime.fromisoformat(at(next_weekday(0), 10)), treatment="Kontrolle"))
        db.add(Invoice(customer_id=anna.id, issued_on=date.today(), description="Füllung", amount_eur=48.5))
        db.commit()

    def get_db():
        with factory() as db:
            yield db

    app = FastAPI()
    app.include_router(admin.router)
    app.dependency_overrides[admin.get_db] = get_db
    return TestClient(app)


def login(client, password="geheim"):
    return client.post("/admin/api/login", json={"username": "admin", "password": password})


@pytest.fixture
def authed(client):
    assert login(client).status_code == 204
    return client


def test_disabled_without_config(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_password", "")
    assert login(client).status_code == 503
    assert client.get("/admin/api/appointments").status_code == 503


def test_requires_login(client):
    for path in ("/admin/api/appointments", "/admin/api/customers", "/admin/api/invoices", "/admin/api/customers/1"):
        assert client.get(path).status_code == 401
    assert client.post("/admin/api/appointments/1/cancel").status_code == 401


def test_wrong_password_rejected(client):
    resp = login(client, "falsch")
    assert resp.status_code == 401
    assert "admin_session" not in resp.cookies
    assert client.get("/admin/api/appointments").status_code == 401


def test_forged_or_expired_cookie_rejected(client, monkeypatch):
    client.cookies.set("admin_session", "9999999999.deadbeef", path="/admin")
    assert client.get("/admin/api/appointments").status_code == 401
    monkeypatch.setattr(admin, "SESSION_SECONDS", -1)
    client.cookies.set("admin_session", admin._session_token(), path="/admin")
    assert client.get("/admin/api/appointments").status_code == 401


def test_login_sets_strict_httponly_cookie_and_logout_clears_it(client):
    header = login(client).headers["set-cookie"].lower()
    assert "httponly" in header and "samesite=strict" in header and "path=/admin" in header
    assert client.get("/admin/api/appointments").status_code == 200
    client.post("/admin/api/logout")
    assert client.get("/admin/api/appointments").status_code == 401


def test_list_and_filter_appointments(authed):
    rows = authed.get("/admin/api/appointments").json()
    assert [(r["treatment"], r["status"], r["customer"]["last_name"]) for r in rows] == [("Kontrolle", "scheduled", "Berg")]
    assert authed.get("/admin/api/appointments", params={"q": "10001"}).json() == rows
    assert authed.get("/admin/api/appointments", params={"q": "anna berg"}).json() == rows
    assert authed.get("/admin/api/appointments", params={"q": "Winter"}).json() == []
    assert authed.get("/admin/api/appointments", params={"status": "cancelled"}).json() == []
    monday = next_weekday(0)
    assert authed.get("/admin/api/appointments", params={"from": str(monday), "to": str(monday)}).json() == rows
    assert authed.get("/admin/api/appointments", params={"from": str(monday + timedelta(days=1))}).json() == []


def test_create_reschedule_cancel_appointment(authed):
    tuesday = next_weekday(1)
    resp = authed.post("/admin/api/appointments", json={"customer_id": 1, "starts_at": at(tuesday, 9), "treatment": "Professionelle Zahnreinigung"})
    assert resp.status_code == 201
    appt_id = resp.json()["id"]
    assert at(tuesday, 9)[11:16] not in [s[11:16] for s in authed.get("/admin/api/free-slots", params={"day": str(tuesday)}).json()]

    resp = authed.patch(f"/admin/api/appointments/{appt_id}", json={"starts_at": at(tuesday, 11)})
    assert resp.status_code == 200 and resp.json()["starts_at"] == at(tuesday, 11)

    resp = authed.post(f"/admin/api/appointments/{appt_id}/cancel")
    assert resp.json()["status"] == "cancelled"
    resp = authed.patch(f"/admin/api/appointments/{appt_id}", json={"starts_at": at(tuesday, 12)})
    assert resp.status_code == 409 and "Stornierte" in resp.json()["detail"]


def test_booking_rules_apply_to_admin(authed):
    def book(starts_at):
        return authed.post("/admin/api/appointments", json={"customer_id": 1, "starts_at": starts_at, "treatment": "Beratung"})

    assert "bereits vergeben" in book(at(next_weekday(0), 10)).json()["detail"]
    assert "Vergangenheit" in book((datetime.now() - timedelta(days=1)).isoformat()).json()["detail"]
    assert "Öffnungszeiten" in book(at(next_weekday(5), 10)).json()["detail"]
    assert "Raster" in book(at(next_weekday(1), 9, 10)).json()["detail"]
    assert book(at(next_weekday(1), 9)).status_code == 201
    assert authed.post("/admin/api/appointments", json={"customer_id": 99, "starts_at": at(next_weekday(1), 10), "treatment": "Beratung"}).status_code == 404


def test_create_and_update_customer(authed):
    resp = authed.post("/admin/api/customers", json={"first_name": "Lukas", "last_name": "Winter", "birth_date": "2016-09-03"})
    assert resp.status_code == 201 and resp.json()["customer_number"] == "10002"
    customer_id = resp.json()["id"]

    resp = authed.patch(f"/admin/api/customers/{customer_id}", json={"first_name": "Luka", "last_name": "Winter", "birth_date": "2016-09-04"})
    assert resp.json()["first_name"] == "Luka" and resp.json()["birth_date"] == "2016-09-04"
    assert authed.post("/admin/api/customers", json={"first_name": "", "last_name": "X", "birth_date": "2000-01-01"}).status_code == 422
    assert [c["last_name"] for c in authed.get("/admin/api/customers", params={"q": "win"}).json()] == ["Winter"]


def test_customer_detail_includes_appointments_and_invoices(authed):
    detail = authed.get("/admin/api/customers/1").json()
    assert detail["customer_number"] == "10001"
    assert [a["treatment"] for a in detail["appointments"]] == ["Kontrolle"]
    assert [i["description"] for i in detail["invoices"]] == ["Füllung"]
    assert authed.get("/admin/api/customers/99").status_code == 404


def test_toggle_invoice_status(authed):
    assert authed.patch("/admin/api/invoices/1", json={"status": "paid"}).json()["status"] == "paid"
    assert authed.get("/admin/api/invoices", params={"status": "open"}).json() == []
    assert authed.patch("/admin/api/invoices/1", json={"status": "bezahlt"}).status_code == 422


def test_only_listed_treatments(authed):
    assert authed.get("/admin/api/treatments").json()[:2] == ["Kontrolluntersuchung", "Professionelle Zahnreinigung"]
    resp = authed.post("/admin/api/appointments", json={"customer_id": 1, "starts_at": at(next_weekday(1), 9), "treatment": "Zahnreinigung"})
    assert resp.status_code == 422

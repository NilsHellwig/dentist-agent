from datetime import date, datetime, timedelta

from sqlalchemy import select

from app.db.models import Appointment, Base, Customer, Invoice, SessionLocal, engine


def init_db() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalar(select(Customer.id).limit(1)) is not None:
            return
        # Termine immer auf Werktage innerhalb der Öffnungszeiten legen
        today = datetime.now().replace(hour=9, minute=30, second=0, microsecond=0)
        next_monday = today + timedelta(days=7 - today.weekday())
        anna = Customer(customer_number="10001", first_name="Anna", last_name="Berg", birth_date=date(1988, 4, 12))
        lukas = Customer(customer_number="10002", first_name="Lukas", last_name="Winter", birth_date=date(2016, 9, 3))
        db.add_all([
            anna,
            lukas,
            Appointment(customer=anna, starts_at=next_monday, treatment="Professionelle Zahnreinigung"),
            Appointment(customer=anna, starts_at=next_monday + timedelta(weeks=8), treatment="Kontrolluntersuchung"),
            Appointment(customer=lukas, starts_at=next_monday + timedelta(days=2, hours=5, minutes=30), treatment="Kinder-Kontrolle"),
            Invoice(customer=anna, issued_on=date.today() - timedelta(days=20), description="Füllung 36", amount_eur=48.50, status="offen"),
            Invoice(customer=anna, issued_on=date.today() - timedelta(days=200), description="Zahnreinigung", amount_eur=89.00, status="bezahlt"),
        ])
        db.commit()

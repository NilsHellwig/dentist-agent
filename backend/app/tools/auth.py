import re
from datetime import date

from pydantic_ai import RunContext
from sqlalchemy import select

from app.config import settings
from app.db.models import Customer
from app.deps import CallSession


def verify_customer(ctx: RunContext[CallSession], customer_number: str, birth_date: date) -> str:
    """Schaltet die geschützten Funktionen frei, wenn Kundennummer und Geburtsdatum zusammenpassen.

    Args:
        customer_number: Kundennummer, nur Ziffern (z.B. '10001').
        birth_date: Geburtsdatum des Kunden als YYYY-MM-DD.
    """
    session = ctx.deps
    if session.locked:
        return "Verifizierung gesperrt: zu viele Fehlversuche. Bitte an die Praxis wenden."
    # Spracherkennung liefert Ziffernfolgen oft als "1 0 0 0 1"; Trennzeichen ignorieren
    customer_number = re.sub(r"[\s.\-,]", "", customer_number)
    # Verschluckte Ziffern sollen keinen Versuch kosten
    if not re.fullmatch(r"\d{5}", customer_number):
        return "Ungültige Kundennummer: sie hat genau 5 Ziffern. Bitte den Kunden, sie langsam Ziffer für Ziffer zu nennen."
    with session.db_factory() as db:
        customer = db.scalar(select(Customer).where(Customer.customer_number == customer_number))
    if customer is None or customer.birth_date != birth_date:
        session.failed_attempts += 1
        if session.failed_attempts >= settings.max_auth_attempts:
            session.locked = True
            return "Verifizierung gesperrt: zu viele Fehlversuche. Bitte an die Praxis wenden."
        # gleiche Meldung für falsche Nummer und falsches Datum, damit keine Nummern erraten werden
        return "Kundennummer und Geburtsdatum passen nicht zusammen."
    session.customer_id = customer.id
    return f"Verifiziert: {customer.first_name} {customer.last_name}."

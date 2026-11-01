import re
from datetime import date

from pydantic_ai import RunContext
from sqlalchemy import select

from app.config import settings
from app.db.models import Customer
from app.deps import CallSession


def verify_customer(ctx: RunContext[CallSession], customer_number: str, birth_date: date) -> str:
    """Unlocks the protected functions if customer number and birth date match.

    Args:
        customer_number: Customer number, digits only (e.g. '10001').
        birth_date: The customer's birth date as YYYY-MM-DD.
    """
    session = ctx.deps
    if session.locked:
        return "Verifizierung gesperrt: zu viele Fehlversuche. Bitte an die Praxis wenden."
    # Speech recognition often returns digit sequences as "1 0 0 0 1"; ignore separators
    customer_number = re.sub(r"[\s.\-,]", "", customer_number)
    # Swallowed digits should not cost an attempt
    if not re.fullmatch(r"\d{5}", customer_number):
        return "Ungültige Kundennummer: sie hat genau 5 Ziffern. Bitte den Kunden, sie langsam Ziffer für Ziffer zu nennen."
    with session.db_factory() as db:
        customer = db.scalar(select(Customer).where(Customer.customer_number == customer_number))
    if customer is None or customer.birth_date != birth_date:
        session.failed_attempts += 1
        if session.failed_attempts >= settings.max_auth_attempts:
            session.locked = True
            return "Verifizierung gesperrt: zu viele Fehlversuche. Bitte an die Praxis wenden."
        # same message for wrong number and wrong date so numbers cannot be guessed
        return "Kundennummer und Geburtsdatum passen nicht zusammen."
    session.customer_id = customer.id
    return f"Verifiziert: {customer.first_name} {customer.last_name}."

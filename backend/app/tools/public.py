from datetime import date, datetime, time, timedelta

from pydantic_ai import RunContext
from sqlalchemy import select

from app.config import settings
from app.db.models import Appointment
from app.deps import CallSession

WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]

# Öffnungszeiten je Wochentag (0 = Montag); muss zu knowledge/allgemein/oeffnungszeiten.md passen
OPENING_HOURS = {0: (8, 17), 1: (8, 17), 2: (8, 17), 3: (8, 17), 4: (8, 13)}
SLOT_MINUTES = 30


def _knowledge_root():
    return settings.knowledge_dir.resolve()


def list_knowledge(ctx: RunContext[CallSession]) -> list[str]:
    """Listet alle Wissensdokumente der Praxis (relative Pfade), z.B. 'sonderregelungen/kinder.md'."""
    root = _knowledge_root()
    return sorted(str(p.relative_to(root)) for p in root.rglob("*.md"))


def read_knowledge(ctx: RunContext[CallSession], path: str) -> str:
    """Liest ein Wissensdokument. `path` stammt aus list_knowledge oder search_knowledge."""
    root = _knowledge_root()
    target = (root / path).resolve()
    if not target.is_relative_to(root) or target.suffix != ".md" or not target.is_file():
        return "Dokument nicht gefunden."
    return target.read_text(encoding="utf-8")


def search_knowledge(ctx: RunContext[CallSession], query: str) -> list[str]:
    """Sucht Stichworte (z.B. 'Kinder', 'Notfall') im Wissen; liefert 'pfad: Zeile'-Treffer."""
    words = [w.lower() for w in query.split() if len(w) > 2]
    hits: list[str] = []
    root = _knowledge_root()
    for p in sorted(root.rglob("*.md")):
        for line in p.read_text(encoding="utf-8").splitlines():
            if any(w in line.lower() for w in words) or any(w in p.stem.lower() for w in words):
                hits.append(f"{p.relative_to(root)}: {line.strip()}")
    return hits[:20] or ["Keine Treffer."]


def free_slots(ctx: RunContext[CallSession], day: date) -> list[str]:
    """Freie Terminzeiten (HH:MM) an einem Tag, im 30-Minuten-Raster innerhalb der Öffnungszeiten."""
    hours = OPENING_HOURS.get(day.weekday())
    if hours is None:
        return []
    start, end = datetime.combine(day, time(hours[0])), datetime.combine(day, time(hours[1]))
    with ctx.deps.db_factory() as db:
        taken = set(
            db.scalars(
                select(Appointment.starts_at).where(
                    Appointment.status == "geplant", Appointment.starts_at >= start, Appointment.starts_at < end
                )
            )
        )
    now = datetime.now()
    slots, t = [], start
    while t < end:
        if t > now and t not in taken:
            slots.append(t.strftime("%H:%M"))
        t += timedelta(minutes=SLOT_MINUTES)
    return slots

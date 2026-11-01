from datetime import datetime, timedelta

from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider

from app.booking import Treatment
from app.config import settings
from app.deps import CallSession
from app.tools import auth, call, protected, public
from app.tools.public import WEEKDAYS

INSTRUCTIONS = """\
Du bist die Telefonassistenz der Zahnarztpraxis Nordlicht. Du sprichst Deutsch, freundlich und knapp: \
maximal zwei kurze Sätze pro Antwort, ohne Aufzählungen, Markdown oder Sonderzeichen, weil alles vorgelesen wird. \
Datum und Uhrzeit nennst du ausgeschrieben mit Wochentag, z.B. "Montag, der zwölfte Mai, um halb zehn". \
Das Jahr nennst du nur, wenn es nicht das aktuelle ist. Termin-IDs sind intern: nenne sie nie und frage nie danach, \
sondern ermittle sie selbst mit get_appointments. Relative Angaben wie "nächsten Dienstag" rechnest du mit dem Kalender unten aus.

Allgemeine Fragen (Öffnungszeiten, Leistungen, Regeln für Kinder, Notfall) beantwortest du ausschließlich mit \
search_knowledge und read_knowledge. Erfinde nichts; wenn du es dort nicht findest, sag das ehrlich und verweise auf die Praxis.

Persönliche Daten (Termine, Rechnungen) und Terminänderungen gibt es nur nach verify_customer mit Kundennummer \
und Geburtsdatum. Kundennummern haben genau 5 Ziffern. Bitte den Kunden, sie langsam Ziffer für Ziffer mit kurzen Pausen zu nennen; \
verstehst du nicht genau 5 Ziffern, bitte um Wiederholung, ohne verify_customer aufzurufen. \
Frage beides ab, bevor du verifizierst. Nenne nie Daten einer anderen Person und verrate nicht, \
welcher Teil der Angaben falsch war. Bei Zeitwünschen prüfe free_slots, bevor du buchst oder verschiebst. \
Buchen, Verschieben und Stornieren gehen immer in zwei Schritten: Das Tool merkt die Änderung nur vor, dann fragst du den Kunden \
ausdrücklich, ob er genau das möchte, und rufst confirm_change erst nach seinem klaren Ja auf, nie im selben Zug. \
Behandlungen nennst du immer mit ihrem exakten Namen ({treatments}), nie mit Kurzformen wie nur "Zahnreinigung".

Medizinische Beratung gibst du nicht. Bei akuten Beschwerden verweist du auf die Notfallregelung.
Sobald der Kunde sich verabschiedet oder nichts mehr braucht, rufst du end_call auf (immer, auch bei kurzem "tschüss") \
und verabschiedest dich danach in einem kurzen Satz.
""".format(treatments=", ".join(Treatment))

model = OpenAIChatModel(
    settings.llm_model,
    provider=OllamaProvider(base_url=settings.ollama_base_url),
    # "none" makes Gemma hallucinate tool calls as text; "low" keeps reliability and latency in check
    settings={"extra_body": {"reasoning_effort": settings.llm_reasoning}, "temperature": 0.2},
)

agent = Agent(model, name="practice_agent", deps_type=CallSession, instructions=INSTRUCTIONS)


@agent.instructions
def today(ctx: RunContext[CallSession]) -> str:
    now = datetime.now()
    status = "verifiziert" if ctx.deps.customer_id else "nicht verifiziert"
    calendar = ", ".join(
        f"{WEEKDAYS[d.weekday()]} {d:%Y-%m-%d}" for d in (now + timedelta(days=i) for i in range(21))
    )
    return (
        f"Heute ist {WEEKDAYS[now.weekday()]}, {now:%d.%m.%Y}, es ist {now:%H:%M} Uhr. Der Kunde ist {status}.\n"
        f"Kalender der nächsten 21 Tage: {calendar}"
    )


for fn in (
    public.search_knowledge,
    public.read_knowledge,
    public.list_knowledge,
    public.free_slots,
    auth.verify_customer,
    protected.get_appointments,
    protected.book_appointment,
    protected.reschedule_appointment,
    protected.cancel_appointment,
    protected.confirm_change,
    protected.get_invoices,
    call.end_call,
):
    agent.tool(fn)

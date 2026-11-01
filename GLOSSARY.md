# Glossary

| Term | German (UI / agent) | Meaning |
| --- | --- | --- |
| Customer | Kunde | Patient of the practice, identified by a 5-digit customer number (Kundennummer) and birth date. |
| Appointment | Termin | A booked 30-minute slot for one customer and one treatment. |
| `scheduled` | geplant | Appointment status: active and occupies its slot. |
| `cancelled` | storniert | Appointment status: kept for history, frees its slot. Appointments are never deleted. |
| Invoice | Rechnung | Amount billed to a customer. |
| `open` | offen | Invoice status: not yet paid. |
| `paid` | bezahlt | Invoice status: settled. |
| Slot | Terminzeit | A 30-minute start time within opening hours (`app/booking.py`). |
| Verification | Verifizierung | Unlocking personal data in a call via customer number + birth date. |
| Admin | Admin | Practice staff using the dashboard at `/admin`; one shared login from `.env`. |

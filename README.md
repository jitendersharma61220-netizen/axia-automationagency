# AXIA Automation Agency

Automations that take repetitive work off small businesses. Each automation is
a Python package under `axia/` that we can set up for a client in an afternoon.

## Automation 1: Lead follow-up

**Who it's for:** local service businesses that live on enquiries, such as
dental and skin clinics, gyms, coaching institutes, real estate agents and
salons.

**The problem:** most of these businesses reply to a new enquiry hours or days
late, and almost never follow up twice. Leads that get a fast reply and a
couple of polite reminders convert far more often.

**What it does:**

1. A lead arrives from a website form, Zapier/Make, a CSV, or the command line.
2. The lead gets an instant "thanks, we'll be in touch" email, and the owner
   gets a "new lead" alert.
3. Follow-ups go out on day 2 and day 5 (configurable) until the lead replies.
4. Duplicate leads are ignored, and a lead marked as replied gets nothing more.

Only standard-library Python 3.11 is needed. There is nothing to install.

### Try it

```bash
cp .env.example .env            # edit the business name; keep AXIA_DRY_RUN=1 to test
set -a; . ./.env; set +a

python -m axia.lead_followup add "Asha Rao" asha@example.com --message "Need a cleaning"
python -m axia.lead_followup list
python -m axia.lead_followup run           # send any due follow-ups
python -m axia.lead_followup replied asha@example.com
python -m axia.lead_followup import leads.csv   # columns: name,email,phone,message
```

### Receive leads from a website

```bash
python -m axia.lead_followup serve --port 8000
curl -X POST localhost:8000/lead -H 'Content-Type: application/json' \
  -d '{"name": "Asha Rao", "email": "asha@example.com", "phone": "98xxxxxx"}'
```

The endpoint accepts JSON or normal HTML form posts with the fields `name`,
`email`, `phone`, `message` and `source`.

### Going live for a client

1. Set the SMTP settings in `.env` (for Gmail, use an app password) and set
   `AXIA_DRY_RUN=0`.
2. Edit the wording in `axia/lead_followup/templates.py`.
3. Run `serve` on a small server, and point the client's form at `/lead`.
4. Schedule `python -m axia.lead_followup run` every hour with cron.

## Development

```bash
python -m unittest discover -s tests -v
```

## Next ideas

- WhatsApp follow-ups (most Indian customers answer WhatsApp before email).
- Read replies from the inbox so leads are marked as replied automatically.
- Google Sheets sync so owners can see their leads without a terminal.
- Appointment and payment reminders as the next automations.

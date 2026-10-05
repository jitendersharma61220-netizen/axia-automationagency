# AXIA Automation Agency

AI agents that take over whole departments' repetitive work for Indian
businesses. Each agent runs a multi-step workflow: Claude does the thinking in
each step (research, scoring, reading documents, writing, classifying) and
returns structured data, while the code decides what actually happens. Anything
that matters waits in an approval queue for a person until the client trusts
the agent enough to switch on auto mode.

| Agent | Department | What it takes over | Status |
| --- | --- | --- | --- |
| `axia.sales` | Sales | Lead research, scoring, WhatsApp/email outreach, reply handling, meeting booking, follow-ups | Built |
| `axia.marketing` | Marketing | Market research, campaign plans, content for every channel, performance analysis | Built |
| `axia.ops` | Operations / accounts | Bill reading, PO matching, GST checks, approvals, payables | Planned |
| `axia.medical` | Clinics | Doctor-approved visit notes, lab report explainers, patient reminders | Planned |
| `axia.hr` | HR | Resume ranking, WhatsApp screening, interview booking | Planned |
| `axia.lead_followup` | Sales (simple) | Instant reply and timed follow-ups for every enquiry | Built |

Shared building blocks live in `axia/core/`: the Claude client (`ai.py`),
email and WhatsApp (`channels.py`), the approval queue (`approvals.py`) and a
small webhook server (`server.py`).

### Setup

```bash
pip install -r requirements.txt     # the Claude SDK; lead_followup needs nothing
cp .env.example .env                # add ANTHROPIC_API_KEY; keep AXIA_DRY_RUN=1 to test
set -a; . ./.env; set +a
```

With `AXIA_DRY_RUN=1` no email or WhatsApp leaves the machine; messages are
printed instead.

## Sales agent (AI SDR)

**Who it's for:** businesses whose sales team spends the day on lead lists:
real estate, coaching institutes, B2B suppliers, agencies, clinics with
high-ticket treatments.

**What it does, for every lead:**

1. **Research.** For company leads, Claude searches the web for what the
   company does, its size and recent news.
2. **Qualify.** Scores the lead 0-100 against the client's ideal customer and
   picks the angle to lead with. Poor fits are disqualified or parked for later.
3. **Reach out.** Writes a personal first message on WhatsApp or email,
   offering real free meeting slots from the calendar.
4. **Handle replies.** Reads each reply and works out the intent:
   - *interested + picks a time*: books the slot, confirms, alerts the sales rep;
   - *question or objection*: drafts an answer (price negotiation and anything
     off-playbook always goes to a human);
   - *not now*: parks the lead and comes back on the date they asked for;
   - *not interested / stop*: closes it and never messages again.
5. **Follow up.** Two follow-ups on silence (day 2 and day 5 by default), each
   adding something new.
6. **Report.** Pipeline by stage, booked meetings and hot leads.

Everything about the client lives in one playbook file
(`examples/sales_playbook.json`): offer, ideal customer, disqualifiers,
pricing rules, meeting hours, the sales rep's contact, tone and `auto_send`.

### Try it

```bash
python -m axia.sales add "Amit Shah" --phone 9820012345 --message "Need 3 BHK in Baner, budget 1.2 Cr"
python -m axia.sales add "Ravi" --email ravi@acme.example --company "Acme Infotech" --website acme.example
python -m axia.sales pending                 # read the drafted messages
python -m axia.sales approve 1               # or: approve 1 --body "edited text"; reject 1
python -m axia.sales reply 9820012345 "Saturday 10 am chalega"
python -m axia.sales report
python -m axia.sales run                     # new leads + due follow-ups; schedule hourly with cron
```

### Going live

1. Fill the playbook for the client and set `AXIA_DRY_RUN=0` with SMTP and/or
   WhatsApp Cloud API details in `.env`.
2. `python -m axia.sales serve --port 8010` on a small server. Point website
   forms at `POST /lead`, the WhatsApp webhook at `/whatsapp`, and forward email
   replies to `POST /reply` (`{"from": ..., "text": ...}`).
3. Run `python -m axia.sales run` hourly from cron.
4. Keep `auto_send: false` for the first weeks; the client approves messages
   with `pending` / `approve`. Switch it on once the drafts need no edits.

Note: WhatsApp only allows free-form messages to people who wrote in the last
24 hours. For cold outreach, register an approved template in Meta, or set
`prefer_whatsapp` to false to use email.

## Marketing campaign engine

**Who it's for:** gyms, clinics, coaching institutes, restaurants and D2C
brands that run their own Instagram, WhatsApp and Google Ads without a
marketing team.

**What it does for a goal like "50 new members for Diwali":**

1. **Research.** Claude searches the web for what nearby competitors are
   offering right now and the festivals and local events in the window.
2. **Plan.** Segments, offer, key message, budget split per channel, KPI
   targets and a dated content calendar built around the research.
3. **Create.** Instagram captions with hashtags and a visual brief, Facebook
   posts, WhatsApp broadcasts and Google responsive search ads. Code checks
   hard rules (Google's 30/90-character limits, banned phrases like
   "guaranteed weight loss") and sends a piece back for one rewrite if needed.
4. **Approve and export.** The owner approves or edits each piece; approved
   posts export as a calendar CSV for Meta Business Suite or any scheduler.
5. **Analyse.** From the ad platforms' numbers, code computes CTR, cost per
   lead and ROAS per channel; Claude explains what is working in plain words
   and proposes a new budget split (at most 20 points shift per channel per
   review).

The brand is configured in `examples/marketing_brand.json`.

```bash
python -m axia.marketing plan "50 new members for Diwali" --start 2026-10-15 --weeks 4
python -m axia.marketing show 1
python -m axia.marketing create 1
python -m axia.marketing pending
python -m axia.marketing approve 3 --edit '{"caption": "New caption"}'
python -m axia.marketing export 1 --out calendar.csv
python -m axia.marketing analyze 1 examples/marketing_metrics.csv
```

## Lead follow-up (simple)

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
python -m unittest discover -s tests -t . -v
```

## Next ideas

- A web dashboard for the approval queue, so clients approve from their phone.
- Google Sheets / CRM sync (Zoho, HubSpot) for the sales pipeline.
- Read the email inbox directly so replies reach the agents without forwarding.

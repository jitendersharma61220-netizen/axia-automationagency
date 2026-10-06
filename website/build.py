"""Generate the AXIA website pages.

All pages share one layout (header, footer, call buttons). Edit the content
below, then run:

    python3 build.py

and commit the regenerated .html files. Brand rule: the word "AI" must not
appear anywhere on the public site.
"""

import html
import json
import re
from pathlib import Path

OUT = Path(__file__).parent

PHONE = "+918930522312"
PHONE_DISPLAY = "+91 89305 22312"
WHATSAPP = "918930522312"

# Where the proposal engine (engine/ in this repo) is hosted, for example
# "https://axia-engine.onrender.com". Leave empty to use the same origin; if
# no engine answers there, the plan form falls back to sending the details on
# WhatsApp.
ENGINE_URL = ""

# ---------------------------------------------------------------- content

DEPTS = [
    {
        "slug": "sales",
        "dept": "Sales",
        "name": "Sales Outreach Agent",
        "c1": "#ff8a3d",
        "c2": "#ffcf5c",
        "icon": '<path d="M3 17l6-6 4 4 8-8"/><path d="M14 7h7v7"/>',
        "tagline": "A sales desk that researches, writes and follows up on every lead, every day.",
        "summary": "Researches every lead, scores fit, writes personal outreach, sorts replies and books meetings straight into your calendar and CRM.",
        "problem": "Your sales team spends its mornings finding contact details, copying data into sheets and writing the same emails again and again. Good leads go cold because nobody followed up on day three.",
        "flow": {
            "inputs": ["Lead lists", "Website forms", "Lead marketplaces"],
            "stages": ["Research", "Score fit", "Write outreach", "You approve", "Send & book"],
            "approval": 3,
            "outputs": ["CRM", "Calendar", "Rep alert"],
        },
        "steps": [
            ("Research", "Reads the company website, recent news and the contact's role so every message starts from real context."),
            ("Score fit", "Scores each lead against your ideal customer and puts the best ones first."),
            ("Write outreach", "Drafts a personal first message for WhatsApp or email, in the lead's own language, with real free meeting slots."),
            ("You approve", "Your rep reviews the batch in one place and approves, edits or skips each message."),
            ("Send and book", "Sends, follows up on silence, sorts every reply into interested, later or not now, and books meetings."),
        ],
        "tools": ["WhatsApp Business", "Gmail / Outlook", "Zoho CRM", "HubSpot", "Google Calendar", "Google Sheets"],
        "case": {
            "meta": "B2B software company · Pune",
            "title": "From 40 cold emails a day to 300 researched ones",
            "body": "The sales team spent mornings finding contacts and writing emails. The agent now researches each company, writes a personal first message and sorts every reply into interested, later or not now.",
            "metrics": [("7x", "outreach volume"), ("3 hrs", "saved per rep daily"), ("2x", "meetings booked")],
        },
    },
    {
        "slug": "marketing",
        "dept": "Marketing",
        "name": "Campaign Engine",
        "c1": "#7b5cff",
        "c2": "#c084fc",
        "icon": '<path d="M4 10v4h3l5 4V6L7 10H4z"/><path d="M16 9a4 4 0 010 6"/><path d="M18.5 6.5a8 8 0 010 11"/>',
        "tagline": "A full marketing team's monthly plan, content and reporting, running on one engine.",
        "summary": "Plans the monthly campaign, writes content for Instagram, WhatsApp, email and ads in your brand voice, then reads results and improves the next round.",
        "problem": "Every festival and sale needs fresh posts, reels scripts, WhatsApp broadcasts and ad copy. Small teams either post late, post generic content, or never look at what actually worked.",
        "flow": {
            "inputs": ["Brand guide", "Past results", "Festive calendar"],
            "stages": ["Plan", "Create", "Brand check", "You approve", "Publish & learn"],
            "approval": 3,
            "outputs": ["Instagram", "WhatsApp", "Google Ads"],
        },
        "steps": [
            ("Plan", "Studies competitors, the season and your past results, then builds a dated calendar with a budget split."),
            ("Create", "Writes posts, reels scripts, WhatsApp broadcasts, emails and ad copy for every date on the calendar."),
            ("Brand check", "Checks tone, banned words, platform length limits and offer details before anything reaches you."),
            ("You approve", "You approve the whole month in one sitting, with quick edits where you want them."),
            ("Publish and learn", "Exports approved content, reads click and lead numbers, and moves budget toward what works."),
        ],
        "tools": ["Instagram", "Facebook", "WhatsApp Business", "Google Ads", "Meta Ads", "Mailchimp"],
        "case": {
            "meta": "D2C skincare brand · Jaipur",
            "title": "A full month of festive content, planned in one afternoon",
            "body": "For the Diwali season the engine built the campaign calendar, wrote posts, reels scripts, WhatsApp broadcasts and ad copy, then flagged which creatives to scale after week one.",
            "metrics": [("120+", "pieces per month"), ("5", "channels covered"), ("1", "approval round")],
        },
    },
    {
        "slug": "accounts",
        "dept": "Operations",
        "name": "Accounts Back-Office",
        "c1": "#2ee6d6",
        "c2": "#4f8bff",
        "icon": '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 7h8M8 11h8M8 15h5"/>',
        "tagline": "Supplier bills read, matched, tax-checked and ready to pay, without manual entry.",
        "summary": "Reads supplier bills, matches them to purchase orders, checks tax details, routes approvals and prepares your payables list.",
        "problem": "Bills arrive as photos on WhatsApp, PDFs on email and paper at the gate. Someone types each one into the accounting software, checks it against the PO by hand and still misses tax mismatches and due dates.",
        "flow": {
            "inputs": ["Bills on WhatsApp", "Email PDFs", "Purchase orders"],
            "stages": ["Read bill", "Match PO", "Tax check", "You approve", "Schedule pay"],
            "approval": 3,
            "outputs": ["Accounting", "Payables list", "Vendor query"],
        },
        "steps": [
            ("Read bill", "Reads photos, scans and PDFs and pulls out vendor, tax ID, items, rates, tax and totals."),
            ("Match PO", "Three-way matches each bill against the purchase order and goods received."),
            ("Tax check", "Validates the tax ID, recomputes the arithmetic and checks the tax split, whether GST, VAT or sales tax."),
            ("You approve", "Clean small bills can pass automatically; anything unusual waits for your approver with a clear note."),
            ("Schedule pay", "Updates the payables list, drafts vendor queries for mismatches and exports the purchase register."),
        ],
        "tools": ["Tally", "QuickBooks", "Xero", "Zoho Books", "WhatsApp Business", "Gmail", "Excel"],
        "case": {
            "meta": "FMCG distributor · Ludhiana",
            "title": "800 supplier bills a month, matched and GST-checked",
            "body": "Bills arrived as photos and PDFs on WhatsApp and email. The system reads them, matches each to its purchase order, flags GST mismatches and sends the payables list for one-click approval.",
            "metrics": [("90%", "bills auto-matched"), ("0", "missed due dates"), ("4 days", "faster month close")],
        },
    },
    {
        "slug": "clinic",
        "dept": "Healthcare",
        "name": "Clinic Assistant",
        "c1": "#ff5c8a",
        "c2": "#ff9a8b",
        "icon": '<path d="M12 21s-7-4.5-7-10a4 4 0 017-2.6A4 4 0 0119 11c0 5.5-7 10-7 10z"/><path d="M12 9v5M9.5 11.5h5"/>',
        "tagline": "Doctors back with patients, while notes, reports and reminders take care of themselves.",
        "summary": "Drafts consultation notes for the doctor to approve, explains lab reports to patients in simple language and sends follow-up reminders.",
        "problem": "Doctors spend hours after OPD writing notes and prescriptions. Patients call the clinic to ask what their lab report means, and follow-up visits and repeat tests get missed.",
        "flow": {
            "inputs": ["Consultation", "Lab reports", "Appointments"],
            "stages": ["Draft notes", "Safety check", "Doctor approves", "Explain", "Remind"],
            "approval": 2,
            "outputs": ["Patient record", "Patient WhatsApp", "Follow-ups"],
        },
        "steps": [
            ("Draft notes", "Turns the consultation into structured notes and a draft prescription."),
            ("Safety check", "Flags allergies, duplicate medicines and missing doses before the doctor sees the draft."),
            ("Doctor approves", "Nothing reaches a patient until the doctor reviews and signs it."),
            ("Explain", "Explains lab reports in simple language the patient understands, with critical values sent to the doctor first."),
            ("Remind", "Sends dose reminders, follow-up visit reminders and repeat test alerts on WhatsApp."),
        ],
        "tools": ["Clinic software", "WhatsApp Business", "Google Calendar", "Lab report PDFs", "Google Sheets"],
        "case": {
            "meta": "Multi-speciality clinic · Indore",
            "title": "Doctors back to patients, not paperwork",
            "body": "Consultation notes are drafted for the doctor to review and sign. Patients get their lab reports explained in their own language, plus reminders for follow-ups and repeat tests.",
            "metrics": [("2 hrs", "saved per doctor daily"), ("100%", "notes doctor-approved"), ("35%", "fewer missed follow-ups")],
        },
    },
    {
        "slug": "hiring",
        "dept": "HR",
        "name": "Hiring Agent",
        "c1": "#5cff9d",
        "c2": "#2ee6d6",
        "icon": '<circle cx="9" cy="8" r="3.5"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6"/><path d="M16 11l2 2 4-4"/>',
        "tagline": "From a thousand applications to a booked interview panel, in days instead of weeks.",
        "summary": "Ranks resumes against the role, runs a first screening on WhatsApp and books interviews with your panel, so recruiters only meet strong candidates.",
        "problem": "A single job post brings hundreds of resumes. Recruiters skim them, call candidates one by one to check salary and notice period, and juggle panel calendars over email.",
        "flow": {
            "inputs": ["Job portals", "Email resumes", "Referrals"],
            "stages": ["Read resume", "Rank", "WhatsApp screen", "HR approves", "Book interview"],
            "approval": 3,
            "outputs": ["Panel calendar", "Candidate updates", "Hiring sheet"],
        },
        "steps": [
            ("Read resume", "Reads every resume format and pulls out skills, experience and evidence for each requirement."),
            ("Rank", "Scores candidates against the role with reasons, keeping personal details out of the scoring."),
            ("WhatsApp screen", "Asks shortlisted candidates about salary, notice period and location on WhatsApp."),
            ("HR approves", "Your HR team approves the shortlist; regret messages wait for HR too."),
            ("Book interview", "Books slots with the panel and keeps candidates updated at every step."),
        ],
        "tools": ["Naukri", "LinkedIn", "WhatsApp Business", "Gmail", "Google Calendar", "Google Sheets"],
        "case": {
            "meta": "Staffing firm · Gurugram",
            "title": "1,000 applications screened in a weekend",
            "body": "For a bulk hiring drive, the agent ranked every resume, ran a short WhatsApp screening with each shortlisted candidate and filled the interview panel's calendar for the week.",
            "metrics": [("10x", "faster shortlisting"), ("48 hrs", "apply to interview"), ("60%", "less recruiter time")],
        },
    },
]

HOME_FLOW = {
    "inputs": ["WhatsApp", "Email", "Forms & sheets"],
    "stages": ["Capture", "Understand", "Check rules", "You approve", "Act"],
    "approval": 3,
    "outputs": ["CRM", "Accounts", "Calendar"],
    "color": "#7b5cff",
    "accent": "#2ee6d6",
}

NAV = [("index", "Home", "index.html"), ("services", "Services", "services.html"), ("portfolio", "Portfolio", "portfolio.html"), ("about", "About", "about.html"), ("plan", "Free plan", "plan.html"), ("contact", "Contact", "contact.html")]

# ---------------------------------------------------------------- icons

PHONE_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4h4l2 5-2.5 1.5a11 11 0 005 5L15 13l5 2v4a2 2 0 01-2 2A16 16 0 013 6a2 2 0 012-2"/></svg>'
WA_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 21l1.6-4.8A8.5 8.5 0 1112 20.5a8.4 8.4 0 01-4.2-1.1L3 21z"/><path d="M9 8.5c0 3.5 3 6.5 6.5 6.5l1-1.6-2-1-1 .8a5 5 0 01-2.7-2.7l.8-1-1-2L9 8.5z"/></svg>'


def esc(s):
    return html.escape(s, quote=True)


def flow_attr(flow, c1=None, c2=None):
    f = dict(flow)
    if c1:
        f["color"] = c1
        f["accent"] = c2
    return esc(json.dumps(f))


# ---------------------------------------------------------------- layout

def layout(key, title, desc, body, engine=True):
    links = []
    for k, label, href in NAV:
        cls = ' class="active"' if k == key or (k == "services" and key in [d["slug"] for d in DEPTS]) else ""
        if k == "services":
            sub = "".join(f'<a href="{d["slug"]}.html"><span class="dot" style="--c:{d["c1"]}"></span>{d["name"]}</a>' for d in DEPTS)
            links.append(f'<div class="has-sub"><a href="{href}"{cls}>{label}</a><div class="sub">{sub}</div></div>')
        else:
            links.append(f'<a href="{href}"{cls}>{label}</a>')
    nav_links = "\n      ".join(links)
    scripts = '<script type="module" src="engine.js"></script>\n  ' if engine else ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(desc)}" />
  <meta name="theme-color" content="#070a1a" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="styles.css" />
</head>
<body>
  <header class="nav">
    <a class="logo" href="index.html" aria-label="AXIA home"><span class="logo-mark" aria-hidden="true"></span>AXIA</a>
    <nav class="nav-links" aria-label="Main">
      {nav_links}
      <a href="tel:{PHONE}" class="btn btn-small btn-call">{PHONE_ICON}<span>Call now</span></a>
    </nav>
    <div class="nav-right">
      <a href="tel:{PHONE}" class="call-chip" aria-label="Call AXIA">{PHONE_ICON}</a>
      <button class="nav-toggle" aria-label="Open menu" aria-expanded="false"><span></span><span></span></button>
    </div>
  </header>

  <main>
{body}
  </main>

  <section class="cta-band">
    <div class="cta-inner reveal">
      <div>
        <h2>Ready to put a department on autopilot?</h2>
        <p>Call or WhatsApp us for a free process audit. We will show you exactly what can run on its own.</p>
      </div>
      <div class="cta-actions">
        <a href="tel:{PHONE}" class="btn">{PHONE_ICON}Call {PHONE_DISPLAY}</a>
        <a href="https://wa.me/{WHATSAPP}" class="btn btn-ghost" target="_blank" rel="noopener">{WA_ICON}WhatsApp us</a>
      </div>
    </div>
  </section>

  <footer class="footer">
    <div class="footer-grid">
      <div>
        <a class="logo" href="index.html"><span class="logo-mark" aria-hidden="true"></span>AXIA</a>
        <p>Department automation for growing businesses, anywhere in the world.</p>
      </div>
      <div>
        <h4>Services</h4>
        {"".join(f'<a href="{d["slug"]}.html">{d["name"]}</a>' for d in DEPTS)}
      </div>
      <div>
        <h4>Company</h4>
        <a href="portfolio.html">Portfolio</a><a href="about.html">About</a><a href="plan.html">Free plan</a><a href="contact.html">Contact</a>
      </div>
      <div>
        <h4>Talk to us</h4>
        <a href="tel:{PHONE}">{PHONE_DISPLAY}</a>
        <a href="https://wa.me/{WHATSAPP}" target="_blank" rel="noopener">WhatsApp</a>
      </div>
    </div>
    <p class="copy">&copy; <span id="year"></span> AXIA Automation Agency</p>
  </footer>

  <div class="float-actions" aria-label="Quick contact">
    <a href="https://wa.me/{WHATSAPP}" class="fab fab-wa" target="_blank" rel="noopener" aria-label="WhatsApp AXIA">{WA_ICON}<span>WhatsApp</span></a>
    <a href="tel:{PHONE}" class="fab fab-call" aria-label="Call AXIA">{PHONE_ICON}<span>Call now</span></a>
  </div>

  {scripts}<script type="module" src="main.js"></script>
</body>
</html>
"""


def page_hero(eyebrow, title, sub, flow, extra=""):
    return f"""    <section class="page-hero">
      <div class="page-hero-copy reveal">
        <p class="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p class="lead">{sub}</p>
        {extra}
      </div>
      <div class="engine-frame reveal">
        <canvas data-engine="flat" data-flow="{flow}" aria-hidden="true"></canvas>
        <p class="engine-caption">Live view of the workflow engine</p>
      </div>
    </section>
"""


def service_card(d):
    steps = "".join(f"<li>{esc(s[0])}</li>" for s in d["steps"])
    return f"""        <a class="card tilt reveal" href="{d["slug"]}.html" style="--c1:{d["c1"]};--c2:{d["c2"]}">
          <div class="card-icon"><svg viewBox="0 0 24 24">{d["icon"]}</svg></div>
          <p class="card-dept">{d["dept"]}</p>
          <h3>{d["name"]}</h3>
          <p>{esc(d["summary"])}</p>
          <ul class="steps">{steps}</ul>
          <span class="card-link">Explore the workflow &rarr;</span>
        </a>
"""


def case_card(d, idx):
    m = "".join(f"<div><b>{a}</b><span>{b}</span></div>" for a, b in d["case"]["metrics"])
    return f"""        <article class="work reveal" data-cat="{d["slug"]}">
          <div class="work-visual" style="--c1:{d["c1"]};--c2:{d["c2"]}"><span class="work-shape s{idx + 1}"></span><span class="work-label">{d["name"]}</span></div>
          <div class="work-body">
            <p class="work-meta">{d["case"]["meta"]}</p>
            <h3>{d["case"]["title"]}</h3>
            <p>{esc(d["case"]["body"])}</p>
            <div class="metrics">{m}</div>
            <a class="text-link" href="{d["slug"]}.html">See how the {d["name"]} works &rarr;</a>
          </div>
        </article>
"""


PROCESS = """      <ol class="process">
        <li class="reveal"><span class="num">01</span><h3>Audit</h3><p>We sit with your team, map the current process and find where hours are lost.</p></li>
        <li class="reveal"><span class="num">02</span><h3>Design</h3><p>We design the workflow, the tools it connects to and the points where a person approves.</p></li>
        <li class="reveal"><span class="num">03</span><h3>Pilot</h3><p>A working pilot goes live on real data in about two weeks, with your team watching every step.</p></li>
        <li class="reveal"><span class="num">04</span><h3>Scale</h3><p>Once results are proven, we roll it out fully and keep tuning it every month.</p></li>
      </ol>
"""

# ---------------------------------------------------------------- pages

def home():
    cards = "".join(service_card(d) for d in DEPTS)
    cases = "".join(case_card(d, i) for i, d in enumerate(DEPTS[:3]))
    body = f"""    <section class="hero">
      <canvas id="hero-canvas" data-engine="hero" data-flow="{flow_attr(HOME_FLOW)}" aria-hidden="true"></canvas>
      <div class="hero-content">
        <p class="eyebrow">Department automation agency</p>
        <h1>Your departments,<br /><span class="grad">on autopilot.</span></h1>
        <p class="lead">AXIA builds workflow engines that run the repetitive work of sales, marketing, accounts, clinics and hiring. Work flows in, gets checked, waits for your approval where it matters, and lands in your tools.</p>
        <div class="hero-cta">
          <a href="plan.html" class="btn">Get your free plan</a>
          <a href="tel:{PHONE}" class="btn btn-ghost">{PHONE_ICON}Call {PHONE_DISPLAY}</a>
        </div>
        <ul class="hero-tags"><li>WhatsApp first</li><li>Any language</li><li>Clients in any country</li><li>Human approval built in</li></ul>
      </div>
    </section>

    <section class="stats reveal">
      <div><strong data-count="5">0</strong><span>department engines</span></div>
      <div><strong data-count="24" data-suffix="x7">0</strong><span>always running</span></div>
      <div><strong data-count="70" data-suffix="%">0</strong><span>manual work we target to remove</span></div>
      <div><strong data-count="14" data-suffix=" days">0</strong><span>typical pilot launch</span></div>
    </section>

    <section class="section">
      <div class="section-head reveal">
        <p class="eyebrow">How the engine works</p>
        <h2>Inputs in. Checked work out.</h2>
        <p class="sub">Every AXIA system is the same reliable engine, set up for one department.</p>
      </div>
      <div class="how-grid">
        <div class="how reveal"><span class="how-n">IN</span><h3>Collect</h3><p>Messages, bills, resumes, leads and reports arrive from WhatsApp, email, forms and your existing software.</p></div>
        <div class="how reveal"><span class="how-n">RUN</span><h3>Process</h3><p>Each item moves through fixed stages: read, check against your rules, draft the next action.</p></div>
        <div class="how reveal how-approve"><span class="how-n">OK</span><h3>You approve</h3><p>Anything important stops for a person. You approve in one tap on your phone.</p></div>
        <div class="how reveal"><span class="how-n">OUT</span><h3>Deliver</h3><p>Approved work lands in your accounting software, CRM, calendars and customer WhatsApp, with a full log.</p></div>
      </div>
    </section>

    <section class="section section-alt">
      <div class="section-head reveal">
        <p class="eyebrow">What we automate</p>
        <h2>Five complete department engines</h2>
        <p class="sub">Not small one-off bots. Each system runs a full workflow end to end and asks your team before anything important goes out.</p>
      </div>
      <div class="cards">
{cards}        <div class="card card-cta reveal">
          <h3>Have a different department in mind?</h3>
          <p>We map your process, find the repeat work and design an engine around it.</p>
          <a href="contact.html" class="btn">Talk to us</a>
        </div>
      </div>
    </section>

    <section class="section">
      <div class="section-head reveal">
        <p class="eyebrow">Portfolio</p>
        <h2>What these engines look like in practice</h2>
        <p class="sub">Sample engagements. Figures are illustrative targets for a typical setup.</p>
      </div>
      <div class="work-grid">
{cases}      </div>
      <div class="center reveal"><a href="portfolio.html" class="btn btn-ghost">See all case studies</a></div>
    </section>

    <section class="section section-alt">
      <div class="section-head reveal"><p class="eyebrow">How we work</p><h2>From messy process to running engine</h2></div>
{PROCESS}    </section>
"""
    return layout("index", "AXIA | Department Automation Agency", "AXIA builds workflow engines that run sales, marketing, accounts, clinic and hiring work for businesses worldwide, with your team approving every key step.", body)


def services():
    cards = "".join(service_card(d) for d in DEPTS)
    body = page_hero(
        "Services",
        'Five engines.<br /><span class="grad">One for each department.</span>',
        "Pick the department that slows you down the most. We set up its engine, connect it to your tools and run a pilot on your real data.",
        flow_attr(HOME_FLOW),
        f'<div class="hero-cta"><a href="contact.html" class="btn">Book a free audit</a><a href="tel:{PHONE}" class="btn btn-ghost">{PHONE_ICON}Call now</a></div>',
    ) + f"""
    <section class="section">
      <div class="cards">
{cards}        <div class="card card-cta reveal">
          <h3>Need a custom engine?</h3>
          <p>Logistics, real estate, education, manufacturing: if the work repeats, it can run on an engine.</p>
          <a href="contact.html" class="btn">Talk to us</a>
        </div>
      </div>
    </section>

    <section class="section section-alt">
      <div class="section-head reveal"><p class="eyebrow">Every engagement includes</p><h2>What you get</h2></div>
      <div class="trust">
        <div class="reveal"><h4>Process audit</h4><p>A written map of your current workflow, where time is lost and what the engine will take over.</p></div>
        <div class="reveal"><h4>Setup and integrations</h4><p>Connected to your WhatsApp, email, accounting software, CRM and sheets. No new software for your team to learn.</p></div>
        <div class="reveal"><h4>Approval dashboard</h4><p>One place on your phone to approve, edit or stop anything before it goes out.</p></div>
        <div class="reveal"><h4>Two-week pilot</h4><p>Live on your real data with your team watching every step before full rollout.</p></div>
        <div class="reveal"><h4>Monthly tuning</h4><p>We review results every month, adjust rules and add new steps as your business grows.</p></div>
        <div class="reveal"><h4>Full activity log</h4><p>Every item the engine touched, what it did and who approved it, ready for audits.</p></div>
      </div>
    </section>

    <section class="section">
      <div class="section-head reveal"><p class="eyebrow">How we work</p><h2>From audit to running engine</h2></div>
{PROCESS}    </section>
"""
    return layout("services", "Services | AXIA", "Five department automation engines for businesses worldwide: sales, marketing, accounts, clinics and hiring.", body)


def dept_page(d, idx):
    steps = "".join(
        f'<li class="reveal{" is-approval" if i == d["flow"]["approval"] else ""}"><span class="num">{i + 1:02d}</span><div><h3>{esc(n)}</h3><p>{esc(t)}</p></div></li>'
        for i, (n, t) in enumerate(d["steps"])
    )
    tools = "".join(f"<li>{esc(t)}</li>" for t in d["tools"])
    others = "".join(
        f'<a class="mini reveal" href="{o["slug"]}.html" style="--c1:{o["c1"]};--c2:{o["c2"]}"><div class="card-icon"><svg viewBox="0 0 24 24">{o["icon"]}</svg></div><span>{o["dept"]}</span><b>{o["name"]}</b></a>'
        for o in DEPTS if o is not d
    )
    body = page_hero(
        f'{d["dept"]} engine',
        f'{d["name"]}',
        d["tagline"],
        flow_attr(d["flow"], d["c1"], d["c2"]),
        f'<div class="hero-cta"><a href="plan.html?service={d["slug"]}" class="btn">Get your free plan</a><a href="tel:{PHONE}" class="btn btn-ghost">{PHONE_ICON}Call now</a></div>',
    ) + f"""
    <section class="section" style="--c1:{d["c1"]};--c2:{d["c2"]}">
      <div class="split">
        <div class="reveal">
          <p class="eyebrow">The problem</p>
          <h2>Where the hours go today</h2>
          <p class="sub">{esc(d["problem"])}</p>
          <p class="eyebrow tools-head">Works with</p>
          <ul class="tool-list">{tools}</ul>
        </div>
        <div>
          <p class="eyebrow reveal">The engine, stage by stage</p>
          <ol class="stage-list">{steps}</ol>
        </div>
      </div>
    </section>

    <section class="section section-alt">
      <div class="section-head reveal"><p class="eyebrow">Sample engagement</p><h2>What it looks like for a real business</h2><p class="sub">Figures are illustrative targets for a typical setup.</p></div>
      <div class="work-grid">
{case_card(d, idx)}      </div>
    </section>

    <section class="section">
      <div class="section-head reveal"><p class="eyebrow">Other engines</p><h2>Automate another department</h2></div>
      <div class="mini-grid">{others}</div>
    </section>
"""
    return layout(d["slug"], f'{d["name"]} | AXIA', d["summary"], body)


def portfolio():
    chips = '<button class="chip active" data-filter="all">All</button>' + "".join(f'<button class="chip" data-filter="{d["slug"]}">{d["dept"]}</button>' for d in DEPTS)
    cases = "".join(case_card(d, i) for i, d in enumerate(DEPTS))
    body = page_hero(
        "Portfolio",
        'Engines at work in<br /><span class="grad">real businesses.</span>',
        "Sample engagements showing how each AXIA engine fits a real business. Figures are illustrative targets for a typical setup.",
        flow_attr(HOME_FLOW),
    ) + f"""
    <section class="section">
      <div class="filters reveal" role="tablist" aria-label="Filter portfolio">{chips}</div>
      <div class="work-grid">
{cases}      </div>
    </section>
"""
    return layout("portfolio", "Portfolio | AXIA", "Sample AXIA automation engagements across sales, marketing, accounts, clinics and hiring.", body)


def about():
    body = page_hero(
        "About AXIA",
        'We build the engines.<br /><span class="grad">Your team keeps control.</span>',
        "AXIA is an automation agency for businesses in any country. We take the repetitive work off your departments so your people can do the work only people can do.",
        flow_attr(HOME_FLOW),
    ) + f"""
    <section class="section">
      <div class="split">
        <div class="reveal">
          <p class="eyebrow">Why we exist</p>
          <h2>Most teams are stuck doing copy-paste work</h2>
          <p class="sub">Typing bills into accounting software. Forwarding resumes. Writing the same follow-up message for the hundredth time. Most businesses run on email, WhatsApp, spreadsheets and hard work, and a lot of that work repeats every single day.</p>
          <p class="sub">We design engines that do the repeat part reliably, in the tools you already use, and stop for a person whenever a decision matters.</p>
        </div>
        <div class="values">
          <div class="reveal"><h4>Approval first</h4><p>Nothing important is sent, paid or filed without a person saying yes.</p></div>
          <div class="reveal"><h4>Your tools, not ours</h4><p>WhatsApp, Gmail, QuickBooks, Tally, Zoho and Google Sheets. No new software for your team.</p></div>
          <div class="reveal"><h4>Built for any market</h4><p>Your local tax rules, your customers' languages, your currency and your time zone.</p></div>
          <div class="reveal"><h4>Results you can measure</h4><p>Every engine comes with a log and a monthly report of hours saved and work done.</p></div>
        </div>
      </div>
    </section>

    <section class="section section-alt">
      <div class="section-head reveal"><p class="eyebrow">How we work</p><h2>From audit to running engine</h2></div>
{PROCESS}    </section>
"""
    return layout("about", "About | AXIA", "AXIA is a department automation agency for businesses worldwide.", body)


def contact():
    opts = "".join(f"<option>{d['dept']}: {d['name']}</option>" for d in DEPTS) + "<option>Something else</option>"
    body = f"""    <section class="page-hero contact-hero">
      <div class="page-hero-copy reveal">
        <p class="eyebrow">Free process audit</p>
        <h1>Tell us which department <span class="grad">slows you down.</span></h1>
        <p class="lead">We will map the process and show you exactly what AXIA can take off your team's plate. No cost, no commitment.</p>
        <div class="contact-cards">
          <a href="tel:{PHONE}" class="contact-card">{PHONE_ICON}<div><b>Call us</b><span>{PHONE_DISPLAY}</span></div></a>
          <a href="https://wa.me/{WHATSAPP}" class="contact-card" target="_blank" rel="noopener">{WA_ICON}<div><b>WhatsApp</b><span>Message us anytime</span></div></a>
        </div>
      </div>
      <form class="contact-form reveal" id="contact-form">
        <label>Name<input name="name" required placeholder="Your name" /></label>
        <label>Company<input name="company" placeholder="Company name" /></label>
        <label>Phone or WhatsApp<input name="phone" required placeholder="+91" /></label>
        <label>Department to automate<select name="dept">{opts}</select></label>
        <button class="btn" type="submit">Send on WhatsApp</button>
        <p class="form-note" id="form-note" role="status"></p>
      </form>
    </section>
"""
    return layout("contact", "Contact | AXIA", "Book a free process audit with AXIA. Call or WhatsApp +91 89305 22312.", body, engine=False)

PLAN_SERVICES = [("whatsapp", "Customer chat", "WhatsApp Automation", "#25d366", "#2ee6d6", "Replies to every customer in seconds, day and night.")] + [
    (d["slug"], d["dept"], d["name"], d["c1"], d["c2"], d["tagline"]) for d in DEPTS
]

CURRENCY_OPTIONS = ["USD", "EUR", "GBP", "INR", "AED", "SAR", "AUD", "CAD", "SGD", "ZAR", "NGN", "KES"]
LANGUAGE_OPTIONS = ["English", "Hindi", "Hinglish", "Spanish", "Arabic", "French", "Portuguese"]


def plan():
    svc = "".join(
        f'<label class="svc" style="--c1:{c1};--c2:{c2}"><input type="radio" name="service" value="{slug}"{" checked" if i == 0 else ""} />'
        f'<span class="svc-dept">{esc(dept)}</span><b>{esc(name)}</b><span class="svc-line">{esc(line)}</span></label>'
        for i, (slug, dept, name, c1, c2, line) in enumerate(PLAN_SERVICES)
    )
    cur = "".join(f"<option>{c}</option>" for c in CURRENCY_OPTIONS)
    lang = "".join(f"<option>{l}</option>" for l in LANGUAGE_OPTIONS)
    body = f"""    <section class="page-hero plan-hero">
      <div class="page-hero-copy reveal">
        <p class="eyebrow">Free automation plan</p>
        <h1>See your business <span class="grad">run on autopilot.</span></h1>
        <p class="lead">Pick a service and tell us about your business. In about a minute the AXIA engine builds your plan.</p>
      </div>
      <ol class="plan-gets reveal">
        <li><b>Why you need it</b><span>The concept, explained around your own problem.</span></li>
        <li><b>A live demo</b><span>Your business, your customers, the problem being solved in front of you.</span></li>
        <li><b>Your pitch deck</b><span>Problem, solution, savings and rollout, ready to save as PDF.</span></li>
        <li><b>On your WhatsApp</b><span>Your problem, the solution, your savings and your extra profit.</span></li>
      </ol>
    </section>

    <section class="section plan-section">
      <form id="plan-form" class="plan-form reveal" data-engine-url="{esc(ENGINE_URL)}" data-whatsapp="{WHATSAPP}" novalidate>
        <fieldset>
          <legend><span>1</span>Pick a service</legend>
          <div class="svc-grid">{svc}</div>
        </fieldset>
        <fieldset>
          <legend><span>2</span>About you</legend>
          <div class="field-grid">
            <label>Your name<input name="name" required maxlength="80" autocomplete="name" /></label>
            <label>Business name<input name="business_name" required maxlength="120" autocomplete="organization" /></label>
            <label>Industry<input name="industry" maxlength="120" placeholder="Dental clinic, furniture store, logistics..." /></label>
            <label>Country<input name="country" maxlength="60" autocomplete="country-name" /></label>
            <label>WhatsApp number<input name="whatsapp" required type="tel" autocomplete="tel" placeholder="+1 415 555 0100" /></label>
            <label>Language for your plan<select name="language">{lang}</select></label>
          </div>
        </fieldset>
        <fieldset>
          <legend><span>3</span>Your business and problem</legend>
          <label>What does your business do?<textarea name="business_description" rows="3" maxlength="1000" placeholder="Who your customers are, what you sell, how they reach you."></textarea></label>
          <label>What is the biggest problem you want solved?<textarea name="main_problem" required rows="3" maxlength="1000" placeholder="We get 80 WhatsApp messages a day and reply hours late, so customers buy elsewhere."></textarea></label>
        </fieldset>
        <fieldset>
          <legend><span>4</span>Your numbers</legend>
          <p class="hint">Rough numbers are fine. They are only used to estimate your savings and profit.</p>
          <div class="field-grid three">
            <label>Currency<select name="currency">{cur}</select></label>
            <label>Team size<input name="team_size" type="number" min="1" value="5" /></label>
            <label>Customer enquiries a month<input name="monthly_inquiries" type="number" min="0" value="300" /></label>
            <label>Average order value<input name="avg_order_value" type="number" min="0" value="2000" /></label>
            <label>Hours a week your team spends on this work<input name="hours_per_week" type="number" min="0" value="20" /></label>
            <label>Staff cost per hour<input name="hourly_cost" type="number" min="0" value="200" /></label>
            <label>Enquiries that become customers (%)<input name="conversion_pct" type="number" min="0.1" max="100" step="0.1" value="10" /></label>
            <label>Profit margin (%)<input name="margin_pct" type="number" min="1" max="100" value="30" /></label>
          </div>
        </fieldset>
        <button class="btn plan-submit" type="submit">Build my plan</button>
        <p class="form-note" id="plan-note" role="status"></p>
      </form>

      <div class="plan-loading" id="plan-loading" hidden>
        <div class="loader" aria-hidden="true"><span></span><span></span><span></span></div>
        <p id="plan-loading-text">Understanding your business</p>
      </div>

      <div class="plan-result" id="plan-result" hidden></div>
    </section>
"""
    return layout("plan", "Your free automation plan | AXIA", "Tell AXIA about your business and get a tailored automation plan: concept, live demo, pitch deck and savings on WhatsApp.", body, engine=False).replace(
        '<script type="module" src="main.js"></script>', '<script type="module" src="main.js"></script>\n  <script type="module" src="plan.js"></script>'
    )


def main():
    pages = {"index.html": home(), "services.html": services(), "portfolio.html": portfolio(), "about.html": about(), "contact.html": contact(), "plan.html": plan()}
    for i, d in enumerate(DEPTS):
        pages[f'{d["slug"]}.html'] = dept_page(d, i)
    for name, content in pages.items():
        if re.search(r"\bai\b|artificial intelligence", html.unescape(content), re.I):
            raise SystemExit(f"Brand rule: {name} contains the word AI")
        (OUT / name).write_text(content)
        print("wrote", name)


if __name__ == "__main__":
    main()

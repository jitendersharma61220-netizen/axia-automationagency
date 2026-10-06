"""The services a visitor can pick, with what each one does and the
assumptions used to estimate savings and extra profit.

The assumptions are deliberately conservative and are shown to the visitor
next to every estimate, so the numbers are never a black box.
"""

SERVICES = {
    "whatsapp": {
        "name": "WhatsApp Automation",
        "dept": "Customer chat",
        "one_liner": "A WhatsApp desk that replies to every customer in seconds, day and night.",
        "concept": (
            "Every message that reaches your WhatsApp number is read, understood and answered "
            "in seconds: prices, availability, catalogue, order status, bookings and payments. "
            "Repeat questions never reach your team again, every enquiry gets a follow-up, and "
            "the chat is handed to a person the moment a human decision is needed."
        ),
        "stages": ["Capture every message", "Understand the request", "Answer and act", "Hand off to your team", "Follow up automatically"],
        "tools": ["WhatsApp Business", "Google Sheets", "Your CRM", "Payment links", "Google Calendar"],
        # share of the repetitive hours the engine takes over
        "automation_share": 0.6,
        # relative lift in conversion from instant replies and follow-ups
        "conversion_uplift": 0.25,
    },
    "sales": {
        "name": "Sales Outreach Agent",
        "dept": "Sales",
        "one_liner": "A sales desk that researches, writes and follows up on every lead, every day.",
        "concept": (
            "Every new lead is researched, scored against your best customers and sent a personal "
            "first message. Silence gets a follow-up, every reply is sorted into interested, later "
            "or not now, and meetings land straight in your reps' calendars and your CRM."
        ),
        "stages": ["Research the lead", "Score the fit", "Write the outreach", "You approve", "Send, follow up and book"],
        "tools": ["WhatsApp Business", "Gmail / Outlook", "Zoho CRM", "HubSpot", "Google Calendar"],
        "automation_share": 0.55,
        "conversion_uplift": 0.3,
    },
    "marketing": {
        "name": "Campaign Engine",
        "dept": "Marketing",
        "one_liner": "Plans, writes and reports on your campaigns across every channel.",
        "concept": (
            "Give the engine a goal and it plans the campaign, writes the posts, emails and WhatsApp "
            "broadcasts in your brand voice, schedules them after your approval and reports every "
            "week on what worked, with the next best move."
        ),
        "stages": ["Plan the campaign", "Write every channel", "You approve", "Publish on schedule", "Report and improve"],
        "tools": ["Instagram", "Facebook", "LinkedIn", "Mailchimp", "WhatsApp broadcasts", "Google Analytics"],
        "automation_share": 0.5,
        "conversion_uplift": 0.15,
    },
    "accounts": {
        "name": "Accounts Back Office",
        "dept": "Accounts and operations",
        "one_liner": "Reads bills, matches orders, checks tax and lines up payments for approval.",
        "concept": (
            "Bills arriving on email or WhatsApp are read automatically, matched against purchase "
            "orders and delivery notes, checked for tax and duplicate errors and entered into your "
            "accounting software. Your finance head approves payments in one place."
        ),
        "stages": ["Collect the bills", "Read and extract", "Match and check", "You approve", "Post and pay"],
        "tools": ["Tally", "QuickBooks", "Xero", "Zoho Books", "Gmail", "Google Drive"],
        "automation_share": 0.7,
        "conversion_uplift": 0.0,
    },
    "clinic": {
        "name": "Clinic Assistant",
        "dept": "Clinics and healthcare",
        "one_liner": "Bookings, reminders, report explainers and visit notes that the doctor approves.",
        "concept": (
            "Patients book and reschedule on WhatsApp, get reminders before every visit, and receive "
            "simple explanations of their lab reports after the doctor approves them. Visit notes are "
            "drafted for the doctor to check and sign, so the day runs on time."
        ),
        "stages": ["Book and remind", "Prepare the visit", "Draft notes", "Doctor approves", "Follow up with the patient"],
        "tools": ["WhatsApp Business", "Google Calendar", "Your clinic software", "Google Sheets"],
        "automation_share": 0.55,
        "conversion_uplift": 0.15,
    },
    "hiring": {
        "name": "Hiring Agent",
        "dept": "HR and hiring",
        "one_liner": "Ranks resumes, screens candidates on WhatsApp and books interviews.",
        "concept": (
            "Every application is read and ranked against the job, shortlisted candidates answer "
            "screening questions on WhatsApp, and interviews are booked straight into your managers' "
            "calendars. Your HR team only meets the right people."
        ),
        "stages": ["Collect applications", "Rank resumes", "Screen on WhatsApp", "You approve", "Book interviews"],
        "tools": ["Naukri / Indeed / LinkedIn", "Gmail", "WhatsApp Business", "Google Calendar", "Google Sheets"],
        "automation_share": 0.65,
        "conversion_uplift": 0.0,
    },
}


def public_catalogue():
    """What the website needs to build the picker."""
    return [
        {"slug": slug, "name": s["name"], "dept": s["dept"], "one_liner": s["one_liner"]}
        for slug, s in SERVICES.items()
    ]

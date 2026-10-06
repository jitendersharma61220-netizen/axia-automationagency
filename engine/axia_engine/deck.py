"""Render a proposal as a printable HTML pitch deck (16:9 slides).

Open it in a browser to present, or print it to save a PDF.
"""

import html

PHONE = "+918930522312"
PHONE_DISPLAY = "+91 89305 22312"
WHATSAPP = "918930522312"


def e(s):
    return html.escape(str(s), quote=True)


CSS = """
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#070a1a;--panel:#11152e;--line:#262b52;--text:#eef0ff;--muted:#a3a8cf;--p:#7b5cff;--t:#2ee6d6}
body{background:#03040c;color:var(--text);font-family:Inter,system-ui,sans-serif}
.slide{width:1280px;height:720px;margin:24px auto;padding:64px 80px;background:radial-gradient(1000px 500px at 85% -10%,#2a1f6b 0%,transparent 60%),var(--bg);position:relative;overflow:hidden;display:flex;flex-direction:column;border-radius:14px}
.slide::after{content:"AXIA";position:absolute;right:48px;bottom:32px;font:700 14px 'Space Grotesk',sans-serif;letter-spacing:.2em;color:var(--muted)}
h1,h2,h3{font-family:'Space Grotesk',sans-serif;line-height:1.1}
h1{font-size:64px;max-width:950px}
h2{font-size:44px;margin-bottom:32px;max-width:1000px}
.eyebrow{color:var(--t);font-weight:600;letter-spacing:.14em;text-transform:uppercase;font-size:14px;margin-bottom:18px}
.lead{font-size:24px;color:var(--muted);max-width:900px;margin-top:24px;line-height:1.45}
.grad{background:linear-gradient(90deg,var(--p),var(--t));-webkit-background-clip:text;background-clip:text;color:transparent}
ul.points{list-style:none;display:grid;gap:16px;font-size:23px;line-height:1.4}
ul.points li{padding-left:34px;position:relative}
ul.points li::before{content:"";position:absolute;left:0;top:10px;width:14px;height:14px;border-radius:4px;background:linear-gradient(135deg,var(--p),var(--t))}
.flow{display:grid;gap:14px}
.flow div{display:grid;grid-template-columns:48px 260px 1fr;align-items:start;gap:16px;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 18px;font-size:18px;line-height:1.4}
.flow b{font-family:'Space Grotesk',sans-serif;font-size:20px}
.flow span.n{color:var(--t);font-weight:700}
.flow p{color:var(--muted)}
.chat{display:flex;flex-direction:column;gap:8px;max-width:760px}
.msg{padding:8px 14px;border-radius:14px;font-size:15px;line-height:1.35;max-width:620px}
.msg.customer{background:#1f2547;align-self:flex-start}
.msg.engine{background:#14533f;align-self:flex-end}
.msg.team{background:#3a2a76;align-self:center;font-size:15px}
.who{display:block;font-size:12px;color:var(--muted);margin-bottom:2px;text-transform:uppercase;letter-spacing:.08em}
.demo-grid{display:grid;grid-template-columns:1fr 360px;gap:40px}
.side{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:22px;font-size:17px;color:var(--muted);line-height:1.45}
.side h3{color:var(--text);font-size:20px;margin-bottom:12px}
.side li{margin:0 0 10px 18px}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:18px;margin-bottom:28px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:22px}
.stat b{display:block;font:700 34px 'Space Grotesk',sans-serif;margin-bottom:6px}
.stat span{color:var(--muted);font-size:15px}
.stat.big{background:linear-gradient(135deg,#3a2a96,#0e5a59);border:0}
.small{font-size:15px;color:var(--muted);line-height:1.5}
.small li{margin:0 0 6px 18px}
.timeline{display:grid;gap:18px}
.timeline div{display:grid;grid-template-columns:220px 1fr;gap:24px;font-size:22px;border-left:3px solid var(--p);padding-left:22px}
.timeline b{font-family:'Space Grotesk',sans-serif;color:var(--t)}
.cta{display:flex;gap:18px;margin-top:40px}
.btn{display:inline-block;padding:16px 26px;border-radius:999px;font-weight:600;font-size:20px;text-decoration:none;color:#fff;background:linear-gradient(90deg,var(--p),#5a8cff)}
.btn.ghost{background:transparent;border:1px solid var(--line)}
.center{justify-content:center}
.toolbar{position:sticky;top:0;z-index:5;display:flex;justify-content:center;gap:12px;padding:12px;background:#03040ccc;backdrop-filter:blur(8px)}
.toolbar button{font:600 15px Inter,sans-serif;padding:10px 18px;border-radius:999px;border:0;background:var(--p);color:#fff;cursor:pointer}
@media print{
  @page{size:1280px 720px;margin:0}
  body{background:var(--bg)}
  .toolbar{display:none}
  .slide{margin:0;border-radius:0;page-break-after:always;break-after:page}
}
@media (max-width:1300px){.slide{zoom:calc(100vw / 1330px)}}
"""


def render(p):
    i, c, n = p["intake"], p["content"], p["numbers"]
    d = n["display"]
    svc = p["service_name"]
    slides = []

    slides.append(f"""<section class="slide center">
  <p class="eyebrow">Proposal for {e(i['business_name'])}</p>
  <h1>{e(svc)} <span class="grad">for {e(i['business_name'])}</span></h1>
  <p class="lead">{e(c['headline'])}</p>
  <p class="lead" style="font-size:18px;margin-top:48px">Prepared for {e(i['name'])} · {e(p['created'][:10])}</p>
</section>""")

    slides.append(f"""<section class="slide">
  <p class="eyebrow">The problem</p>
  <h2>What is slowing {e(i['business_name'])} down</h2>
  <p class="lead" style="margin-top:0">{e(c['problem_summary'])}</p>
  <div class="stats" style="margin-top:40px;grid-template-columns:repeat(3,1fr)">
    <div class="stat"><b>{i['hours_per_week']:g} hrs</b><span>a week spent on this work today</span></div>
    <div class="stat"><b>{i['monthly_inquiries']:,.0f}</b><span>customer enquiries a month</span></div>
    <div class="stat"><b>{i['team_size']:g}</b><span>people on the team</span></div>
  </div>
</section>""")

    reasons = "".join(f"<li>{e(r)}</li>" for r in c["why_you_need_it"])
    slides.append(f"""<section class="slide">
  <p class="eyebrow">Why you need it</p>
  <h2>Why {e(svc)} fits your business</h2>
  <ul class="points">{reasons}</ul>
</section>""")

    steps = "".join(
        f'<div><span class="n">{k + 1:02d}</span><b>{e(s["step"])}</b><p>{e(s["detail"])}</p></div>'
        for k, s in enumerate(c["how_it_works"])
    )
    slides.append(f"""<section class="slide">
  <p class="eyebrow">The solution</p>
  <h2>How the engine works, stage by stage</h2>
  <div class="flow">{steps}</div>
</section>""")

    who = {"customer": "Customer", "engine": "AXIA engine", "team": "Your team"}
    msgs = "".join(
        f'<div class="msg {e(m["sender"])}"><span class="who">{who.get(m["sender"], "")}</span>{e(m["text"])}</div>'
        for m in c["demo"]["messages"][:6]
    )
    bts = "".join(f"<li>{e(b)}</li>" for b in c["demo"]["behind_the_scenes"])
    slides.append(f"""<section class="slide">
  <p class="eyebrow">Demo</p>
  <h2 style="margin-bottom:20px">{e(c['demo']['scenario'])}</h2>
  <div class="demo-grid">
    <div class="chat">{msgs}</div>
    <div class="side"><h3>Behind the scenes</h3><ul>{bts}</ul></div>
  </div>
</section>""")

    assumptions = "".join(f"<li>{e(a)}</li>" for a in n["assumptions"])
    slides.append(f"""<section class="slide">
  <p class="eyebrow">Savings and profit</p>
  <h2>What it is worth to {e(i['business_name'])}</h2>
  <div class="stats">
    <div class="stat"><b>{e(d['hours_saved_month'])}</b><span>of team time saved a month</span></div>
    <div class="stat"><b>{e(d['labour_saving_month'])}</b><span>saved on team time a month</span></div>
    <div class="stat"><b>{e(d['extra_profit_month'])}</b><span>extra profit a month</span></div>
    <div class="stat big"><b>{e(d['yearly_gain'])}</b><span>total gain a year</span></div>
  </div>
  <p class="small">Estimate based on the numbers you shared:</p>
  <ul class="small">{assumptions}</ul>
</section>""")

    phases = "".join(f"<div><b>{e(r['when'])}</b><span>{e(r['what'])}</span></div>" for r in c["rollout"])
    slides.append(f"""<section class="slide">
  <p class="eyebrow">Rollout</p>
  <h2>From kickoff to fully live</h2>
  <div class="timeline">{phases}</div>
</section>""")

    slides.append(f"""<section class="slide center">
  <p class="eyebrow">Next step</p>
  <h1>Let's map it on <span class="grad">your real process.</span></h1>
  <p class="lead">A free process audit with the AXIA team. No cost, no commitment.</p>
  <div class="cta">
    <a class="btn" href="https://wa.me/{WHATSAPP}">WhatsApp {PHONE_DISPLAY}</a>
    <a class="btn ghost" href="tel:{PHONE}">Call us</a>
  </div>
</section>""")

    body = "\n".join(slides)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{e(svc)} for {e(i['business_name'])} | AXIA</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Inter:wght@400;600&display=swap" rel="stylesheet" />
<style>{CSS}</style>
</head>
<body>
<div class="toolbar"><button onclick="window.print()">Save as PDF</button></div>
{body}
</body>
</html>
"""

// Free plan page: sends the visitor's details to the AXIA proposal engine
// (engine/ in this repo) and shows the concept, a live demo, the savings,
// the pitch deck and the WhatsApp message. Opening plan.html?id=<id> shows a
// saved plan. If no engine is reachable, the details go to AXIA on WhatsApp.
const form = document.getElementById("plan-form");
const note = document.getElementById("plan-note");
const loading = document.getElementById("plan-loading");
const loadingText = document.getElementById("plan-loading-text");
const result = document.getElementById("plan-result");
const params = new URLSearchParams(location.search);
const ENGINE = (params.get("engine") || form.dataset.engineUrl || "").replace(/\/$/, "");
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

async function engineReachable() {
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 4000);
    const r = await fetch(`${ENGINE}/health`, { signal: ctrl.signal });
    clearTimeout(t);
    return r.ok;
  } catch {
    return false;
  }
}

// Preselect a service from ?service=sales (links on the department pages)
const pre = params.get("service");
if (pre) {
  const radio = form.querySelector(`input[name="service"][value="${CSS.escape(pre)}"]`);
  if (radio) radio.checked = true;
}

const STEPS = [
  "Understanding your business",
  "Explaining why you need it",
  "Building a demo around your customers",
  "Calculating your savings and profit",
  "Preparing your pitch deck",
  "Writing your WhatsApp message",
];
let stepTimer;
function showLoading(on) {
  loading.hidden = !on;
  form.hidden = on;
  clearInterval(stepTimer);
  if (!on) return;
  let i = 0;
  loadingText.textContent = STEPS[0];
  stepTimer = setInterval(() => {
    i = Math.min(i + 1, STEPS.length - 1);
    loadingText.textContent = STEPS[i];
  }, 6000);
  loading.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "center" });
}

function sendOnWhatsApp(data) {
  const text = [
    "Hi AXIA, please prepare my free automation plan.",
    `Service: ${form.querySelector('input[name="service"]:checked')?.closest("label").querySelector("b").textContent}`,
    `Name: ${data.name}`,
    `Business: ${data.business_name}${data.industry ? ` (${data.industry})` : ""}${data.country ? `, ${data.country}` : ""}`,
    `Problem: ${data.main_problem}`,
    `Enquiries a month: ${data.monthly_inquiries}, hours a week on this work: ${data.hours_per_week}`,
  ].join("\n");
  window.open(`https://wa.me/${form.dataset.whatsapp}?text=${encodeURIComponent(text)}`, "_blank", "noopener");
  note.textContent = "WhatsApp is opening with your details. Press send and we will share your plan there.";
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  note.textContent = "";
  const missing = [...form.querySelectorAll("[required]")].find((el) => !el.value.trim());
  if (missing) {
    note.textContent = `Please fill in: ${missing.closest("label").firstChild.textContent.trim()}`;
    missing.focus();
    return;
  }
  const data = Object.fromEntries(new FormData(form));
  if (!(await engineReachable())) return sendOnWhatsApp(data);

  showLoading(true);
  try {
    const r = await fetch(`${ENGINE}/api/proposals`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    const body = await r.json();
    if (!r.ok) throw new Error(body.error || "Something went wrong");
    history.replaceState(null, "", `?id=${encodeURIComponent(body.id)}${params.get("engine") ? `&engine=${encodeURIComponent(ENGINE)}` : ""}`);
    showLoading(false);
    render(body);
  } catch (err) {
    showLoading(false);
    note.textContent = err.message;
  }
});

// ------------------------------------------------------------------ render

const WHO = { customer: "Customer", engine: "AXIA engine", team: "Your team" };

function render(p) {
  const c = p.content;
  const n = p.numbers;
  const d = n.display;
  form.hidden = true;
  const why = c.why_you_need_it.map((r) => `<li>${esc(r)}</li>`).join("");
  const how = c.how_it_works
    .map((s, i) => `<li><span class="num">${String(i + 1).padStart(2, "0")}</span><div><h3>${esc(s.step)}</h3><p>${esc(s.detail)}</p></div></li>`)
    .join("");
  const bts = c.demo.behind_the_scenes.map((b) => `<li>${esc(b)}</li>`).join("");
  const assumptions = n.assumptions.map((a) => `<li>${esc(a)}</li>`).join("");
  const rollout = c.rollout.map((r) => `<li><b>${esc(r.when)}</b><span>${esc(r.what)}</span></li>`).join("");
  const wa = p.whatsapp;
  const waBlock = wa.sent
    ? `<p class="wa-status ok">Sent to your WhatsApp.</p>`
    : wa.save_link
      ? `<p class="wa-status">Tap below to save this plan in your own WhatsApp.</p><a class="btn btn-wa" href="${esc(wa.save_link)}" target="_blank" rel="noopener">Save to my WhatsApp</a>`
      : "";

  result.innerHTML = `
    <div class="plan-head">
      <p class="eyebrow">${esc(p.service_name)} plan for ${esc(p.intake.business_name)}</p>
      <h2>${esc(c.headline)}</h2>
    </div>

    <article class="plan-block">
      <p class="plan-step"><span>1</span>The concept</p>
      <div class="split">
        <div>
          <h3>Your problem</h3>
          <p class="sub">${esc(c.problem_summary)}</p>
          <h3>What ${esc(p.service_name)} does</h3>
          <p class="sub">${esc(p.concept)}</p>
        </div>
        <div>
          <h3>Why your business needs it</h3>
          <ul class="ticks">${why}</ul>
        </div>
      </div>
      <h3 class="how-title">How it works for you</h3>
      <ol class="stage-list">${how}</ol>
    </article>

    <article class="plan-block">
      <p class="plan-step"><span>2</span>Your demo</p>
      <div class="demo">
        <div class="phone">
          <div class="phone-top"><span class="dot"></span><b>${esc(p.intake.business_name)}</b><small>WhatsApp</small></div>
          <div class="chat" id="demo-chat" aria-live="polite"></div>
        </div>
        <div>
          <h3>${esc(c.demo.scenario)}</h3>
          <p class="sub">Watch the engine handle it. Messages in green are the engine; purple notes are your team.</p>
          <h4 class="bts-title">Behind the scenes</h4>
          <ul class="ticks">${bts}</ul>
          <button class="btn btn-ghost" type="button" id="demo-replay">Play again</button>
        </div>
      </div>
    </article>

    <article class="plan-block">
      <p class="plan-step"><span>3</span>Your savings and profit</p>
      <div class="money">
        <div><b>${esc(d.hours_saved_month)}</b><span>team time saved a month</span></div>
        <div><b>${esc(d.labour_saving_month)}</b><span>saved on team time a month</span></div>
        <div><b>${esc(d.extra_profit_month)}</b><span>extra profit a month</span></div>
        <div class="total"><b>${esc(d.yearly_gain)}</b><span>total gain a year</span></div>
      </div>
      <p class="hint">Estimate from the numbers you shared:</p>
      <ul class="assumptions">${assumptions}</ul>
      <h3 class="how-title">Rollout</h3>
      <ul class="rollout">${rollout}</ul>
    </article>

    <article class="plan-block plan-actions">
      <div>
        <p class="plan-step"><span>4</span>Your pitch deck</p>
        <p class="sub">Problem, solution, demo, savings and rollout on eight slides. Open it and use Save as PDF to keep or share it.</p>
        <a class="btn" href="${esc(p.deck_url)}" target="_blank" rel="noopener">Open my pitch deck</a>
      </div>
      <div>
        <p class="plan-step"><span>5</span>On WhatsApp</p>
        ${waBlock}
        <pre class="wa-preview">${esc(wa.text)}</pre>
        <a class="btn btn-ghost" href="${esc(wa.chat_link)}" target="_blank" rel="noopener">Book my free audit on WhatsApp</a>
      </div>
    </article>`;
  result.hidden = false;
  result.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" });
  playDemo(c.demo.messages);
  document.getElementById("demo-replay").addEventListener("click", () => playDemo(c.demo.messages));
}

let demoRun = 0;
async function playDemo(messages) {
  const run = ++demoRun;
  const chat = document.getElementById("demo-chat");
  chat.innerHTML = "";
  const wait = (ms) => new Promise((r) => setTimeout(r, reduceMotion ? 0 : ms));
  for (const m of messages) {
    if (run !== demoRun) return;
    const typing = document.createElement("div");
    typing.className = `msg ${m.sender} typing`;
    typing.innerHTML = "<i></i><i></i><i></i>";
    chat.appendChild(typing);
    chat.scrollTop = chat.scrollHeight;
    await wait(m.sender === "customer" ? 900 : 1300);
    if (run !== demoRun) return;
    typing.className = `msg ${m.sender}`;
    typing.innerHTML = `<span class="who">${WHO[m.sender] || ""}</span>${esc(m.text)}`;
    chat.scrollTop = chat.scrollHeight;
    await wait(700);
  }
}

// Show a saved plan from ?id=
const id = params.get("id");
if (id) {
  form.hidden = true;
  loading.hidden = false;
  loadingText.textContent = "Loading your plan";
  fetch(`${ENGINE}/api/proposals/${encodeURIComponent(id)}`)
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error("We could not find this plan. Build a new one below."))))
    .then((p) => {
      loading.hidden = true;
      render(p);
    })
    .catch((err) => {
      loading.hidden = true;
      form.hidden = false;
      note.textContent = err.message;
    });
}

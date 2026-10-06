// Page UI shared by every page: nav, reveal animations, counters, card tilt,
// portfolio filter and the WhatsApp contact form. 3D scenes live in engine.js.
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const nav = document.querySelector(".nav");
const toggle = document.querySelector(".nav-toggle");
const onScroll = () => nav.classList.toggle("scrolled", window.scrollY > 30);
window.addEventListener("scroll", onScroll, { passive: true });
onScroll();
toggle.addEventListener("click", () => {
  const open = nav.classList.toggle("open");
  toggle.setAttribute("aria-expanded", String(open));
});

const year = document.getElementById("year");
if (year) year.textContent = new Date().getFullYear();

// Scroll reveal + stat counters
const counted = new WeakSet();
function runCounter(el) {
  if (counted.has(el)) return;
  counted.add(el);
  const target = Number(el.dataset.count);
  const suffix = el.dataset.suffix || "";
  const start = performance.now();
  const dur = reduceMotion ? 0 : 1400;
  (function tick(now) {
    const t = dur ? Math.min((now - start) / dur, 1) : 1;
    el.textContent = Math.round(target * (1 - Math.pow(1 - t, 3))) + suffix;
    if (t < 1) requestAnimationFrame(tick);
  })(start);
}
const io = new IntersectionObserver(
  (entries) => {
    entries.forEach((e) => {
      if (!e.isIntersecting) return;
      e.target.classList.add("in");
      e.target.querySelectorAll("[data-count]").forEach(runCounter);
      io.unobserve(e.target);
    });
  },
  { threshold: 0.12 }
);
document.querySelectorAll(".reveal").forEach((el) => io.observe(el));

// 3D tilt on service cards
if (!reduceMotion && window.matchMedia("(hover: hover)").matches) {
  document.querySelectorAll(".tilt").forEach((card) => {
    card.addEventListener("mousemove", (e) => {
      const r = card.getBoundingClientRect();
      const x = (e.clientX - r.left) / r.width - 0.5;
      const y = (e.clientY - r.top) / r.height - 0.5;
      card.style.transform = `rotateY(${x * 12}deg) rotateX(${-y * 12}deg)`;
    });
    card.addEventListener("mouseleave", () => (card.style.transform = ""));
  });
}

// Portfolio filter
const chips = document.querySelectorAll(".chip");
chips.forEach((chip) =>
  chip.addEventListener("click", () => {
    chips.forEach((c) => c.classList.toggle("active", c === chip));
    const f = chip.dataset.filter;
    document.querySelectorAll(".work").forEach((w) => {
      const show = f === "all" || w.dataset.cat === f;
      w.classList.toggle("hidden", !show);
      if (show) w.classList.add("in");
    });
  })
);

// Contact form: opens WhatsApp with the enquiry pre-filled
const WHATSAPP_NUMBER = "918930522312";
const form = document.getElementById("contact-form");
if (form) {
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const d = new FormData(form);
    const text = [
      "Hi AXIA, I would like a free process audit.",
      `Name: ${d.get("name")}`,
      d.get("company") ? `Company: ${d.get("company")}` : "",
      `Phone: ${d.get("phone")}`,
      `Department: ${d.get("dept")}`,
    ]
      .filter(Boolean)
      .join("\n");
    window.open(`https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(text)}`, "_blank", "noopener");
    document.getElementById("form-note").textContent = `Thanks ${d.get("name")}! WhatsApp is opening with your details. Just press send.`;
    form.reset();
  });
}

import * as THREE from "./vendor/three.module.min.js";

const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/* ---------- Page UI ---------- */
const nav = document.querySelector(".nav");
const toggle = document.querySelector(".nav-toggle");
window.addEventListener("scroll", () => nav.classList.toggle("scrolled", window.scrollY > 30), { passive: true });
toggle.addEventListener("click", () => {
  const open = nav.classList.toggle("open");
  toggle.setAttribute("aria-expanded", String(open));
});
document.querySelectorAll(".nav-links a").forEach((a) => a.addEventListener("click", () => nav.classList.remove("open")));

document.getElementById("year").textContent = new Date().getFullYear();

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
      card.style.transform = `rotateY(${x * 14}deg) rotateX(${-y * 14}deg) translateZ(0)`;
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
document.getElementById("contact-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const d = new FormData(e.target);
  const text = [
    "Hi AXIA, I would like a free process audit.",
    `Name: ${d.get("name")}`,
    d.get("company") ? `Company: ${d.get("company")}` : "",
    `Phone: ${d.get("phone")}`,
    `Department: ${d.get("dept")}`,
  ].filter(Boolean).join("\n");
  window.open(`https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(text)}`, "_blank", "noopener");
  document.getElementById("form-note").textContent = `Thanks ${d.get("name")}! WhatsApp is opening with your details. Just press send.`;
  e.target.reset();
});

/* ---------- 3D helpers ---------- */
function webglAvailable() {
  try {
    const c = document.createElement("canvas");
    return !!(window.WebGLRenderingContext && (c.getContext("webgl2") || c.getContext("webgl")));
  } catch {
    return false;
  }
}

function glowTexture() {
  const s = 128;
  const c = document.createElement("canvas");
  c.width = c.height = s;
  const g = c.getContext("2d");
  const grad = g.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2);
  grad.addColorStop(0, "rgba(255,255,255,1)");
  grad.addColorStop(0.25, "rgba(255,255,255,0.6)");
  grad.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = grad;
  g.fillRect(0, 0, s, s);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

function makeRenderer(canvas) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  return renderer;
}

function fit(renderer, camera, canvas) {
  const w = canvas.clientWidth;
  const h = canvas.clientHeight;
  if (canvas.width !== Math.floor(w * renderer.getPixelRatio()) || canvas.height !== Math.floor(h * renderer.getPixelRatio())) {
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
}

// Run a render loop only while the canvas is on screen.
function loopWhenVisible(canvas, frame) {
  let visible = true;
  new IntersectionObserver(([e]) => (visible = e.isIntersecting)).observe(canvas);
  const clock = new THREE.Clock();
  (function tick() {
    requestAnimationFrame(tick);
    if (visible) frame(clock.getElapsedTime());
  })();
}

/* ---------- Hero scene: the AXIA core with five department nodes ---------- */
function heroScene() {
  const canvas = document.getElementById("hero-canvas");
  const renderer = makeRenderer(canvas);
  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x070a1a, 0.045);
  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
  camera.position.set(0, 0, 14);

  const glow = glowTexture();
  const world = new THREE.Group();
  scene.add(world);

  // Core: layered icosahedron
  const core = new THREE.Group();
  world.add(core);
  const coreSolid = new THREE.Mesh(
    new THREE.IcosahedronGeometry(1.35, 1),
    new THREE.MeshStandardMaterial({ color: 0x3a2fa0, emissive: 0x4a2bff, emissiveIntensity: 0.55, metalness: 0.5, roughness: 0.2, flatShading: true })
  );
  core.add(coreSolid);
  const coreWire = new THREE.LineSegments(
    new THREE.WireframeGeometry(new THREE.IcosahedronGeometry(2.1, 1)),
    new THREE.LineBasicMaterial({ color: 0x8f7bff, transparent: true, opacity: 0.45 })
  );
  core.add(coreWire);
  const outerWire = new THREE.LineSegments(
    new THREE.EdgesGeometry(new THREE.DodecahedronGeometry(2.8)),
    new THREE.LineBasicMaterial({ color: 0x2ee6d6, transparent: true, opacity: 0.25 })
  );
  core.add(outerWire);
  const coreGlow = new THREE.Sprite(new THREE.SpriteMaterial({ map: glow, color: 0x7b5cff, transparent: true, opacity: 0.9, blending: THREE.AdditiveBlending, depthWrite: false }));
  coreGlow.scale.set(9, 9, 1);
  core.add(coreGlow);

  scene.add(new THREE.AmbientLight(0x6670ff, 0.5));
  const key = new THREE.PointLight(0xff8a3d, 260, 40);
  key.position.set(5, 4, 6);
  scene.add(key);
  const rim = new THREE.PointLight(0x2ee6d6, 220, 40);
  rim.position.set(-6, -3, 3);
  scene.add(rim);

  // Five department nodes on tilted orbits
  const depts = [0xff8a3d, 0x7b5cff, 0x2ee6d6, 0xff5c8a, 0x5cff9d];
  const nodes = depts.map((color, i) => {
    const radius = 4.2 + (i % 2) * 0.9;
    const tilt = new THREE.Euler((i * 0.7) - 1.2, i * 1.25, (i - 2) * 0.35);
    const orbit = new THREE.Group();
    orbit.rotation.copy(tilt);
    world.add(orbit);

    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(radius, 0.008, 6, 160),
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.28 })
    );
    ring.rotation.x = Math.PI / 2;
    orbit.add(ring);

    const node = new THREE.Group();
    const body = new THREE.Mesh(
      new THREE.OctahedronGeometry(0.32, 0),
      new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0.8, metalness: 0.4, roughness: 0.3, flatShading: true })
    );
    node.add(body);
    const halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: glow, color, transparent: true, opacity: 0.85, blending: THREE.AdditiveBlending, depthWrite: false }));
    halo.scale.set(2, 2, 1);
    node.add(halo);
    orbit.add(node);

    // Connection line from core to node, plus a pulse that travels along it
    const lineGeo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]);
    const line = new THREE.Line(lineGeo, new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.35 }));
    world.add(line);
    const pulse = new THREE.Sprite(new THREE.SpriteMaterial({ map: glow, color, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
    pulse.scale.set(0.7, 0.7, 1);
    world.add(pulse);

    return { orbit, node, body, radius, line, pulse, speed: 0.18 + i * 0.035, phase: i * 1.3 };
  });

  // Starfield / data particles
  const count = 1400;
  const pos = new Float32Array(count * 3);
  const col = new Float32Array(count * 3);
  const palette = [new THREE.Color(0x7b5cff), new THREE.Color(0x2ee6d6), new THREE.Color(0xff8a3d), new THREE.Color(0xffffff)];
  for (let i = 0; i < count; i++) {
    const r = 8 + Math.random() * 22;
    const th = Math.random() * Math.PI * 2;
    const ph = Math.acos(2 * Math.random() - 1);
    pos.set([r * Math.sin(ph) * Math.cos(th), r * Math.sin(ph) * Math.sin(th), r * Math.cos(ph)], i * 3);
    const c = palette[i % palette.length];
    col.set([c.r, c.g, c.b], i * 3);
  }
  const pGeo = new THREE.BufferGeometry();
  pGeo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  pGeo.setAttribute("color", new THREE.BufferAttribute(col, 3));
  const particles = new THREE.Points(pGeo, new THREE.PointsMaterial({ size: 0.12, map: glow, vertexColors: true, transparent: true, opacity: 0.8, blending: THREE.AdditiveBlending, depthWrite: false }));
  scene.add(particles);

  // Mouse parallax
  const mouse = { x: 0, y: 0 };
  window.addEventListener("pointermove", (e) => {
    mouse.x = e.clientX / window.innerWidth - 0.5;
    mouse.y = e.clientY / window.innerHeight - 0.5;
  });

  const tmp = new THREE.Vector3();
  const speed = reduceMotion ? 0 : 1;

  loopWhenVisible(canvas, (t) => {
    fit(renderer, camera, canvas);
    const wide = camera.aspect > 1.1;
    world.position.x = wide ? 4.2 : 0;
    world.position.y = wide ? 0 : 2.2;
    world.scale.setScalar(wide ? 1 : 0.72);

    const s = t * speed;
    core.rotation.y = s * 0.25;
    core.rotation.x = Math.sin(s * 0.3) * 0.3;
    coreWire.rotation.y = -s * 0.4;
    outerWire.rotation.z = s * 0.15;
    coreGlow.material.opacity = 0.75 + Math.sin(s * 2) * 0.15;

    nodes.forEach((n) => {
      const a = n.phase + s * n.speed;
      n.node.position.set(Math.cos(a) * n.radius, 0, Math.sin(a) * n.radius);
      n.body.rotation.x = s * 1.2;
      n.body.rotation.y = s * 0.9;
      n.node.getWorldPosition(tmp);
      world.worldToLocal(tmp);
      const p = n.line.geometry.attributes.position;
      p.setXYZ(1, tmp.x, tmp.y, tmp.z);
      p.needsUpdate = true;
      const k = (s * 0.6 + n.phase) % 1;
      n.pulse.position.copy(tmp).multiplyScalar(k);
      n.pulse.material.opacity = Math.sin(k * Math.PI);
    });

    particles.rotation.y = s * 0.02;
    particles.rotation.x = s * 0.01;

    camera.position.x += (mouse.x * 2.5 - camera.position.x) * 0.04;
    camera.position.y += (-mouse.y * 1.8 - camera.position.y) * 0.04;
    camera.lookAt(world.position.x * 0.5, world.position.y * 0.5, 0);

    renderer.render(scene, camera);
  });
}

/* ---------- Contact scene: flowing torus knot ---------- */
function ctaScene() {
  const canvas = document.getElementById("cta-canvas");
  const renderer = makeRenderer(canvas);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
  camera.position.set(0, 0, 12);

  const glow = glowTexture();
  const group = new THREE.Group();
  scene.add(group);

  const knotGeo = new THREE.TorusKnotGeometry(3, 0.9, 260, 24, 2, 3);
  const wire = new THREE.LineSegments(
    new THREE.WireframeGeometry(knotGeo),
    new THREE.LineBasicMaterial({ color: 0x7b5cff, transparent: true, opacity: 0.07 })
  );
  group.add(wire);

  const pts = knotGeo.attributes.position;
  const colors = new Float32Array(pts.count * 3);
  const a = new THREE.Color(0xff8a3d);
  const b = new THREE.Color(0x2ee6d6);
  for (let i = 0; i < pts.count; i++) {
    const c = a.clone().lerp(b, (i / pts.count) % 1);
    colors.set([c.r, c.g, c.b], i * 3);
  }
  const dotGeo = new THREE.BufferGeometry();
  dotGeo.setAttribute("position", pts);
  dotGeo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
  const dots = new THREE.Points(dotGeo, new THREE.PointsMaterial({ size: 0.12, map: glow, vertexColors: true, transparent: true, opacity: 0.55, blending: THREE.AdditiveBlending, depthWrite: false }));
  group.add(dots);

  const speed = reduceMotion ? 0 : 1;
  loopWhenVisible(canvas, (t) => {
    fit(renderer, camera, canvas);
    const wide = camera.aspect > 1.1;
    group.position.x = wide ? -6 : 0;
    group.position.y = wide ? 0 : 3;
    group.scale.setScalar(wide ? 1 : 0.7);
    group.rotation.x = t * speed * 0.12;
    group.rotation.y = t * speed * 0.18;
    renderer.render(scene, camera);
  });
}

if (webglAvailable()) {
  heroScene();
  ctaScene();
} else {
  document.body.classList.add("no-webgl");
}

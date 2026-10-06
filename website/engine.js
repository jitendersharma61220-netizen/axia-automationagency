// AXIA automation engine: a 3D workflow of inputs -> processing stages -> outputs,
// with data packets flowing through pipes. Each <canvas data-engine> on a page
// gets its own scene, configured by the JSON in its data-flow attribute.
import * as THREE from "./vendor/three.module.min.js";

const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const DEFAULT_FLOW = {
  inputs: ["WhatsApp", "Email", "Forms & sheets"],
  stages: ["Capture", "Understand", "Check rules", "You approve", "Act"],
  approval: 3,
  outputs: ["CRM", "Tally", "Calendar"],
  color: "#7b5cff",
  accent: "#2ee6d6",
};

function glowTexture() {
  const s = 128;
  const c = document.createElement("canvas");
  c.width = c.height = s;
  const g = c.getContext("2d");
  const grad = g.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2);
  grad.addColorStop(0, "rgba(255,255,255,1)");
  grad.addColorStop(0.3, "rgba(255,255,255,0.5)");
  grad.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = grad;
  g.fillRect(0, 0, s, s);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

let labelBoost = 1;

function label(text, color, opts = {}) {
  const font = "600 44px 'Space Grotesk', system-ui, sans-serif";
  const c = document.createElement("canvas");
  const g = c.getContext("2d");
  g.font = font;
  const padX = 34;
  const w = Math.ceil(g.measureText(text).width) + padX * 2;
  const h = 86;
  c.width = w;
  c.height = h;
  g.font = font;
  g.fillStyle = "rgba(9,12,32,0.82)";
  g.strokeStyle = color;
  g.lineWidth = 3;
  const r = h / 2 - 2;
  g.beginPath();
  g.roundRect(2, 2, w - 4, h - 4, r);
  g.fill();
  g.stroke();
  g.fillStyle = opts.textColor || "#eef0ff";
  g.textBaseline = "middle";
  g.fillText(text, padX, h / 2 + 2);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false }));
  const scale = (opts.scale || 0.0105) * labelBoost;
  sprite.scale.set(w * scale, h * scale, 1);
  sprite.renderOrder = 10;
  return sprite;
}

function gearGeometry(teeth = 10, rOuter = 0.42, rInner = 0.33, hole = 0.12, depth = 0.1) {
  const shape = new THREE.Shape();
  const steps = teeth * 4;
  for (let i = 0; i <= steps; i++) {
    const a = (i / steps) * Math.PI * 2;
    const r = i % 4 < 2 ? rOuter : rInner;
    const x = Math.cos(a) * r;
    const y = Math.sin(a) * r;
    if (i === 0) shape.moveTo(x, y);
    else shape.lineTo(x, y);
  }
  const h = new THREE.Path();
  h.absarc(0, 0, hole, 0, Math.PI * 2, true);
  shape.holes.push(h);
  const geo = new THREE.ExtrudeGeometry(shape, { depth, bevelEnabled: false });
  geo.center();
  return geo;
}

function buildScene(canvas) {
  let flow = DEFAULT_FLOW;
  try {
    if (canvas.dataset.flow) flow = { ...DEFAULT_FLOW, ...JSON.parse(canvas.dataset.flow) };
  } catch {}
  const mode = canvas.dataset.engine || "flat"; // "hero" = angled background, "flat" = three-quarter view
  labelBoost = canvas.clientWidth < 600 ? 1.5 : 1;

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  const scene = new THREE.Scene();
  scene.fog = new THREE.Fog(0x070a1a, 18, 42);
  const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 100);

  const glow = glowTexture();
  const main = new THREE.Color(flow.color);
  const accent = new THREE.Color(flow.accent);
  const approveColor = new THREE.Color("#ff8a3d");
  const world = new THREE.Group();
  scene.add(world);

  scene.add(new THREE.AmbientLight(0x8890ff, 0.6));
  const l1 = new THREE.PointLight(main, 120, 40);
  l1.position.set(-4, 6, 6);
  scene.add(l1);
  const l2 = new THREE.PointLight(accent, 120, 40);
  l2.position.set(6, 3, 6);
  scene.add(l2);

  // Floor grid
  const grid = new THREE.GridHelper(60, 60, main, 0x1b2150);
  grid.position.y = -2.2;
  grid.material.transparent = true;
  grid.material.opacity = 0.35;
  world.add(grid);

  const nStages = flow.stages.length;
  const span = 3.4;
  const stageX = (i) => (i - (nStages - 1) / 2) * span;
  const inX = stageX(0) - span * 1.35;
  const outX = stageX(nStages - 1) + span * 1.35;
  const colY = (i, n) => (i - (n - 1) / 2) * 1.55;

  const animated = [];

  // Processing stages: glass blocks with a turning gear inside
  const stagePos = [];
  flow.stages.forEach((name, i) => {
    const isApproval = i === flow.approval;
    const color = isApproval ? approveColor : main.clone().lerp(accent, i / Math.max(1, nStages - 1));
    const g = new THREE.Group();
    g.position.set(stageX(i), 0, 0);
    world.add(g);
    stagePos.push(g.position.clone());

    const box = new THREE.Mesh(
      new THREE.BoxGeometry(1.5, 1.5, 1.5),
      new THREE.MeshPhysicalMaterial({ color: 0x141a44, metalness: 0.2, roughness: 0.15, transparent: true, opacity: 0.55, transmission: 0.3, emissive: color, emissiveIntensity: 0.08 })
    );
    g.add(box);
    const edges = new THREE.LineSegments(new THREE.EdgesGeometry(box.geometry), new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.9 }));
    g.add(edges);

    let core;
    if (isApproval) {
      // Human approval stage: a ring with a tick
      core = new THREE.Group();
      core.add(new THREE.Mesh(new THREE.TorusGeometry(0.4, 0.07, 12, 48), new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0.9 })));
      const tick = new THREE.Shape();
      tick.moveTo(-0.2, 0).lineTo(-0.05, -0.16).lineTo(0.22, 0.16).lineTo(0.17, 0.2).lineTo(-0.05, -0.06).lineTo(-0.15, 0.04);
      const tickMesh = new THREE.Mesh(new THREE.ExtrudeGeometry(tick, { depth: 0.06, bevelEnabled: false }), new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: color, emissiveIntensity: 0.6 }));
      tickMesh.position.z = -0.03;
      core.add(tickMesh);
    } else {
      core = new THREE.Mesh(gearGeometry(10 + i * 2), new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0.55, metalness: 0.6, roughness: 0.3 }));
    }
    g.add(core);

    const halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: glow, color, transparent: true, opacity: 0.35, blending: THREE.AdditiveBlending, depthWrite: false }));
    halo.scale.set(3.4, 3.4, 1);
    g.add(halo);

    const lbl = label(`${String(i + 1).padStart(2, "0")}  ${name}`, `#${color.getHexString()}`);
    lbl.position.set(0, i % 2 ? -1.4 : 1.4, 0);
    g.add(lbl);

    animated.push({ core, edges, halo, isApproval, phase: i * 0.9 });
  });

  // Input and output terminals
  function terminal(name, x, y, color, side) {
    const g = new THREE.Group();
    g.position.set(x, y, 0);
    world.add(g);
    const disc = new THREE.Mesh(new THREE.CylinderGeometry(0.32, 0.32, 0.14, 32), new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0.7, metalness: 0.5, roughness: 0.3 }));
    disc.rotation.z = Math.PI / 2;
    g.add(disc);
    const ring = new THREE.Mesh(new THREE.TorusGeometry(0.5, 0.02, 8, 48), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.6 }));
    ring.rotation.y = Math.PI / 2;
    g.add(ring);
    const halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: glow, color, transparent: true, opacity: 0.5, blending: THREE.AdditiveBlending, depthWrite: false }));
    halo.scale.set(1.8, 1.8, 1);
    g.add(halo);
    const lbl = label(name, `#${color.getHexString()}`, { scale: 0.0085 });
    const lw = lbl.scale.x;
    lbl.position.set(side * (lw / 2 + 0.7), 0, 0);
    g.add(lbl);
    animated.push({ ring, phase: y });
    return g.position.clone();
  }
  const inPos = flow.inputs.map((n, i) => terminal(n, inX, colY(i, flow.inputs.length), accent, -1));
  const outPos = flow.outputs.map((n, i) => terminal(n, outX, colY(i, flow.outputs.length), main.clone().lerp(accent, 0.5), 1));

  // Pipes between everything, with packets flowing along them
  const pipes = [];
  function pipe(a, b, color, lift = 0.5, packets = 3, speed = 0.22) {
    const mid = a.clone().lerp(b, 0.5);
    mid.y += lift;
    mid.z += 0.4;
    const curve = new THREE.QuadraticBezierCurve3(a, mid, b);
    const tube = new THREE.Mesh(new THREE.TubeGeometry(curve, 40, 0.035, 8, false), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.45 }));
    world.add(tube);
    const list = [];
    for (let k = 0; k < packets; k++) {
      const pk = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.16, 0.16), new THREE.MeshBasicMaterial({ color: 0xffffff }));
      const glowS = new THREE.Sprite(new THREE.SpriteMaterial({ map: glow, color, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
      glowS.scale.set(0.8, 0.8, 1);
      pk.add(glowS);
      world.add(pk);
      list.push({ mesh: pk, offset: k / packets + Math.random() * 0.1 });
    }
    pipes.push({ curve, list, speed: speed * (0.85 + Math.random() * 0.3) });
  }
  const edgeOffset = new THREE.Vector3(0.78, 0, 0);
  inPos.forEach((p) => pipe(p.clone().add(new THREE.Vector3(0.35, 0, 0)), stagePos[0].clone().sub(edgeOffset), accent, 0.2, 2));
  for (let i = 0; i < nStages - 1; i++) {
    const c = i + 1 === flow.approval || i === flow.approval ? approveColor : main.clone().lerp(accent, i / Math.max(1, nStages - 1));
    pipe(stagePos[i].clone().add(edgeOffset), stagePos[i + 1].clone().sub(edgeOffset), c, 0.45, 3, 0.3);
  }
  outPos.forEach((p) => pipe(stagePos[nStages - 1].clone().add(edgeOffset), p.clone().sub(new THREE.Vector3(0.35, 0, 0)), main.clone().lerp(accent, 0.5), 0.2, 2));

  // Floating data dust
  const dustN = 500;
  const dp = new Float32Array(dustN * 3);
  for (let i = 0; i < dustN; i++) dp.set([(Math.random() - 0.5) * 50, Math.random() * 14 - 3, (Math.random() - 0.5) * 30 - 6], i * 3);
  const dg = new THREE.BufferGeometry();
  dg.setAttribute("position", new THREE.BufferAttribute(dp, 3));
  const dust = new THREE.Points(dg, new THREE.PointsMaterial({ size: 0.09, map: glow, color: accent, transparent: true, opacity: 0.55, blending: THREE.AdditiveBlending, depthWrite: false }));
  scene.add(dust);

  // Layout extent for camera fitting (labels included, floor grid excluded)
  world.remove(grid);
  world.updateMatrixWorld(true);
  const bounds = new THREE.Box3().setFromObject(world);
  world.add(grid);
  const halfWidth = Math.max(Math.abs(bounds.min.x), Math.abs(bounds.max.x)) + 0.4;

  const mouse = { x: 0, y: 0 };
  window.addEventListener("pointermove", (e) => {
    mouse.x = e.clientX / window.innerWidth - 0.5;
    mouse.y = e.clientY / window.innerHeight - 0.5;
  });

  function fit() {
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    if (!w || !h) return;
    const pr = renderer.getPixelRatio();
    if (canvas.width !== Math.floor(w * pr) || canvas.height !== Math.floor(h * pr)) {
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    }
  }

  let visible = true;
  new IntersectionObserver(([e]) => (visible = e.isIntersecting)).observe(canvas);
  const clock = new THREE.Clock();
  const tmp = new THREE.Vector3();

  function frame() {
    requestAnimationFrame(frame);
    if (!visible) return;
    fit();
    const t = reduceMotion ? 2 : clock.getElapsedTime();
    const vFov = THREE.MathUtils.degToRad(camera.fov);
    const wide = camera.aspect > 1.1;
    let dist;

    if (mode === "hero" && wide && canvas.clientWidth > 760) {
      // Render as if the canvas were wider, so the engine sits in the right part
      // of the hero, behind and beside the headline.
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      const virtualW = w * 1.42;
      camera.setViewOffset(virtualW, h, 0, 0, w, h);
      world.rotation.y = -0.38 + Math.sin(t * 0.15) * 0.03;
      world.position.set(0, -0.6, 0);
      dist = (halfWidth * 1.45) / Math.tan(vFov / 2) / (virtualW / h);
      camera.position.set(mouse.x * 1.5, 4 - mouse.y * 1.2, dist);
      camera.lookAt(0, 0, 0);
    } else {
      // Front view sized so the whole pipeline fits the canvas width
      camera.clearViewOffset();
      // Three-quarter view: the pipeline runs diagonally, so it fills more of the frame
      const narrow = camera.aspect < 1.3;
      world.rotation.y = (narrow ? -0.72 : -0.4) + Math.sin(t * 0.2) * 0.04;
      world.position.set(0, 0, 0);
      dist = (halfWidth * (narrow ? 0.8 : 0.98)) / Math.tan(vFov / 2) / camera.aspect;
      camera.position.set(1.2 + mouse.x * 1.2, dist * 0.36 - mouse.y * 0.8, dist);
      camera.lookAt(1.2, 0.2, 0);
    }

    scene.fog.near = dist * 0.85;
    scene.fog.far = dist * 2.4;

    animated.forEach((a) => {
      if (a.core) {
        if (a.isApproval) a.core.rotation.y = Math.sin(t * 1.5 + a.phase) * 0.6;
        else a.core.rotation.z = t * (0.8 + a.phase * 0.1) * (a.phase % 2 ? -1 : 1);
        const pulse = 0.5 + 0.5 * Math.sin(t * 2.4 - a.phase * 1.3);
        a.edges.material.opacity = 0.45 + pulse * 0.55;
        a.halo.material.opacity = 0.18 + pulse * 0.3;
      }
      if (a.ring) a.ring.scale.setScalar(1 + 0.12 * Math.sin(t * 3 + a.phase));
    });

    pipes.forEach((p) => {
      p.list.forEach((pk) => {
        const k = (t * p.speed + pk.offset) % 1;
        p.curve.getPointAt(k, tmp);
        pk.mesh.position.copy(tmp);
        pk.mesh.rotation.set(t * 2, t * 1.5, 0);
        const s = Math.sin(k * Math.PI);
        pk.mesh.scale.setScalar(0.4 + s * 0.8);
      });
    });

    dust.rotation.y = t * 0.01;
    renderer.render(scene, camera);
  }
  frame();
}

function webglAvailable() {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    return false;
  }
}

if (webglAvailable()) {
  document.querySelectorAll("canvas[data-engine]").forEach(buildScene);
} else {
  document.body.classList.add("no-webgl");
}

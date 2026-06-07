// Renderer: a transparent Three.js scene with a low-poly PLACEHOLDER figure in
// a peacock palette (deep indigo, teal, gold). Idle bob + slow rotate.
//
// Click-through coordination: the window ignores mouse events by default, but
// {forward:true} still delivers mousemove here. We raycast the figure and, when
// the cursor is over it, ask main to stop ignoring so the figure can be dragged
// (window reposition) and clicked (a little reaction).

const THREE = require('three');
const { ipcRenderer } = require('electron');

// --- palette ----------------------------------------------------------------
const INDIGO = 0x312e81;
const INDIGO_DEEP = 0x1e1b4b;
const TEAL = 0x14b8a6;
const GOLD = 0xf5b301;

const canvas = document.getElementById('scene');

const renderer = new THREE.WebGLRenderer({
  canvas,
  alpha: true, // transparent background
  antialias: true,
});
renderer.setClearColor(0x000000, 0); // fully transparent
renderer.setPixelRatio(window.devicePixelRatio || 1);
renderer.setSize(window.innerWidth, window.innerHeight, false);

const scene = new THREE.Scene();

const camera = new THREE.PerspectiveCamera(
  42,
  window.innerWidth / window.innerHeight,
  0.1,
  100,
);
camera.position.set(0, 0.4, 4.2);
camera.lookAt(0, 0.3, 0);

// --- lighting (flat-shaded low-poly look) -----------------------------------
scene.add(new THREE.AmbientLight(0xffffff, 0.55));
const key = new THREE.DirectionalLight(0xfff4d6, 1.1);
key.position.set(2, 3, 2);
scene.add(key);
const rim = new THREE.DirectionalLight(0x66e0ff, 0.5);
rim.position.set(-2, 1, -1.5);
scene.add(rim);

function poly(color, opts = {}) {
  return new THREE.MeshStandardMaterial({
    color,
    flatShading: true,
    roughness: 0.45,
    metalness: 0.25,
    ...opts,
  });
}

// --- the placeholder figure -------------------------------------------------
// A stylized floating figure: tapered cloak/body, a faceted head, a gold halo
// crown, and two small floating "hand" orbs. All basic geometry — no model file.
const pet = new THREE.Group();

// Body — a low-poly tapered cloak (6-sided cone).
const body = new THREE.Mesh(new THREE.ConeGeometry(0.62, 1.5, 6), poly(INDIGO));
body.position.y = -0.25;
pet.add(body);

// A second, smaller cone as a layered collar/shawl in deep indigo.
const collar = new THREE.Mesh(new THREE.ConeGeometry(0.5, 0.55, 6), poly(INDIGO_DEEP));
collar.position.y = 0.32;
pet.add(collar);

// Head — faceted teal icosahedron.
const head = new THREE.Mesh(new THREE.IcosahedronGeometry(0.42, 0), poly(TEAL));
head.position.y = 0.95;
pet.add(head);

// Gold halo crown above the head.
const halo = new THREE.Mesh(
  new THREE.TorusGeometry(0.46, 0.06, 6, 16),
  poly(GOLD, { metalness: 0.6, roughness: 0.3 }),
);
halo.position.y = 1.4;
halo.rotation.x = Math.PI / 2;
pet.add(halo);

// A single peacock-feather-ish gold accent (octahedron) on the chest.
const gem = new THREE.Mesh(new THREE.OctahedronGeometry(0.16, 0), poly(GOLD, { metalness: 0.7 }));
gem.position.set(0, 0.45, 0.42);
pet.add(gem);

// Floating "hand" orbs.
const handGeo = new THREE.IcosahedronGeometry(0.13, 0);
const handL = new THREE.Mesh(handGeo, poly(TEAL));
handL.position.set(-0.62, 0.05, 0.15);
const handR = new THREE.Mesh(handGeo, poly(TEAL));
handR.position.set(0.62, 0.05, 0.15);
pet.add(handL, handR);

scene.add(pet);

// --- interaction state ------------------------------------------------------
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();

let ignoringMouse = true; // mirrors the window's current state (starts ignoring)
let dragging = false;
let dragMoved = 0; // accumulated cursor travel during a press (to tell drag vs click)
let lastDownScreen = null;
let clickPulse = 0; // decays after a click for a small "reaction" animation

function setIgnore(next) {
  if (next === ignoringMouse) return;
  ignoringMouse = next;
  ipcRenderer.send('set-ignore-mouse', next);
}

function pointerOverPet(clientX, clientY) {
  pointer.x = (clientX / window.innerWidth) * 2 - 1;
  pointer.y = -(clientY / window.innerHeight) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  return raycaster.intersectObject(pet, true).length > 0;
}

window.addEventListener('mousemove', (e) => {
  const over = pointerOverPet(e.clientX, e.clientY);
  if (!dragging) {
    // Capture the mouse only while hovering the figure; otherwise fall through.
    setIgnore(!over);
  } else {
    dragMoved += Math.abs(e.movementX) + Math.abs(e.movementY);
    ipcRenderer.send('drag-move', { mouseX: e.screenX, mouseY: e.screenY });
  }
});

window.addEventListener('mousedown', (e) => {
  if (e.button !== 0) return;
  if (!pointerOverPet(e.clientX, e.clientY)) return;
  dragging = true;
  dragMoved = 0;
  lastDownScreen = { x: e.screenX, y: e.screenY };
  ipcRenderer.send('drag-start', { mouseX: e.screenX, mouseY: e.screenY });
});

window.addEventListener('mouseup', () => {
  if (!dragging) return;
  dragging = false;
  ipcRenderer.send('drag-end');
  // A small travel means it was a click, not a drag -> play a reaction.
  if (dragMoved < 5) clickPulse = 1;
});

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight, false);
});

// --- animation --------------------------------------------------------------
const clock = new THREE.Clock();

function animate() {
  requestAnimationFrame(animate);
  const t = clock.getElapsedTime();

  // Gentle idle bob + slow rotate.
  pet.position.y = Math.sin(t * 1.6) * 0.08;
  pet.rotation.y += 0.006;

  // Halo and chest gem drift a touch for life.
  halo.rotation.z = t * 0.4;
  gem.rotation.y = t * 0.8;

  // Click reaction: a quick squash-and-spin that decays.
  if (clickPulse > 0) {
    clickPulse = Math.max(0, clickPulse - 0.04);
    const s = 1 + Math.sin((1 - clickPulse) * Math.PI) * 0.12;
    pet.scale.set(s, s, s);
    pet.rotation.y += clickPulse * 0.06;
  } else {
    pet.scale.set(1, 1, 1);
  }

  renderer.render(scene, camera);
}
animate();

// Signal readiness (useful when launched headless-ish for verification).
console.log('[krish-pet] renderer ready');

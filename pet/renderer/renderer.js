// Renderer: a transparent Three.js scene that shows the Krish character.
//
// On startup it tries to load assets/krishna.glb. Until that file exists (or if
// it fails to load) it falls back to a low-poly PLACEHOLDER figure in a peacock
// palette, so the pet always runs. When the GLB loads we wire up:
//   - an AnimationMixer with clips indexed by name (idle/watch/flute/sleep/...)
//   - morph-target "expressions" (blink/smile/angry/sad/surprised) with an
//     auto-blink loop
//   - a setMood() state machine mapping moods to a (clip + expression) combo
//
// Click-through: the window ignores mouse events by default; {forward:true}
// still delivers mousemove here so we can raycast the character and capture the
// mouse only while hovering it (drag = reposition window, click = a reaction).

import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

// --- palette ----------------------------------------------------------------
const INDIGO = 0x312e81;
const INDIGO_DEEP = 0x1e1b4b;
const TEAL = 0x14b8a6;
const GOLD = 0xf5b301;

// Names we look up inside the GLB. Edit these to match your exported rig.
const CLIP_NAMES = ['idle', 'watch', 'flute', 'sleep', 'cheer', 'angry'];
const EXPRESSION_NAMES = ['blink', 'smile', 'angry', 'sad', 'surprised'];

// Mood -> (animation clip + expression weights). Used by both GLB and (loosely)
// the placeholder. Order matches number keys 1-6 and the tray submenu.
const MOODS = {
  idle: { clip: 'idle', expressions: {} }, // neutral
  watching: { clip: 'watch', expressions: { smile: 0.35 } }, // slight smile
  happy: { clip: 'cheer', expressions: { smile: 1.0 } },
  flute: { clip: 'flute', expressions: { smile: 0.5 } }, // calm smile
  sleeping: { clip: 'sleep', expressions: { blink: 1.0 } }, // eyes closed
  angry: { clip: 'angry', expressions: { angry: 1.0 } },
};
const MOOD_ORDER = ['idle', 'watching', 'happy', 'flute', 'sleeping', 'angry'];

const GLB_URL = new URL('../assets/krishna.glb', import.meta.url).href;

// ---------------------------------------------------------------------------
const canvas = document.getElementById('scene');
const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
renderer.setClearColor(0x000000, 0);
renderer.setPixelRatio(window.devicePixelRatio || 1);
renderer.setSize(window.innerWidth, window.innerHeight, false);
renderer.outputColorSpace = THREE.SRGBColorSpace;

const scene = new THREE.Scene();

const camera = new THREE.PerspectiveCamera(42, window.innerWidth / window.innerHeight, 0.1, 100);
camera.position.set(0, 0.4, 4.2);
camera.lookAt(0, 0.3, 0);

scene.add(new THREE.AmbientLight(0xffffff, 0.6));
const key = new THREE.DirectionalLight(0xfff4d6, 1.1);
key.position.set(2, 3, 2);
scene.add(key);
const rim = new THREE.DirectionalLight(0x66e0ff, 0.5);
rim.position.set(-2, 1, -1.5);
scene.add(rim);

// `pet` is the container we move/scale; its contents are swapped placeholder
// -> GLB once the model loads.
const pet = new THREE.Group();
scene.add(pet);

// --- shared character state -------------------------------------------------
let isPlaceholder = true;
let mixer = null;
const actions = {}; // clipName -> THREE.AnimationAction
let currentAction = null;

// Expression name -> array of { mesh, index } across all morphing meshes.
const morphMap = {};
// Smoothly-lerped expression weights: name -> { current, target }.
const expressionState = {};
let autoBlink = true;
let currentMood = 'idle';

// placeholder visual tweaks per mood (so hotkeys do something before the GLB).
let placeholderSpin = 0.006;
let placeholderHead = null;

// --- placeholder figure -----------------------------------------------------
function poly(color, opts = {}) {
  return new THREE.MeshStandardMaterial({
    color,
    flatShading: true,
    roughness: 0.45,
    metalness: 0.25,
    ...opts,
  });
}

function buildPlaceholder() {
  const g = new THREE.Group();

  const body = new THREE.Mesh(new THREE.ConeGeometry(0.62, 1.5, 6), poly(INDIGO));
  body.position.y = -0.25;
  g.add(body);

  const collar = new THREE.Mesh(new THREE.ConeGeometry(0.5, 0.55, 6), poly(INDIGO_DEEP));
  collar.position.y = 0.32;
  g.add(collar);

  const head = new THREE.Mesh(new THREE.IcosahedronGeometry(0.42, 0), poly(TEAL));
  head.position.y = 0.95;
  g.add(head);
  placeholderHead = head;

  const halo = new THREE.Mesh(
    new THREE.TorusGeometry(0.46, 0.06, 6, 16),
    poly(GOLD, { metalness: 0.6, roughness: 0.3 }),
  );
  halo.position.y = 1.4;
  halo.rotation.x = Math.PI / 2;
  g.add(halo);

  const gem = new THREE.Mesh(new THREE.OctahedronGeometry(0.16, 0), poly(GOLD, { metalness: 0.7 }));
  gem.position.set(0, 0.45, 0.42);
  g.add(gem);

  const handGeo = new THREE.IcosahedronGeometry(0.13, 0);
  const handL = new THREE.Mesh(handGeo, poly(TEAL));
  handL.position.set(-0.62, 0.05, 0.15);
  const handR = new THREE.Mesh(handGeo, poly(TEAL));
  handR.position.set(0.62, 0.05, 0.15);
  g.add(handL, handR);

  // Noticeably smaller than the first skeleton.
  g.scale.setScalar(0.78);
  return g;
}

let placeholderGroup = buildPlaceholder();
pet.add(placeholderGroup);

// --- GLB load (with graceful fallback) --------------------------------------
function frameModel(model) {
  // Normalize size so any export reads as a small pet, and recenter on origin
  // with feet near the bottom of the view.
  const box = new THREE.Box3().setFromObject(model);
  const size = new THREE.Vector3();
  const center = new THREE.Vector3();
  box.getSize(size);
  box.getCenter(center);
  const targetHeight = 1.8; // world units; camera framing keeps this small on-screen
  const scale = size.y > 0 ? targetHeight / size.y : 1;
  model.scale.setScalar(scale);
  model.position.sub(center.multiplyScalar(scale));
  model.position.y += (size.y * scale) / 2 - 0.9; // sit a touch low
}

function indexClips(gltf) {
  mixer = new THREE.AnimationMixer(gltf.scene);
  for (const clip of gltf.animations) {
    actions[clip.name.toLowerCase()] = mixer.clipAction(clip);
  }
  // Warn about clips we expected but didn't find (helps debugging a new export).
  const missing = CLIP_NAMES.filter((n) => !actions[n]);
  if (missing.length) console.warn('[krish-pet] GLB missing clips:', missing.join(', '));
}

function indexMorphs(root) {
  root.traverse((obj) => {
    if (!obj.isMesh || !obj.morphTargetDictionary) return;
    for (const [key, index] of Object.entries(obj.morphTargetDictionary)) {
      const want = EXPRESSION_NAMES.find((n) => key.toLowerCase() === n || key.toLowerCase().includes(n));
      if (!want) continue;
      (morphMap[want] ||= []).push({ mesh: obj, index });
    }
  });
  // Initialize lerp state for whatever expressions exist.
  for (const name of EXPRESSION_NAMES) expressionState[name] = { current: 0, target: 0 };
  const found = Object.keys(morphMap);
  if (found.length) console.log('[krish-pet] expressions found:', found.join(', '));
  else console.warn('[krish-pet] no matching morph targets found');
}

function loadGLB() {
  const loader = new GLTFLoader();
  loader.load(
    GLB_URL,
    (gltf) => {
      const model = gltf.scene;
      frameModel(model);
      pet.remove(placeholderGroup);
      placeholderGroup = null;
      placeholderHead = null;
      pet.add(model);
      isPlaceholder = false;

      indexClips(gltf);
      indexMorphs(model);
      setMood('idle'); // play idle + neutral by default
      console.log('[krish-pet] GLB loaded:', GLB_URL);
    },
    undefined,
    () => {
      // Missing or unreadable file: keep the placeholder running.
      console.log('[krish-pet] no GLB yet (keeping placeholder):', GLB_URL);
    },
  );
}

// --- animation API ----------------------------------------------------------
// Crossfade to a named clip with smooth blending.
function crossfadeTo(clipName, duration = 0.4) {
  const next = actions[clipName];
  if (!next || next === currentAction) return;
  next.reset();
  next.enabled = true;
  next.setEffectiveWeight(1);
  next.play();
  if (currentAction) currentAction.crossFadeTo(next, duration, false);
  currentAction = next;
}

// Smoothly drive a morph-target expression toward `weight` (0..1).
function setExpression(name, weight) {
  if (!expressionState[name]) expressionState[name] = { current: 0, target: 0 };
  expressionState[name].target = weight;
}

function resetExpressions(except = {}) {
  for (const name of Object.keys(expressionState)) {
    if (!(name in except)) setExpression(name, 0);
  }
}

// --- mood state machine -----------------------------------------------------
function setMood(state) {
  const mood = MOODS[state];
  if (!mood) return;
  currentMood = state;

  // Sleeping holds the eyes shut, so pause the auto-blink loop for it.
  autoBlink = state !== 'sleeping';

  if (!isPlaceholder) {
    crossfadeTo(mood.clip);
    resetExpressions(mood.expressions);
    for (const [name, weight] of Object.entries(mood.expressions)) setExpression(name, weight);
  } else {
    applyPlaceholderMood(state);
  }
}

// Give the placeholder *some* visible reaction per mood so the hotkeys/tray can
// be verified before the GLB exists.
function applyPlaceholderMood(state) {
  const tint = {
    idle: TEAL,
    watching: 0x22d3ee,
    happy: GOLD,
    flute: 0x60a5fa,
    sleeping: INDIGO_DEEP,
    angry: 0xef4444,
  }[state];
  const spin = {
    idle: 0.006,
    watching: 0.01,
    happy: 0.03,
    flute: 0.012,
    sleeping: 0.0015,
    angry: 0.02,
  }[state];
  placeholderSpin = spin ?? 0.006;
  if (placeholderHead && tint != null) placeholderHead.material.color.setHex(tint);
}

// --- blink loop -------------------------------------------------------------
function scheduleBlink() {
  const delay = 2200 + Math.random() * 2800;
  setTimeout(() => {
    if (autoBlink && morphMap.blink) {
      setExpression('blink', 1);
      setTimeout(() => {
        if (autoBlink) setExpression('blink', 0);
      }, 110);
    }
    scheduleBlink();
  }, delay);
}
scheduleBlink();

// --- interaction (hover capture, drag, click) -------------------------------
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
let ignoringMouse = true;
let dragging = false;
let dragMoved = 0;
let clickPulse = 0;

function setIgnore(next) {
  if (next === ignoringMouse) return;
  ignoringMouse = next;
  window.petAPI?.setIgnoreMouse(next);
}

function pointerOverPet(clientX, clientY) {
  pointer.x = (clientX / window.innerWidth) * 2 - 1;
  pointer.y = -(clientY / window.innerHeight) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  return raycaster.intersectObject(pet, true).length > 0;
}

window.addEventListener('mousemove', (e) => {
  if (!dragging) {
    setIgnore(!pointerOverPet(e.clientX, e.clientY));
  } else {
    dragMoved += Math.abs(e.movementX) + Math.abs(e.movementY);
    window.petAPI?.dragMove(e.screenX, e.screenY);
  }
});

window.addEventListener('mousedown', (e) => {
  if (e.button !== 0 || !pointerOverPet(e.clientX, e.clientY)) return;
  dragging = true;
  dragMoved = 0;
  window.petAPI?.dragStart(e.screenX, e.screenY);
});

window.addEventListener('mouseup', () => {
  if (!dragging) return;
  dragging = false;
  window.petAPI?.dragEnd();
  if (dragMoved < 5) clickPulse = 1; // a click, not a drag -> reaction
});

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight, false);
});

// Number keys 1-6 trigger moods for manual testing.
window.addEventListener('keydown', (e) => {
  const idx = parseInt(e.key, 10) - 1;
  if (idx >= 0 && idx < MOOD_ORDER.length) setMood(MOOD_ORDER[idx]);
});

// Moods pushed from the tray submenu.
window.petAPI?.onMood((mood) => setMood(mood));

// --- main loop --------------------------------------------------------------
const clock = new THREE.Clock();

function animate() {
  requestAnimationFrame(animate);
  const dt = clock.getDelta();
  const t = clock.elapsedTime;

  if (mixer) mixer.update(dt);

  // Smoothly apply expression weights to all matching morph targets.
  const lerp = Math.min(1, dt * 10);
  for (const name of Object.keys(expressionState)) {
    const s = expressionState[name];
    s.current += (s.target - s.current) * lerp;
    const targets = morphMap[name];
    if (targets) for (const { mesh, index } of targets) mesh.morphTargetInfluences[index] = s.current;
  }

  // Gentle idle bob for both placeholder and GLB.
  pet.position.y = Math.sin(t * 1.6) * 0.06;

  // The placeholder has no clips, so spin it (speed varies by mood).
  if (isPlaceholder) pet.rotation.y += placeholderSpin;

  // Click reaction: quick squash-and-spin that decays.
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

// Kick off the GLB load attempt (falls back to the placeholder on failure).
loadGLB();

console.log('[krish-pet] renderer ready');

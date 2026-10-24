"use strict";

const $ = (sel) => document.querySelector(sel);
const ENGINE_KEY = "formbondhu.engine";
const LANG_KEY = "formbondhu.lang";
const STEP_ORDER = ["read", "match", "audit", "verify", "explain", "draft"];
const STEP_TEXT = {
  read: ["ফর্ম পড়া", "Read the document"],
  match: ["নিয়মের কার্ড মেলানো", "Match the rule card"],
  audit: ["প্রতিটি নিয়ম যাচাই", "Check every rule"],
  verify: ["প্রতিটি সমস্যা আবার দেখা", "Double-check each problem"],
  explain: ["সমাধান লেখা", "Write the fixes"],
  draft: ["সংশোধিত দরখাস্ত লেখা", "Draft the corrected letter"],
};
const ENGINE_TEXT = {
  aistudio: ["Gemma 4 চলছে Google AI Studio-তে (open-weights model, hosted free API)", "Gemma 4 is running on Google AI Studio (open-weights model, hosted free API)"],
  ollama: ["Gemma 4 চলছে আপনার নিজের কম্পিউটারে, Ollama দিয়ে", "Gemma 4 is running on your own computer through Ollama"],
};
const VERDICT = {
  problems: { cls: "bad", bn: (n) => `${bnDigits(n)}টি কারণে ফেরত আসবে`, en: (n) => `Will be returned: ${n} problem${n === 1 ? "" : "s"}` },
  check_manually: { cls: "warn", bn: () => "নিজে একবার দেখুন", en: () => "Check these yourself" },
  ready: { cls: "good", bn: () => "জমা দেওয়ার জন্য প্রস্তুত", en: () => "Ready to submit" },
  unknown_form: { cls: "unknown", bn: () => "অচেনা ফর্ম", en: () => "Unknown document" },
};
const STAMP_TEXT = {
  problems: ["ফেরত আসবে", "Will be returned"],
  check_manually: ["নিজে দেখুন", "Check yourself"],
  ready: ["জমা দেওয়ার জন্য প্রস্তুত", "Ready to submit"],
  unknown_form: ["অচেনা ফর্ম", "Unknown document"],
};

/* The harness rail: one node per step; blue nodes are Gemma 4, green nodes are plain code. */
const RAIL = [
  { id: "read", ai: true, bn: "পড়া", en: "Read",
    say: ["Gemma 4 ছবিটা পড়ে প্রতিটি লেখা হুবহু তুলে আনে", "Gemma 4 reads the photo and copies every value exactly"],
    tech: "Gemma 4 vision → strict JSON, Pydantic-validated, 1 self-repair retry", icon: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>' },
  { id: "match", ai: false, bn: "মেলানো", en: "Match",
    say: ["কোড বুঝে নেয় এটা কোন ফর্ম বা দরখাস্ত", "Code works out which form or letter it is"],
    tech: "Deterministic matcher → rule card (form/letter aware); unknown → refuse", icon: '<path d="M10 14a4 4 0 0 0 5.66 0l3-3a4 4 0 0 0-5.66-5.66l-1 1"/><path d="M14 10a4 4 0 0 0-5.66 0l-3 3a4 4 0 0 0 5.66 5.66l1-1"/>' },
  { id: "audit", ai: false, bn: "নিয়ম", en: "Rules",
    say: ["অফিসের প্রতিটি নিয়ম কোড দিয়ে মিলিয়ে দেখে", "Code checks every office rule"],
    tech: "Rule engine: required · pattern · date · contains_any · signature · photo", icon: '<path d="M10 6h10M10 12h10M10 18h10"/><path d="M3 6l1.5 1.5L7 5M3 12l1.5 1.5L7 11M3 18l1.5 1.5L7 17"/>' },
  { id: "verify", ai: true, bn: "পুনর্দেখা", en: "Re-check",
    say: ["Gemma আবার ছবিতে দেখে, ভুলটা সত্যিই আছে কি না", "Gemma looks again to confirm each problem"],
    tech: "Second vision pass per flag; unconfirmed → manual review", icon: '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.5-4.5"/>' },
  { id: "explain", ai: true, bn: "সমাধান", en: "Fix",
    say: ["কীভাবে ঠিক করবেন, বাংলায় লিখে দেয়", "It explains each fix in plain Bangla and English"],
    tech: "Grounded generation from rule text; unknown rule IDs dropped", icon: '<path d="M4 5h16v11H9l-5 4z"/>' },
  { id: "draft", ai: true, bn: "দরখাস্ত", en: "Draft",
    say: ["দরখাস্ত হলে আপনার তথ্য দিয়েই নতুন করে লিখে দেয়", "For letters, it rewrites the letter from your own details"],
    tech: "Letter rewrite + code-side ID grounding (invented IDs removed)", icon: '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13 7l4 4"/>' },
];

const state = { cards: [], engines: null, engineValue: "", engineNotes: [], cardId: null, blob: null, pads: {}, previewUrl: null, running: false };

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const bnDigits = (n) => String(n).replace(/\d/g, (d) => "০১২৩৪৫৬৭৮৯"[d]);
/* bi(): Bangla first with English as a quiet second line; in English mode only the English shows.
   one(): exactly one language at a time. Both take already-escaped HTML. */
const bi = (bn, en) => `<span class="bn">${bn}</span><span class="en">${en}</span>`;
const one = (bn, en) => `<span class="bn-only">${bn}</span><span class="en-only">${en}</span>`;
const lang = () => document.documentElement.dataset.lang || "bn";

function buildRail(el, interactive = false) {
  const tag = interactive ? "button" : "span";
  el.innerHTML = `<div class="rail-track"><span class="rail-line"></span><span class="rail-dot"></span></div>
    <ol class="rail-nodes">${RAIL.map((n, i) => `<li class="node ${n.ai ? "ai" : "code"}" data-step="${n.id}" style="--i:${i}">
      <${tag} class="node-btn" ${interactive ? `type="button" data-index="${i}" aria-label="${n.en}: ${n.say[1]}"` : ""}>
      <span class="node-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${n.icon}</svg></span>
      <span class="node-label">${one(n.bn, n.en)}</span></${tag}></li>`).join("")}</ol>
    <p class="rail-legend"><span class="lg ai">Gemma 4 (AI)</span><span class="lg code">${one("কোড (নিয়ম)", "Code (rules)")}</span></p>`;
}

/* The storyboard in the hero plays the six steps on a 12 s loop (2 s per step).
   Tapping a step seeks every animation in it to that step and pauses, so the story can be read at any pace. */
const STORY_MS = 12000;
const STEP_MS = 2000;
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function buildStory() {
  const story = $("#story");
  buildRail($("#hero-rail"), true);
  $("#story-caps").innerHTML = RAIL.map((n, i) => `<p class="cap" data-i="${i}" style="--i:${i}">
    <span class="cap-step ${n.ai ? "ai" : "code"}">${i + 1}</span>
    <span class="cap-text">${one(n.say[0], n.say[1])}<span class="cap-tech">${esc(n.tech)}</span></span></p>`).join("");
  for (const btn of story.querySelectorAll(".node-btn")) btn.addEventListener("click", () => storySeek(Number(btn.dataset.index)));
  $("#story-toggle").addEventListener("click", () => setStoryPaused(!story.classList.contains("paused")));
  if (reducedMotion) storySeek(0);
  else setStoryPaused(false);
}

function storySeek(index) {
  const story = $("#story");
  story.dataset.step = index;
  if (!reducedMotion) {
    for (const a of story.getAnimations({ subtree: true })) a.currentTime = STORY_MS + index * STEP_MS + 1100;
  }
  setStoryPaused(true);
}

function setStoryPaused(paused) {
  const story = $("#story");
  story.classList.toggle("paused", paused);
  if (!reducedMotion) {
    for (const a of story.getAnimations({ subtree: true })) (paused ? a.pause() : a.play());
  }
  $("#story-toggle").innerHTML = paused ? one("▶ চালান", "▶ Play") : one("⏸ থামান", "⏸ Pause");
}

/* The workspace rail stays still until a check starts; then it mirrors the real run step by step. */
function railIdle() {
  const el = $("#live-rail");
  el.className = "rail idle";
  for (const node of el.querySelectorAll(".node")) node.classList.remove("running", "done", "skipped", "failed");
  el.style.removeProperty("--pos");
}

function railLive() {
  const el = $("#live-rail");
  el.className = "rail live";
  for (const node of el.querySelectorAll(".node")) node.classList.remove("running", "done", "skipped", "failed");
  el.style.setProperty("--pos", "0%");
}

function railStep(id, status) {
  const el = $("#live-rail");
  const node = el.querySelector(`.node[data-step="${id}"]`);
  if (!node) return;
  node.classList.remove("running", "done", "skipped", "failed");
  node.classList.add(status);
  if (status === "running" || status === "done") {
    const index = RAIL.findIndex((n) => n.id === id);
    el.style.setProperty("--pos", `${(index / (RAIL.length - 1)) * 100}%`);
  }
}

function store(key, value) {
  try {
    if (value === undefined) return localStorage.getItem(key);
    localStorage.setItem(key, value);
  } catch (_) { /* storage can be blocked; the choice just won't be remembered */ }
  return null;
}

async function init() {
  setLang(store(LANG_KEY) || "bn", false);
  buildStory();
  buildRail($("#live-rail"));
  for (const btn of document.querySelectorAll(".lang-switch button")) btn.addEventListener("click", () => setLang(btn.dataset.lang));
  const [cards, engines] = await Promise.all([
    fetch("/api/cards").then((r) => r.json()),
    fetch("/api/engines").then((r) => r.json()),
  ]);
  state.cards = cards;
  state.engines = engines;
  renderEngines();
  $("#known-forms").innerHTML = cards.map((c) => one(esc(c.title_bn), esc(c.title_en))).join(", ");
  bindTabs();
  bindSnap();
  bindMaker();
  $("#check-btn").addEventListener("click", runCheck);
  $("#cta-snap").addEventListener("click", () => { showTab("snap"); $("#photo-input").click(); });
  $("#cta-sample").addEventListener("click", trySample);
  $("#edit-btn").addEventListener("click", () => {
    reviewing(false);
    $(".input-pane").scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

function setLang(value, remember = true) {
  const html = document.documentElement;
  html.dataset.lang = value;
  html.lang = value;
  for (const btn of document.querySelectorAll(".lang-switch button")) btn.setAttribute("aria-checked", String(btn.dataset.lang === value));
  if (remember) store(LANG_KEY, value);
}

/* ---------- engine choice ---------- */

function renderEngines() {
  const box = $("#engine-chips");
  const saved = store(ENGINE_KEY);
  const choices = [];
  box.innerHTML = "";
  state.engineNotes = [];
  for (const engine of state.engines.engines) {
    for (const model of engine.available ? engine.models : [null]) {
      const value = model ? `${engine.id}|${model}` : "";
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "chip engine-chip";
      chip.setAttribute("role", "radio");
      chip.disabled = !engine.available;
      chip.dataset.value = value;
      chip.innerHTML = `<span class="dot ${engine.available ? "on" : "off"}" aria-hidden="true"></span><span>${esc(engine.label)}<span class="sub">${esc(model || "not available here")}</span></span>`;
      chip.addEventListener("click", () => selectEngine(value));
      box.append(chip);
      if (model) choices.push(value);
    }
    if (!engine.available) state.engineNotes.push(`${engine.label}: ${engine.reason}`);
  }
  const def = state.engines.engines.find((e) => e.id === state.engines.default && e.available);
  selectEngine(choices.includes(saved) ? saved : def ? `${def.id}|${def.default_model}` : choices[0] || "", false);
}

function selectEngine(value, remember = true) {
  state.engineValue = value;
  if (remember && value) store(ENGINE_KEY, value);
  for (const chip of document.querySelectorAll(".engine-chip")) {
    chip.setAttribute("aria-checked", String(Boolean(value) && chip.dataset.value === value));
  }
  const engine = selectedEngine();
  const main = engine ? one(...ENGINE_TEXT[engine.backend].map(esc)) : one("কোনো মডেল চালু নেই।", "No engine is available.");
  $("#engine-note").innerHTML = main + state.engineNotes.map((n) => `<span class="note-line">${esc(n)}</span>`).join("");
  $("#check-btn").disabled = !state.blob || !engine;
}

function selectedEngine() {
  if (!state.engineValue) return null;
  const [backend, ...rest] = state.engineValue.split("|");
  return { backend, model: rest.join("|") };
}

/* After Check the editor folds away so the document and the analysis sit side by side;
   "Edit again" brings it back. */
function reviewing(on) {
  $(".input-pane").classList.toggle("reviewing", on);
  $("#edit-btn").hidden = !on;
}

/* ---------- tabs ---------- */

function bindTabs() {
  $("#tab-snap").addEventListener("click", () => showTab("snap"));
  $("#tab-maker").addEventListener("click", () => showTab("maker"));
}

async function showTab(name) {
  reviewing(false);
  for (const t of ["snap", "maker"]) {
    $(`#tab-${t}`).setAttribute("aria-selected", String(t === name));
    $(`#pane-${t}`).hidden = t !== name;
  }
  setBlob(null);
  if (name === "maker") await refreshMakerPreview();
}

async function trySample() {
  await showTab("maker");
  selectCard(state.cards.some((c) => c.id === "transcript_letter") ? "transcript_letter" : state.cards[0].id, false);
  plantMistakes(currentCard());
  await refreshMakerPreview();
  $("#dock").scrollIntoView({ behavior: "smooth", block: "center" });
}

/* ---------- photo path ---------- */

function bindSnap() {
  $("#photo-input").addEventListener("change", async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    setBlob(await downscale(file));
  });
}

async function downscale(file, max = 1600) {
  const url = URL.createObjectURL(file);
  try {
    const img = await new Promise((resolve, reject) => {
      const i = new Image();
      i.onload = () => resolve(i);
      i.onerror = reject;
      i.src = url;
    });
    const scale = Math.min(1, max / Math.max(img.naturalWidth, img.naturalHeight));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(img.naturalWidth * scale);
    canvas.height = Math.round(img.naturalHeight * scale);
    canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
    return await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.85));
  } finally {
    URL.revokeObjectURL(url);
  }
}

function setBlob(blob) {
  state.blob = blob;
  $("#check-btn").disabled = !blob || !selectedEngine();
  $("#stamp").hidden = true;
  if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
  state.previewUrl = blob ? URL.createObjectURL(blob) : null;
  $("#sheet").hidden = !blob;
  if (blob) $("#preview").src = state.previewUrl;
  if (!state.running) railIdle();
}

/* ---------- form maker ---------- */

function bindMaker() {
  const box = $("#card-chips");
  const groups = [["form", "ছাপা ফর্ম", "Printed forms"], ["letter", "দরখাস্ত", "Application letters"]];
  for (const [kind, bn, en] of groups) {
    const cards = state.cards.filter((c) => (c.kind || "form") === kind);
    if (!cards.length) continue;
    const group = document.createElement("div");
    group.className = "chip-group";
    group.innerHTML = `<p class="chip-group-title">${one(bn, en)}</p>`;
    for (const card of cards) {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "chip card-chip";
      chip.setAttribute("role", "radio");
      chip.dataset.id = card.id;
      chip.innerHTML = `<span class="card-title">${bi(esc(card.title_bn), esc(card.title_en))}</span><span class="aud">${one(esc(card.audience_bn || ""), esc(card.audience_en || ""))}</span>`;
      chip.addEventListener("click", () => selectCard(card.id));
      group.append(chip);
    }
    box.append(group);
  }
  $("#photo-toggle").addEventListener("change", refreshMakerPreview);
  $("#plant-mistakes").addEventListener("click", () => { plantMistakes(currentCard()); refreshMakerPreview(); });
  $("#fill-correct").addEventListener("click", () => { buildMaker(currentCard()); refreshMakerPreview(); });
  selectCard(state.cards.some((c) => c.id === "transcript_application") ? "transcript_application" : state.cards[0].id, false);
}

function selectCard(id, refresh = true) {
  state.cardId = id;
  for (const chip of document.querySelectorAll(".card-chip")) chip.setAttribute("aria-checked", String(chip.dataset.id === id));
  const card = currentCard();
  $("#card-source").textContent = card.source || "";
  buildMaker(card);
  if (refresh) refreshMakerPreview();
}

const currentCard = () => state.cards.find((c) => c.id === state.cardId) || state.cards[0];

function signatureName(card) {
  const field = card.fields.find((f) => f.key === "student_name" || f.key === "sender_name");
  const words = (field ? field.sample : "Signature").split(/\s+/).filter((w) => !/^md\.?$/i.test(w));
  return words[0] || "Signature";
}

function buildMaker(card) {
  const fields = $("#maker-fields");
  fields.innerHTML = "";
  for (const f of card.fields) {
    const label = document.createElement("label");
    label.innerHTML = bi(esc(f.label_bn), esc(f.label_en));
    // Long values get a wrapping box across the full width, so nothing is cut off inside the field.
    const wide = f.sample.length > 22;
    const input = document.createElement(wide ? "textarea" : "input");
    if (wide) { input.rows = 2; label.classList.add("wide"); }
    input.value = f.sample;
    input.dataset.key = f.key;
    input.autocomplete = "off";
    input.addEventListener("input", debounce(refreshMakerPreview, 300));
    label.append(input);
    fields.append(label);
  }
  const sigs = $("#maker-signatures");
  sigs.innerHTML = "";
  state.pads = {};
  for (const s of card.signatures) {
    const wrap = document.createElement("div");
    wrap.className = "sig";
    wrap.innerHTML = `<span>${bi(esc(s.label_bn), esc(s.label_en))}<span class="sig-hint">${one("আঙুল বা মাউস দিয়ে স্বাক্ষর করুন", "Sign with your finger or mouse")}</span></span>`;
    const padWrap = document.createElement("div");
    padWrap.className = "sig-pad-wrap";
    const canvas = document.createElement("canvas");
    const clear = document.createElement("button");
    clear.type = "button";
    clear.className = "sig-clear";
    clear.innerHTML = one("মুছুন", "Clear");
    padWrap.append(canvas, clear);
    wrap.append(padWrap);
    sigs.append(wrap);
    state.pads[s.key] = makePad(canvas, clear);
  }
  $("#photo-row").hidden = !card.photo_required;
  $("#photo-toggle").checked = true;
  const name = signatureName(card);
  for (const pad of Object.values(state.pads)) pad.sample(name);
}

function plantMistakes(card) {
  // Each rule card lists its own three demo mistakes, so the button always plants exactly three problems.
  const demo = card.demo_mistakes || {};
  for (const [key, value] of Object.entries(demo.set || {})) {
    const input = $(`#maker-fields [data-key='${key}']`);
    if (input) input.value = value;
  }
  if (demo.clear_signature && state.pads[demo.clear_signature]) state.pads[demo.clear_signature].clear();
  if (demo.photo_off) $("#photo-toggle").checked = false;
}

function makePad(canvas, clearBtn) {
  const ratio = Math.max(1, window.devicePixelRatio || 1);
  const ctx = canvas.getContext("2d");
  const size = () => {
    canvas.width = Math.round(canvas.clientWidth * ratio) || 600;
    canvas.height = Math.round(90 * ratio);
    ctx.lineWidth = 2.6 * ratio;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.strokeStyle = "#1f3a93";
  };
  let drawing = false;
  let inked = false;
  const point = (e) => {
    const r = canvas.getBoundingClientRect();
    return [(e.clientX - r.left) * ratio, (e.clientY - r.top) * ratio];
  };
  canvas.addEventListener("pointerdown", (e) => {
    drawing = true;
    inked = true;
    canvas.setPointerCapture(e.pointerId);
    ctx.beginPath();
    ctx.moveTo(...point(e));
  });
  canvas.addEventListener("pointermove", (e) => {
    if (!drawing) return;
    ctx.lineTo(...point(e));
    ctx.stroke();
  });
  const end = () => {
    if (!drawing) return;
    drawing = false;
    refreshMakerPreview();
  };
  canvas.addEventListener("pointerup", end);
  canvas.addEventListener("pointercancel", end);
  const drawName = (name) => {
    size();
    ctx.save();
    ctx.fillStyle = "#1f3a93";
    ctx.font = `${40 * ratio}px "Homemade Apple", "Caveat", cursive`;
    ctx.translate(canvas.width * 0.08, canvas.height * 0.68);
    ctx.rotate(-0.06);
    ctx.fillText(name, 0, 0);
    ctx.restore();
  };
  const pad = {
    canvas,
    get inked() { return inked; },
    clear() { size(); inked = false; },
    sample(name) {
      // A cursive name like a real student signature; judges can clear it and sign themselves.
      drawName(name);
      inked = true;
      document.fonts.load(`30px "Homemade Apple"`).then(() => {
        if (!inked) return;
        drawName(name);
        refreshMakerPreview();
      }).catch(() => {});
    },
  };
  clearBtn.addEventListener("click", () => { pad.clear(); refreshMakerPreview(); });
  return pad;
}

function debounce(fn, ms) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

async function refreshMakerPreview() {
  if ($("#pane-maker").hidden) return;
  const canvas = await renderFormCanvas(currentCard());
  setBlob(await new Promise((resolve) => canvas.toBlob(resolve, "image/png")));
}

function fitFont(ctx, text, maxWidth, size, family, weight = "400") {
  let s = size;
  do {
    ctx.font = `${weight} ${s}px ${family}`;
    if (ctx.measureText(text).width <= maxWidth) break;
    s -= 1;
  } while (s > 12);
  return s;
}

/* Draws the filled form exactly as a phone photo of paper would show it; the model only ever sees this image. */
async function renderFormCanvas(card) {
  const UI = '"Anek Bangla", "Noto Sans Bengali", "Bangla Sangam MN", sans-serif';
  const HAND = '"Caveat", "Bradley Hand", cursive';
  await Promise.all([document.fonts.load(`30px ${HAND}`), document.fonts.load(`20px ${UI}`)]).catch(() => {});
  const values = Object.fromEntries([...document.querySelectorAll("#maker-fields [data-key]")].map((i) => [i.dataset.key, i.value]));
  if (card.kind === "letter") return renderLetterCanvas(card, values, HAND);
  const W = 1000, rowH = 60, top = 230, labelW = 400;
  const H = top + card.fields.length * rowH + 300;
  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#fffdf8";
  ctx.fillRect(0, 0, W, H);
  ctx.strokeStyle = "#555";
  ctx.lineWidth = 1.5;
  ctx.strokeRect(14, 14, W - 28, H - 28);

  ctx.fillStyle = "#111";
  ctx.font = `700 26px Arial, sans-serif`;
  ctx.fillText("SAMPLE UNIVERSITY (IIUC-style sample form)", 40, 62);
  ctx.font = `20px Arial, sans-serif`;
  ctx.fillText(card.office_en, 40, 94);
  ctx.font = `700 23px Arial, sans-serif`;
  ctx.fillText(card.title_en.toUpperCase(), 40, 130);
  ctx.font = `22px ${UI}`;
  ctx.fillText(card.title_bn, 40, 166);

  if (card.photo_required) {
    const px = W - 190, py = 34, pw = 140, ph = 170;
    if ($("#photo-toggle").checked) {
      const g = ctx.createLinearGradient(px, py, px, py + ph);
      g.addColorStop(0, "#cfd8dc");
      g.addColorStop(1, "#90a4ae");
      ctx.fillStyle = g;
      ctx.fillRect(px, py, pw, ph);
      ctx.fillStyle = "#4e342e";
      ctx.beginPath();
      ctx.arc(px + pw / 2, py + 62, 30, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#37474f";
      ctx.beginPath();
      ctx.ellipse(px + pw / 2, py + ph, 58, 62, 0, Math.PI, 0);
      ctx.fill();
    } else {
      ctx.setLineDash([6, 5]);
      ctx.strokeRect(px, py, pw, ph);
      ctx.setLineDash([]);
      ctx.fillStyle = "#333";
      ctx.font = `14px Arial, sans-serif`;
      ctx.fillText("Paste passport-size", px + 8, py + 80);
      ctx.fillText("photo here", px + 36, py + 100);
    }
  }

  ctx.strokeStyle = "#333";
  ctx.lineWidth = 1.2;
  card.fields.forEach((f, i) => {
    const y = top + i * rowH;
    ctx.strokeRect(40, y, W - 80, rowH);
    ctx.beginPath();
    ctx.moveTo(40 + labelW, y);
    ctx.lineTo(40 + labelW, y + rowH);
    ctx.stroke();
    const label = `${f.label_bn} / ${f.label_en}`;
    ctx.fillStyle = "#111";
    fitFont(ctx, label, labelW - 24, 19, UI);
    ctx.fillText(label, 52, y + 38);
    ctx.fillStyle = "#1f3a93";
    fitFont(ctx, values[f.key] || "", W - 80 - labelW - 30, 32, HAND, "500");
    ctx.fillText(values[f.key] || "", 40 + labelW + 16, y + 41);
  });

  let y = top + card.fields.length * rowH + 36;
  ctx.fillStyle = "#222";
  if (card.attachments.length) {
    const attach = "Attach: " + card.attachments.map((a, i) => `(${i + 1}) ${a.en}`).join(", ");
    fitFont(ctx, attach, W - 80, 17, "Arial, sans-serif");
    ctx.fillText(attach, 40, y);
  }

  y += 150;
  const n = card.signatures.length;
  card.signatures.forEach((s, k) => {
    const boxW = 320;
    const x = n === 1 ? 40 : 40 + k * (W - 80 - boxW);
    const pad = state.pads[s.key];
    if (pad && pad.inked) ctx.drawImage(pad.canvas, x, y - 92, boxW, 86);
    ctx.strokeStyle = "#333";
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(x + boxW, y);
    ctx.stroke();
    ctx.fillStyle = "#111";
    const caption = `${s.label_bn} / ${s.label_en}`;
    fitFont(ctx, caption, boxW, 18, UI);
    ctx.fillText(caption, x, y + 28);
  });
  return canvas;
}

/* A handwritten application letter on ruled paper, in the usual Bangladeshi university format. */
function renderLetterCanvas(card, values, HAND) {
  const W = 1000, left = 90, lineH = 46, width = W - left - 60;
  const measure = document.createElement("canvas").getContext("2d");
  measure.font = `500 30px ${HAND}`;
  const wrap = (text) => {
    const out = [];
    let line = "";
    for (const word of text.split(/\s+/).filter(Boolean)) {
      const next = line ? `${line} ${word}` : word;
      if (measure.measureText(next).width > width && line) { out.push(line); line = word; } else line = next;
    }
    if (line) out.push(line);
    return out;
  };
  const body = (card.body_template_en || "").replace(/\{(\w+)\}/g, (_, k) => values[k] || "");
  const lines = [`Date: ${values.date || ""}`, "", "To", ...(values.addressee || "").split(/,\s*/).filter(Boolean),
    "", `Subject: ${values.subject || ""}`, "", "Sir,", ...wrap(body), "", "Yours obediently,", "@sig",
    `Name: ${values.student_name || ""}`, `ID: ${values.student_id || ""}`,
    `Department: ${values.department || ""}, Semester: ${values.semester || ""}`];
  const H = 70 + lines.length * lineH + 70;
  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#fffdf6";
  ctx.fillRect(0, 0, W, H);
  ctx.strokeStyle = "#cfdcef";
  ctx.lineWidth = 1;
  for (let y = 70 + lineH; y < H; y += lineH) { ctx.beginPath(); ctx.moveTo(0, y + 8); ctx.lineTo(W, y + 8); ctx.stroke(); }
  ctx.strokeStyle = "#e7a5a5";
  ctx.beginPath(); ctx.moveTo(left - 22, 0); ctx.lineTo(left - 22, H); ctx.stroke();
  ctx.fillStyle = "#1f3a93";
  ctx.font = `500 30px ${HAND}`;
  lines.forEach((text, i) => {
    const y = 70 + (i + 1) * lineH;
    if (text === "@sig") {
      const pad = state.pads.student;
      // Keep the pad's proportions so the signature stays as large as it was drawn.
      if (pad && pad.inked) ctx.drawImage(pad.canvas, left, y - 52, 380, 380 * pad.canvas.height / pad.canvas.width);
      return;
    }
    ctx.fillText(text, left, y);
  });
  return canvas;
}

/* ---------- running a check ---------- */

const STATE_TEXT = {
  waiting: one("অপেক্ষায়", "Waiting"),
  running: one("চলছে…", "Running…"),
  done: one("হয়েছে ✓", "Done ✓"),
  skipped: one("দরকার হয়নি", "Not needed"),
  lettersOnly: one("শুধু দরখাস্তে", "Letters only"),
  failed: one("ব্যর্থ ✗", "Failed ✗"),
};

function resetTrace() {
  railLive();
  const trace = $("#trace");
  trace.innerHTML = "";
  for (const id of STEP_ORDER) {
    const li = document.createElement("li");
    li.id = `step-${id}`;
    li.className = "waiting";
    li.innerHTML = `<span class="t-title">${bi(STEP_TEXT[id][0], STEP_TEXT[id][1])}</span>
      <span class="t-state">${STATE_TEXT.waiting}</span><span class="t-meta"></span>`;
    trace.append(li);
  }
}

function whoRan(event) {
  if (event.kind === "code") return `<span class="who">${one("কোড", "Code")}</span> (${esc(event.tool)}), ${one("নিয়ম অনুযায়ী, কোনো AI নয়", "rule-based, no AI")}`;
  const where = event.backend === "ollama" ? "local Ollama" : "Google AI Studio";
  return `<span class="who">Gemma 4 · ${esc(event.model)}</span>, ${where}`;
}

function onStep(event) {
  const li = $(`#step-${event.id}`);
  if (!li) return;
  const meta = li.querySelector(".t-meta");
  railStep(event.id, event.status === "start" ? "running" : "done");
  if (event.status === "start") {
    li.className = "running";
    li.querySelector(".t-state").innerHTML = STATE_TEXT.running;
    meta.innerHTML = whoRan(event);
    return;
  }
  li.className = "done";
  li.querySelector(".t-state").innerHTML = STATE_TEXT.done;
  const ms = event.ms ? `, ${(event.ms / 1000).toFixed(1)} s` : "";
  const retried = event.retried ? `, ${one("ফরম্যাট ঠিক করতে আবার চেষ্টা", "retried once to fix the format")}` : "";
  meta.innerHTML = whoRan(event) + ms + retried;
  const details = document.createElement("details");
  details.innerHTML = `<summary>${one("আসল আউটপুট", "Raw output")}</summary><pre>${esc(JSON.stringify(event.output, null, 2))}</pre>`;
  meta.append(details);
}

async function runCheck() {
  const engine = selectedEngine();
  if (!state.blob || !engine) return;
  const btn = $("#check-btn");
  btn.disabled = true;
  $("#result").innerHTML = "";
  $("#stamp").hidden = true;
  resetTrace();
  state.running = true;
  reviewing(true);
  // Take the student to where the analysis is happening, on phones and desktops alike.
  $(".slip").scrollIntoView({ behavior: "smooth", block: "start" });
  const body = new FormData();
  body.append("image", state.blob, state.blob.type === "image/png" ? "form.png" : "form.jpg");
  body.append("backend", engine.backend);
  body.append("model", engine.model);
  try {
    const resp = await fetch("/api/check", { method: "POST", body });
    if (!resp.ok) {
      const detail = (await resp.json().catch(() => ({}))).detail || resp.statusText;
      return showError(detail);
    }
    // Events are read as they stream; if a host buffers the stream they simply arrive together.
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let cut;
      while ((cut = buffer.indexOf("\n\n")) >= 0) {
        const chunk = buffer.slice(0, cut);
        buffer = buffer.slice(cut + 2);
        for (const line of chunk.split("\n")) {
          if (line.startsWith("data: ")) handleEvent(JSON.parse(line.slice(6)));
        }
      }
    }
  } catch (err) {
    showError(`Network problem: ${err.message}`);
  } finally {
    state.running = false;
    btn.disabled = !state.blob;
  }
}

function handleEvent(event) {
  if (event.type === "step") onStep(event);
  else if (event.type === "result") renderResult(event);
  else if (event.type === "error") showError(event.message);
}

function showError(message) {
  for (const li of document.querySelectorAll("#trace li.running")) {
    li.className = "done";
    li.querySelector(".t-state").innerHTML = STATE_TEXT.failed;
    railStep(li.id.replace("step-", ""), "failed");
  }
  $("#result").innerHTML = `<div class="error"><strong>${one("যাচাই শেষ করা যায়নি।", "The check could not finish.")}</strong><br>${esc(message)}</div>`;
}

function stamp(status) {
  const v = VERDICT[status];
  const el = $("#stamp");
  el.className = `stamp ${v.cls}`;
  el.innerHTML = one(...STAMP_TEXT[status]);
  el.hidden = false;
}

function renderResult(r) {
  for (const id of STEP_ORDER) {
    const li = $(`#step-${id}`);
    if (li && li.className === "waiting") {
      li.className = "skipped";
      li.querySelector(".t-state").innerHTML = id === "draft" && r.card?.kind !== "letter" ? STATE_TEXT.lettersOnly : STATE_TEXT.skipped;
      railStep(id, "skipped");
    }
  }
  const count = (r.problems || []).length;
  stamp(r.status);
  const v = VERDICT[r.status];
  const parts = [];
  if (r.status === "unknown_form") {
    parts.push(`<p class="verdict unknown">${one(v.bn(), v.en())}</p>
      <p class="verdict-sub">${one(`ফর্মবন্ধু শুধু যেসব নথির নিয়ম জানে সেগুলোই যাচাই করে, তাই আন্দাজ করে না। শিরোনাম পড়েছে: “${esc(r.form_title)}”।`,
        `FormBondhu only checks documents it has rules for, so it does not guess. It read the title as “${esc(r.form_title)}”.`)}</p>`);
    parts.push(`<h3>${one("যে নথিগুলো চেনে", "Documents it knows")}</h3><ul class="docs">${r.known.map((k) => `<li>${bi(esc(k.title_bn), esc(k.title_en))}</li>`).join("")}</ul>`);
  } else {
    parts.push(`<span class="badge">${one("নমুনা নিয়ম", "Sample rules")}</span>`);
    parts.push(`<p class="verdict ${v.cls}">${one(v.bn(count), v.en(count))}</p><p class="verdict-sub">${one(esc(r.card.title_bn), esc(r.card.title_en))}</p>`);
    if ("speechSynthesis" in window) parts.push(`<button type="button" class="ghost listen-btn" id="listen">${one("শুনুন", "Read aloud")}</button>`);
    if (count) parts.push(`<h3>${one("যা ঠিক করতে হবে", "Fix before you go")}</h3><ul class="problems">${r.problems.map(problemItem).join("")}</ul>`);
    if (r.draft) {
      const holes = (r.draft.placeholders || []).length
        ? `<p class="letter-note">${one("বন্ধনীর [ ] জায়গাগুলো নিজে পূরণ করুন।", "Fill in the parts in square brackets yourself.")}</p>` : "";
      parts.push(`<h3>${one("সংশোধিত দরখাস্ত", "Corrected letter")}<span class="h3-sub">${one("শুধু আপনার দেওয়া তথ্য দিয়ে লেখা", "written only from your own details")}</span></h3>
        <div class="letter-box"><button type="button" class="ghost copy-btn" id="copy-letter">${one("কপি করুন", "Copy")}</button>
        <pre class="letter">${esc(r.draft.letter).replace(/\[([^\]]+)\]/g, '<mark class="hole">[$1]</mark>')}</pre>${holes}</div>`);
    }
    if ((r.manual || []).length) {
      parts.push(`<h3>${one("নিজে একবার দেখুন", "Check these yourself")}<span class="h3-sub">${one("দ্বিতীয়বার দেখে নিশ্চিত হওয়া যায়নি", "the second look could not confirm them")}</span></h3><ul class="problems manual">${r.manual.map(problemItem).join("")}</ul>`);
    }
    if (r.attachments.length) {
      parts.push(`<h3>${one("সাথে যা নিতে হবে", "Bring with it")}</h3><ul class="docs">${r.attachments.map((a) => `<li>${bi(esc(a.bn), esc(a.en))}</li>`).join("")}</ul>`);
    }
    parts.push(`<h3>${one("কোন অফিসে, কোন ক্রমে", "Where to go, in order")}</h3><ol class="route">${r.route.map((s) => `<li><span class="office">${bi(esc(s.office_bn), esc(s.office_en))}</span><span>${bi(esc(s.task_bn), esc(s.task_en))}</span></li>`).join("")}</ol>`);
    if ((r.passed || []).length) {
      const n = r.passed.length;
      parts.push(`<details class="passed"><summary>${one(`${bnDigits(n)}টি নিয়ম ঠিক আছে`, `${n} rules passed`)}</summary><ul>${r.passed.map((p) => `<li>${esc(p.rule_id)}: ${one(esc(p.label_bn), esc(p.label_en))}</li>`).join("")}</ul></details>`);
    }
  }
  const where = r.engine.backend === "ollama" ? "local Ollama" : "Google AI Studio";
  const secs = (r.ms / 1000).toFixed(1);
  parts.push(`<p class="run-meta">${one(`মডেল: Gemma 4 (${esc(r.engine.model)}), ${where}। মোট সময় ${secs} সেকেন্ড।`, `Model: Gemma 4 (${esc(r.engine.model)}) on ${where}. Total ${secs} s.`)}${r.card?.source ? `<br>${esc(r.card.source)}` : ""}</p>`);
  $("#result").innerHTML = parts.join("");
  // Bring the verdict to the middle of the screen once it lands, unless it is already near the top.
  const verdict = $(".verdict");
  const box = verdict && verdict.getBoundingClientRect();
  if (box && (box.top < 0 || box.top > window.innerHeight * 0.55)) {
    setTimeout(() => verdict.scrollIntoView({ behavior: "smooth", block: "center" }), 350);
  }
  const listen = $("#listen");
  if (listen) listen.addEventListener("click", () => speakResult(r));
  const copy = $("#copy-letter");
  if (copy) {
    copy.addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(r.draft.letter); copy.innerHTML = one("কপি হয়েছে", "Copied"); } catch (_) { copy.innerHTML = one("কপি করা যায়নি", "Copy failed"); }
    });
  }
}

/* Reads the verdict and each fix aloud for students who cannot read the screen easily.
   Uses a Bangla voice when the device has one and Bangla is selected, otherwise English. */
function speakResult(r) {
  speechSynthesis.cancel();
  const v = VERDICT[r.status];
  const items = [...(r.problems || []), ...(r.manual || [])];
  const bnVoice = speechSynthesis.getVoices().find((x) => x.lang && x.lang.toLowerCase().startsWith("bn"));
  const useBn = lang() === "bn" && bnVoice;
  const text = useBn
    ? [v.bn(items.length), ...items.map((p) => `${p.label_bn}: ${p.fix_bn}`)].join("। ")
    : [v.en(items.length), ...items.map((p) => `${p.label_en}: ${p.fix_en}`)].join(". ");
  const u = new SpeechSynthesisUtterance(text);
  if (useBn) { u.voice = bnVoice; u.lang = bnVoice.lang; } else { u.lang = "en-US"; }
  u.rate = 0.95;
  speechSynthesis.speak(u);
}

function problemItem(p) {
  const seen = p.seen ? `<p class="seen">${one("Gemma যা দেখেছে", "What Gemma saw")}: “${esc(p.seen)}”</p>` : "";
  return `<li><div class="where"><span>${one(esc(p.label_bn), esc(p.label_en))}</span><span class="rid">${esc(p.rule_id)}</span></div>
    <p class="fix">${bi(esc(p.fix_bn), esc(p.fix_en))}</p>${seen}</li>`;
}

init().catch((err) => showError(`Could not start: ${err.message}`));

"use strict";

const $ = (sel) => document.querySelector(sel);
const STORE_KEY = "formbondhu.engine";
const STEP_ORDER = ["read", "match", "audit", "verify", "explain"];
const STEP_TEXT = {
  read: ["ফর্ম পড়া", "Read the form"],
  match: ["নিয়মের কার্ড মেলানো", "Match the rule card"],
  audit: ["প্রতিটি নিয়ম যাচাই", "Check every rule"],
  verify: ["প্রতিটি সমস্যা আবার দেখা", "Double-check each problem"],
  explain: ["বাংলায় সমাধান লেখা", "Write fixes in Bangla"],
};
const ENGINE_TEXT = {
  aistudio: "Gemma 4 চলছে Google AI Studio-তে (open-weights model, hosted free API)",
  ollama: "Gemma 4 চলছে আপনার নিজের কম্পিউটারে, Ollama দিয়ে (open-weights model, runs locally)",
};
const VERDICT = {
  problems: { cls: "bad", bn: "ফেরত আসবে", en: (n) => `${n} problem${n === 1 ? "" : "s"} found` },
  check_manually: { cls: "warn", bn: "নিজে একবার দেখুন", en: () => "Check these yourself" },
  ready: { cls: "good", bn: "জমা দেওয়ার জন্য প্রস্তুত", en: () => "Ready to submit" },
  unknown_form: { cls: "unknown", bn: "অচেনা ফর্ম", en: () => "Unknown form" },
};

const state = { cards: [], engines: null, blob: null, pads: {}, previewUrl: null };

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const bnDigits = (n) => String(n).replace(/\d/g, (d) => "০১২৩৪৫৬৭৮৯"[d]);

function store(value) {
  try {
    if (value === undefined) return localStorage.getItem(STORE_KEY);
    localStorage.setItem(STORE_KEY, value);
  } catch (_) { /* storage can be blocked; the choice just won't be remembered */ }
  return null;
}

async function init() {
  const [cards, engines] = await Promise.all([
    fetch("/api/cards").then((r) => r.json()),
    fetch("/api/engines").then((r) => r.json()),
  ]);
  state.cards = cards;
  state.engines = engines;
  renderEngines();
  $("#known-forms").textContent = cards.map((c) => c.title_bn).join(", ");
  bindTabs();
  bindSnap();
  bindMaker();
  $("#check-btn").addEventListener("click", runCheck);
}

/* ---------- engine choice ---------- */

function renderEngines() {
  const select = $("#engine-select");
  const saved = store();
  const notes = [];
  select.innerHTML = "";
  for (const engine of state.engines.engines) {
    if (engine.available) {
      for (const model of engine.models) {
        const opt = new Option(`${engine.label}: ${model}`, `${engine.id}|${model}`);
        select.add(opt);
      }
    } else {
      const opt = new Option(`${engine.label}: not available here`, "", false, false);
      opt.disabled = true;
      select.add(opt);
      notes.push(`${engine.label}: ${engine.reason}`);
    }
  }
  const values = [...select.options].filter((o) => !o.disabled).map((o) => o.value);
  const def = state.engines.engines.find((e) => e.id === state.engines.default && e.available);
  select.value = values.includes(saved) ? saved : def ? `${def.id}|${def.default_model}` : values[0] || "";
  const update = () => {
    const engine = selectedEngine();
    const lines = [engine ? ENGINE_TEXT[engine.backend] : "কোনো মডেল চালু নেই। No engine is available.", ...notes];
    $("#engine-note").innerHTML = lines.map((l, i) => (i ? `<span class="en">${esc(l)}</span>` : esc(l))).join("");
  };
  select.addEventListener("change", () => { store(select.value); update(); });
  update();
}

function selectedEngine() {
  const value = $("#engine-select").value;
  if (!value) return null;
  const [backend, ...rest] = value.split("|");
  return { backend, model: rest.join("|") };
}

/* ---------- tabs ---------- */

function bindTabs() {
  const tabs = [["#tab-snap", "#pane-snap"], ["#tab-maker", "#pane-maker"]];
  for (const [tabSel, paneSel] of tabs) {
    $(tabSel).addEventListener("click", async () => {
      for (const [t, p] of tabs) {
        $(t).setAttribute("aria-selected", String(t === tabSel));
        $(p).hidden = p !== paneSel;
      }
      setBlob(null);
      if (paneSel === "#pane-maker") await refreshMakerPreview();
    });
  }
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
}

/* ---------- form maker ---------- */

function bindMaker() {
  const select = $("#card-select");
  for (const card of state.cards) select.add(new Option(card.title_bn, card.id));
  if (state.cards.some((c) => c.id === "transcript_application")) select.value = "transcript_application";
  const showTitle = () => { $("#card-title-en").textContent = currentCard().title_en; };
  select.addEventListener("change", () => { showTitle(); buildMaker(currentCard()); refreshMakerPreview(); });
  showTitle();
  $("#photo-toggle").addEventListener("change", refreshMakerPreview);
  $("#plant-mistakes").addEventListener("click", () => { plantMistakes(currentCard()); refreshMakerPreview(); });
  $("#fill-correct").addEventListener("click", () => { buildMaker(currentCard()); refreshMakerPreview(); });
  buildMaker(currentCard());
}

const currentCard = () => state.cards.find((c) => c.id === $("#card-select").value) || state.cards[0];

function buildMaker(card) {
  const fields = $("#maker-fields");
  fields.innerHTML = "";
  for (const f of card.fields) {
    const label = document.createElement("label");
    label.innerHTML = `${esc(f.label_bn)}<span class="en">${esc(f.label_en)}</span>`;
    const input = document.createElement("input");
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
    wrap.innerHTML = `<span>${esc(s.label_bn)} <span class="en">${esc(s.label_en)}: আঙুল বা মাউস দিয়ে স্বাক্ষর করুন / sign with finger or mouse</span></span>`;
    const padWrap = document.createElement("div");
    padWrap.className = "sig-pad-wrap";
    const canvas = document.createElement("canvas");
    const clear = document.createElement("button");
    clear.type = "button";
    clear.className = "sig-clear";
    clear.textContent = "মুছুন / Clear";
    padWrap.append(canvas, clear);
    wrap.append(padWrap);
    sigs.append(wrap);
    state.pads[s.key] = makePad(canvas, clear);
  }
  $("#photo-row").hidden = !card.photo_required;
  $("#photo-toggle").checked = true;
  for (const pad of Object.values(state.pads)) pad.sample();
}

function plantMistakes(card) {
  const date = $("#maker-fields input[data-key='date']");
  if (date) date.value = "12/3/26";
  const lastSig = card.signatures[card.signatures.length - 1];
  state.pads[lastSig.key].clear();
  if (card.photo_required) {
    $("#photo-toggle").checked = false;
  } else {
    const code = $("#maker-fields input[data-key='course_code']");
    if (code) code.value = "Data Structures";
  }
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
  const pad = {
    canvas,
    get inked() { return inked; },
    clear() { size(); inked = false; },
    sample() {
      // A pre-drawn squiggle so "Fill it correctly" starts from a signed form; judges can clear and re-sign.
      size();
      const w = canvas.width, h = canvas.height;
      ctx.beginPath();
      ctx.moveTo(w * 0.08, h * 0.65);
      ctx.bezierCurveTo(w * 0.18, h * 0.05, w * 0.25, h * 0.95, w * 0.36, h * 0.45);
      ctx.bezierCurveTo(w * 0.45, h * 0.1, w * 0.52, h * 0.8, w * 0.62, h * 0.5);
      ctx.bezierCurveTo(w * 0.7, h * 0.3, w * 0.8, h * 0.7, w * 0.9, h * 0.35);
      ctx.stroke();
      inked = true;
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

  const values = Object.fromEntries([...document.querySelectorAll("#maker-fields input")].map((i) => [i.dataset.key, i.value]));
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
  const attach = "Attach: " + card.attachments.map((a, i) => `(${i + 1}) ${a.en}`).join(", ");
  fitFont(ctx, attach, W - 80, 17, "Arial, sans-serif");
  ctx.fillText(attach, 40, y);

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

/* ---------- running a check ---------- */

function resetTrace() {
  const trace = $("#trace");
  trace.innerHTML = "";
  for (const id of STEP_ORDER) {
    const li = document.createElement("li");
    li.id = `step-${id}`;
    li.className = "waiting";
    li.innerHTML = `<span class="t-title">${STEP_TEXT[id][0]}<span class="en">${STEP_TEXT[id][1]}</span></span>
      <span class="t-state">অপেক্ষায়</span><span class="t-meta"></span>`;
    trace.append(li);
  }
}

function whoRan(event) {
  if (event.kind === "code") return `<span class="who">কোড</span> (${esc(event.tool)}), নিয়ম অনুযায়ী, কোনো AI নয়`;
  const where = event.backend === "ollama" ? "local Ollama" : "Google AI Studio";
  return `<span class="who">Gemma 4 · ${esc(event.model)}</span> on ${where}`;
}

function onStep(event) {
  const li = $(`#step-${event.id}`);
  if (!li) return;
  const meta = li.querySelector(".t-meta");
  if (event.status === "start") {
    li.className = "running";
    li.querySelector(".t-state").textContent = "চলছে…";
    meta.innerHTML = whoRan(event);
    return;
  }
  li.className = "done";
  li.querySelector(".t-state").textContent = "হয়েছে ✓";
  const ms = event.ms ? `, ${(event.ms / 1000).toFixed(1)} s` : "";
  const retried = event.retried ? ", ফরম্যাট ঠিক করতে একবার আবার চেষ্টা" : "";
  meta.innerHTML = whoRan(event) + ms + retried;
  const details = document.createElement("details");
  details.innerHTML = `<summary>মডেল/কোডের আসল আউটপুট দেখুন (raw output)</summary><pre>${esc(JSON.stringify(event.output, null, 2))}</pre>`;
  li.append(details);
}

async function runCheck() {
  const engine = selectedEngine();
  if (!state.blob || !engine) return;
  const btn = $("#check-btn");
  btn.disabled = true;
  $("#result").innerHTML = "";
  $("#stamp").hidden = true;
  resetTrace();
  // On a phone the steps panel sits below the button; bring it into view so the run is visible.
  if (window.matchMedia("(max-width: 919px)").matches) $(".slip").scrollIntoView({ behavior: "smooth", block: "start" });
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
    showError(`নেটওয়ার্ক সমস্যা। Network problem: ${err.message}`);
  } finally {
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
    li.querySelector(".t-state").textContent = "ব্যর্থ ✗";
  }
  $("#result").innerHTML = `<div class="error"><strong>যাচাই শেষ করা যায়নি।</strong> The check could not finish.<br>${esc(message)}</div>`;
}

function stamp(status, count) {
  const v = VERDICT[status];
  const el = $("#stamp");
  el.className = `stamp ${v.cls}`;
  el.innerHTML = `${v.bn}<span class="en">${esc(v.en(count))}</span>`;
  el.hidden = false;
}

function renderResult(r) {
  for (const id of STEP_ORDER) {
    const li = $(`#step-${id}`);
    if (li && li.className === "waiting") {
      li.className = "skipped";
      li.querySelector(".t-state").textContent = "দরকার হয়নি";
    }
  }
  const count = (r.problems || []).length;
  stamp(r.status, count);
  const v = VERDICT[r.status];
  const parts = [];
  if (r.status === "unknown_form") {
    parts.push(`<p class="verdict">${v.bn}</p><p class="verdict-en">FormBondhu only checks forms it has rules for, so it does not guess. It read the title as "${esc(r.form_title)}".</p>`);
    parts.push(`<h3>যে ফর্মগুলো চেনে<span class="en">Forms it knows</span></h3><ul class="docs">${r.known.map((k) => `<li>${esc(k.title_bn)} <span class="en">${esc(k.title_en)}</span></li>`).join("")}</ul>`);
  } else {
    const headline = r.status === "problems" ? `${bnDigits(count)}টি কারণে ফর্মটি ফেরত আসবে` : v.bn;
    parts.push(`<span class="badge">নমুনা নিয়ম / sample rules</span>`);
    parts.push(`<p class="verdict ${v.cls}">${headline}</p><p class="verdict-en">${esc(r.card.title_en)}: ${esc(v.en(count))}</p>`);
    if (count) {
      parts.push(`<h3>যা ঠিক করতে হবে<span class="en">Fix before you go</span></h3><ul class="problems">${r.problems.map(problemItem).join("")}</ul>`);
    }
    if ((r.manual || []).length) {
      parts.push(`<h3>নিজে একবার দেখুন<span class="en">The second look could not confirm these</span></h3><ul class="problems manual">${r.manual.map(problemItem).join("")}</ul>`);
    }
    parts.push(`<h3>সাথে যা নিতে হবে<span class="en">Bring with the form</span></h3><ul class="docs">${r.attachments.map((a) => `<li>${esc(a.bn)} <span class="en">${esc(a.en)}</span></li>`).join("")}</ul>`);
    parts.push(`<h3>কোন অফিসে, কোন ক্রমে<span class="en">Where to go, in order</span></h3><ol class="route">${r.route.map((s) => `<li><span class="office">${esc(s.office_bn)} <span class="en">${esc(s.office_en)}</span></span><span>${esc(s.task_bn)} <span class="en">${esc(s.task_en)}</span></span></li>`).join("")}</ol>`);
    if ((r.passed || []).length) {
      parts.push(`<details class="passed"><summary>${bnDigits(r.passed.length)}টি নিয়ম ঠিক আছে (${r.passed.length} rules passed)</summary><ul>${r.passed.map((p) => `<li>${esc(p.rule_id)}: ${esc(p.label_bn)} / ${esc(p.label_en)}</li>`).join("")}</ul></details>`);
    }
  }
  const where = r.engine.backend === "ollama" ? "local Ollama" : "Google AI Studio";
  parts.push(`<p class="run-meta">মডেল: Gemma 4 (${esc(r.engine.model)}) on ${where}. মোট সময় ${(r.ms / 1000).toFixed(1)} সেকেন্ড.</p>`);
  $("#result").innerHTML = parts.join("");
}

function problemItem(p) {
  const seen = p.seen ? `<p class="seen">Gemma যা দেখেছে: “${esc(p.seen)}”</p>` : "";
  return `<li><div class="where"><span>${esc(p.label_bn)} / ${esc(p.label_en)}</span><span class="rid">${esc(p.rule_id)}</span></div>
    <p class="fix">${esc(p.fix_bn)}</p><p class="fix-en">${esc(p.fix_en)}</p>${seen}</li>`;
}

init().catch((err) => showError(`অ্যাপ চালু হয়নি। Could not start: ${err.message}`));

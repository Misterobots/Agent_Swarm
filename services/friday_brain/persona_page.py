"""Self-contained persona-editor page served by friday_brain at GET /personas.

No external assets (LAN-first, works offline). Talks to the CRUD API on the same origin. If a
FRIDAY_PERSONA_TOKEN is configured, the page prompts for it once and sends it as X-Persona-Token
on every API call (also accepted as ?token= for a bookmarkable link).
"""

PERSONA_EDITOR_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Friday — Personas</title>
<style>
  :root {
    --bg: #0e1116; --panel: #171b22; --panel2: #1e232c; --border: #2a313c;
    --text: #e6e9ef; --muted: #9aa4b2; --accent: #6ea8fe; --accent2: #3b82f6;
    --ok: #3fb950; --danger: #f85149;
  }
  @media (prefers-color-scheme: light) {
    :root {
      --bg: #f5f7fa; --panel: #ffffff; --panel2: #f0f3f7; --border: #d8dee6;
      --text: #1b2027; --muted: #5b6470; --accent: #2563eb; --accent2: #1d4ed8;
    }
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--text);
    font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
  header { padding: 20px 24px; border-bottom: 1px solid var(--border);
    display: flex; align-items: baseline; gap: 14px; flex-wrap: wrap; }
  header h1 { margin: 0; font-size: 20px; letter-spacing: .2px; }
  header .sub { color: var(--muted); font-size: 13px; }
  .wrap { max-width: 1100px; margin: 0 auto; padding: 20px 24px 60px; }
  .tokenbar { display: flex; gap: 8px; align-items: center; margin: 6px 0 18px; flex-wrap: wrap; }
  .tokenbar input { flex: 1; min-width: 160px; }
  .brand { color: var(--accent); font-weight: 700; }
  .cards { display: grid; gap: 22px; grid-template-columns: 1fr; }
  @media (min-width: 900px) { .cards { grid-template-columns: 1fr 1fr; } }
  .card { background: var(--panel); border: 1px solid var(--border); border-radius: 14px; overflow: hidden; }
  .card h2 { margin: 0; padding: 16px 18px; font-size: 17px; background: var(--panel2);
    border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; gap: 8px; }
  .card h2 .model { font-size: 11px; color: var(--muted); font-weight: 400; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
  .card .body { padding: 16px 18px; }
  label { display: block; font-size: 12px; text-transform: uppercase; letter-spacing: .6px;
    color: var(--muted); margin: 14px 0 5px; }
  label:first-child { margin-top: 0; }
  input[type=text], textarea, input[type=password] {
    width: 100%; background: var(--panel2); color: var(--text); border: 1px solid var(--border);
    border-radius: 9px; padding: 9px 11px; font: inherit; }
  textarea { resize: vertical; min-height: 62px; }
  .hint { font-size: 11px; color: var(--muted); margin-top: 4px; text-transform: none; letter-spacing: 0; }
  .row { display: flex; gap: 12px; flex-wrap: wrap; }
  .row > div { flex: 1; min-width: 140px; }
  .refs { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 8px; }
  .ref { position: relative; width: 92px; }
  .ref img { width: 92px; height: 92px; object-fit: cover; border-radius: 9px; border: 1px solid var(--border);
    background: var(--panel2); display: block; }
  .ref.selfimg img { border-color: var(--ok); box-shadow: 0 0 0 2px var(--ok); }
  .ref .cap { font-size: 10px; color: var(--muted); margin-top: 3px; word-break: break-all; text-align: center; }
  .ref .mark { display: block; width: 100%; margin-top: 4px; font-size: 10px; padding: 3px 0; cursor: pointer;
    background: var(--panel2); border: 1px solid var(--border); border-radius: 6px; color: var(--muted); }
  .ref.selfimg .mark { color: var(--ok); border-color: var(--ok); }
  .actions { display: flex; gap: 10px; align-items: center; margin-top: 18px; flex-wrap: wrap; }
  button { background: var(--accent2); color: #fff; border: 0; border-radius: 9px; padding: 9px 16px;
    font: inherit; font-weight: 600; cursor: pointer; }
  button.ghost { background: transparent; color: var(--accent); border: 1px solid var(--border); }
  button:disabled { opacity: .5; cursor: default; }
  .status { font-size: 13px; color: var(--muted); }
  .status.ok { color: var(--ok); } .status.err { color: var(--danger); }
  .uploadwrap { display: flex; align-items: center; gap: 10px; margin-top: 8px; }
  input[type=file] { font-size: 12px; color: var(--muted); }
  .globalmsg { padding: 10px 14px; border-radius: 9px; margin-bottom: 16px; display: none; }
  .globalmsg.err { display: block; background: rgba(248,81,73,.12); color: var(--danger); border: 1px solid var(--danger); }
</style>
</head>
<body>
<header>
  <h1><span class="brand">Friday</span> · Persona Studio</h1>
  <span class="sub">Two brains, two assistants — edit each one's voice, character, memory, and look.</span>
</header>
<div class="wrap">
  <div class="tokenbar" id="tokenbar" style="display:none">
    <label style="margin:0">Access token</label>
    <input type="password" id="token" placeholder="FRIDAY_PERSONA_TOKEN" autocomplete="off">
    <button class="ghost" onclick="saveToken()">Use token</button>
  </div>
  <div class="globalmsg" id="globalmsg"></div>
  <div class="cards" id="cards"></div>
</div>

<script>
const $ = (id) => document.getElementById(id);
let TOKEN = new URLSearchParams(location.search).get("token") || sessionStorage.getItem("friday_persona_token") || "";

function headers(extra) {
  const h = Object.assign({}, extra || {});
  if (TOKEN) h["X-Persona-Token"] = TOKEN;
  return h;
}
function saveToken() {
  TOKEN = $("token").value.trim();
  sessionStorage.setItem("friday_persona_token", TOKEN);
  load();
}
function esc(s) { return (s == null ? "" : String(s)).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c])); }
function modelPath(model) { return "/api/personas/" + model.split("/").map(encodeURIComponent).join("/"); }

async function load() {
  $("globalmsg").className = "globalmsg";
  try {
    const r = await fetch("/api/personas", { headers: headers() });
    if (r.status === 401) { showTokenBar("A token is required to view or edit personas."); return; }
    if (!r.ok) throw new Error("HTTP " + r.status);
    const data = await r.json();
    render(data.personas || data);
  } catch (e) {
    $("globalmsg").className = "globalmsg err";
    $("globalmsg").textContent = "Could not load personas: " + e.message;
  }
}
function showTokenBar(msg) {
  $("tokenbar").style.display = "flex";
  $("globalmsg").className = "globalmsg err";
  $("globalmsg").textContent = msg;
}

function render(personas) {
  const cards = $("cards");
  cards.innerHTML = "";
  const entries = Array.isArray(personas) ? personas : Object.entries(personas).map(([model, p]) => ({ model, ...p }));
  entries.forEach(p => cards.appendChild(cardFor(p)));
}

function cardFor(p) {
  const model = p.model;
  const el = document.createElement("div");
  el.className = "card";
  const refs = (p.visual_refs || []).map(r => {
    const url = modelPath(model) + "/visual_ref/" + encodeURIComponent(r.name) + (TOKEN ? "?token=" + encodeURIComponent(TOKEN) : "");
    return `<div class="ref ${r.self_image ? "selfimg" : ""}">
      <img src="${url}" alt="${esc(r.name)}" loading="lazy">
      <div class="cap">${esc(r.name)}</div>
      <span class="mark" data-name="${esc(r.name)}">${r.self_image ? "★ self-image" : "set self-image"}</span>
    </div>`;
  }).join("");
  el.innerHTML = `
    <h2><span>${esc(p.display_name || "(unnamed)")}</span><span class="model">${esc(model)}</span></h2>
    <div class="body">
      <label>Display name</label>
      <input type="text" data-f="display_name" value="${esc(p.display_name)}">
      <label>Nationality &amp; voice</label>
      <textarea data-f="nationality_voice">${esc(p.nationality_voice)}</textarea>
      <label>Attitude</label>
      <textarea data-f="attitude">${esc(p.attitude)}</textarea>
      <label>Traits <span class="hint">(comma-separated)</span></label>
      <input type="text" data-f="traits" value="${esc((p.traits || []).join(", "))}">
      <label>Appearance <span class="hint">(used to seed a self-portrait)</span></label>
      <textarea data-f="appearance">${esc(p.appearance)}</textarea>
      <label>Backstory</label>
      <textarea data-f="backstory" style="min-height:110px">${esc(p.backstory)}</textarea>
      <div class="row">
        <div>
          <label>Memory namespace <span class="hint">(blank = shared base memory)</span></label>
          <input type="text" data-f="memory_namespace" value="${esc(p.memory_namespace)}">
        </div>
      </div>
      <label>Visual references</label>
      <div class="refs">${refs || '<span class="hint">No images yet.</span>'}</div>
      <div class="uploadwrap">
        <input type="file" accept="image/*" data-upload>
        <button class="ghost" data-uploadbtn>Upload image</button>
      </div>
      <div class="actions">
        <button data-save>Save persona</button>
        <span class="status" data-status></span>
      </div>
    </div>`;

  const status = el.querySelector("[data-status]");
  el.querySelector("[data-save]").onclick = () => save(model, el, status);
  el.querySelector("[data-uploadbtn]").onclick = () => upload(model, el, status);
  el.querySelectorAll(".mark").forEach(m => m.onclick = () => setSelf(model, m.dataset.name, status));
  return el;
}

function collect(el) {
  const out = {};
  el.querySelectorAll("[data-f]").forEach(i => {
    const f = i.dataset.f;
    if (f === "traits") out[f] = i.value.split(",").map(s => s.trim()).filter(Boolean);
    else out[f] = i.value;
  });
  return out;
}

async function save(model, el, status) {
  status.className = "status"; status.textContent = "Saving…";
  try {
    const r = await fetch(modelPath(model), {
      method: "PUT", headers: headers({ "Content-Type": "application/json" }),
      body: JSON.stringify(collect(el)),
    });
    if (r.status === 401) { status.className = "status err"; status.textContent = "Unauthorized — set token."; showTokenBar("A token is required."); return; }
    if (!r.ok) throw new Error("HTTP " + r.status);
    status.className = "status ok"; status.textContent = "Saved. Applies on the next turn — no restart.";
  } catch (e) { status.className = "status err"; status.textContent = "Save failed: " + e.message; }
}

async function upload(model, el, status) {
  const input = el.querySelector("[data-upload]");
  if (!input.files || !input.files[0]) { status.className = "status err"; status.textContent = "Pick an image first."; return; }
  status.className = "status"; status.textContent = "Uploading…";
  const fd = new FormData();
  fd.append("file", input.files[0]);
  try {
    const r = await fetch(modelPath(model) + "/visual_ref", { method: "POST", headers: headers(), body: fd });
    if (r.status === 401) { status.className = "status err"; status.textContent = "Unauthorized — set token."; return; }
    if (!r.ok) throw new Error("HTTP " + r.status);
    status.className = "status ok"; status.textContent = "Uploaded.";
    load();
  } catch (e) { status.className = "status err"; status.textContent = "Upload failed: " + e.message; }
}

async function setSelf(model, name, status) {
  status.className = "status"; status.textContent = "Updating…";
  try {
    // Read current, flip self_image flags, PUT back.
    const r = await fetch(modelPath(model), { headers: headers() });
    const p = await r.json();
    const refs = (p.visual_refs || []).map(x => ({ ...x, self_image: x.name === name }));
    const w = await fetch(modelPath(model), {
      method: "PUT", headers: headers({ "Content-Type": "application/json" }),
      body: JSON.stringify({ visual_refs: refs }),
    });
    if (!w.ok) throw new Error("HTTP " + w.status);
    status.className = "status ok"; status.textContent = "Self-image set.";
    load();
  } catch (e) { status.className = "status err"; status.textContent = "Failed: " + e.message; }
}

if (TOKEN) sessionStorage.setItem("friday_persona_token", TOKEN);
load();
</script>
</body>
</html>
"""

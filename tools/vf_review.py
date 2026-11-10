"""Review page (video + visual timeline + client notes) and editor timeline export for video-factory.

The page is one static HTML file next to the video: no server. The edit's tracks come from
renders/<name>.timeline.json (written by every render) and are embedded in the page, because a
browser will not read a separate local file. Changes made on the page (part order, transitions,
notes) cannot be written back to disk without a server, so they leave as a text request to copy
or save, which Claude applies to story.json.
"""
from __future__ import annotations

import html
import json
import sys
import urllib.parse
from pathlib import Path

REVIEW_HTML = r"""<!doctype html>
<html lang="__LANG__" dir="__DIR__">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ — review</title>
<style>
  :root { --bg:#f6f5f2; --card:#fff; --ink:#1c1c1c; --muted:#6b6b6b; --line:#e2e0da; --accent:#c8551f;
          --foot:#3b6ea8; --motion:#8a5cc2; --ov:#2e9c74; --broll:#c99a2e; --cap:#7a7a7a; --aud:#4a8f9c; --sel:#ffd24a; }
  @media (prefers-color-scheme: dark) { :root { --bg:#141414; --card:#1e1e1e; --ink:#eee; --muted:#9a9a9a; --line:#333;
          --accent:#ff8a4c; --foot:#4f86c6; --motion:#a47ad8; --ov:#3cb88b; --broll:#d9ad45; --cap:#8d8d8d; --aud:#5aa7b5; } }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--ink); font:15px/1.5 system-ui, "Segoe UI", Arial, sans-serif; }
  main { max-width: 1180px; margin: 0 auto; padding: 20px 16px 64px; }
  h1 { font-size: 21px; margin: 0 0 2px; } h2 { font-size: 16px; margin: 22px 0 8px; }
  .sub, .hint { color: var(--muted); font-size: 13px; margin: 0 0 14px; }
  video { width: 100%; max-height: 62vh; background:#000; border-radius: 10px; display:block; }
  button, select { font: inherit; }
  button { padding:8px 14px; border:0; border-radius:8px; background:var(--accent); color:#fff; cursor:pointer; }
  button.ghost { background:transparent; color:var(--ink); border:1px solid var(--line); }
  .bar { display:flex; gap:8px; margin:10px 0; flex-wrap: wrap; align-items: center; }
  /* timeline: time runs left to right, as in every editor */
  .tl-wrap { direction:ltr; background:var(--card); border:1px solid var(--line); border-radius:10px; overflow-x:auto; }
  .tl { position:relative; padding: 0 0 6px 92px; min-width: 100%; }
  .ruler { position:relative; height:22px; border-bottom:1px solid var(--line); font-size:11px; color:var(--muted); }
  .tick { position:absolute; top:0; height:100%; border-left:1px solid var(--line); padding-left:3px; }
  .track { position:relative; height:34px; border-bottom:1px dashed var(--line); }
  .track.parts { height:46px; }
  .tname { position:absolute; left:-92px; width:86px; top:0; bottom:0; display:flex; align-items:center;
           font-size:12px; color:var(--muted); direction:rtl; justify-content:flex-start; padding-right:6px; }
  .clip { position:absolute; top:5px; bottom:5px; border-radius:6px; color:#fff; font-size:11px; padding:2px 6px;
          overflow:hidden; white-space:nowrap; text-overflow:ellipsis; cursor:pointer; unicode-bidi:plaintext; text-align:start;
          box-shadow: inset 0 0 0 1px rgba(0,0,0,.15); }
  .clip.footage { background:var(--foot); } .clip.motion { background:var(--motion); }
  .clip.ov { background:var(--ov); } .clip.broll { background:var(--broll); } .clip.cap { background:var(--cap); }
  .clip.aud { background:var(--aud); }
  .clip.sel { outline: 3px solid var(--sel); }
  .clip.dragging { opacity:.4; }
  .clip.drop { outline: 3px dashed var(--sel); }
  .junc { position:absolute; top:-1px; transform:translateX(-50%); z-index:3; font-size:10px; background:var(--card);
          color:var(--ink); border:1px solid var(--line); border-radius:10px; padding:0 6px; cursor:pointer; white-space:nowrap; }
  .junc.changed { border-color: var(--accent); color: var(--accent); font-weight:600; }
  .playhead { position:absolute; top:0; bottom:0; width:2px; background:var(--accent); z-index:4; pointer-events:none; }
  .info { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:10px 12px; min-height: 44px; }
  .info b { color: var(--accent); }
  textarea { width:100%; min-height: 56px; padding:10px; border:1px solid var(--line); border-radius:8px;
             background:var(--card); color:var(--ink); font:inherit; }
  ol { padding:0; list-style:none; margin: 0; }
  li { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:8px 12px; margin:6px 0;
       display:flex; gap:12px; align-items:flex-start; }
  .t { font-variant-numeric: tabular-nums; color: var(--accent); cursor:pointer; direction:ltr; min-width: 58px; }
  .x { margin-inline-start:auto; background:none; color:var(--muted); padding:0 4px; }
  .legend { display:flex; gap:12px; flex-wrap:wrap; font-size:12px; color:var(--muted); margin:6px 0; }
  .legend span::before { content:""; display:inline-block; width:10px; height:10px; border-radius:3px; margin-left:4px;
                         vertical-align:-1px; background: var(--c); }
  dialog { border:1px solid var(--line); border-radius:10px; background:var(--card); color:var(--ink); }
  pre { white-space: pre-wrap; unicode-bidi: plaintext; text-align:start; background:var(--bg); padding:10px; border-radius:8px;
        border:1px solid var(--line); font-size:12px; max-height: 220px; overflow:auto; }
</style>
</head>
<body>
<main>
  <h1>__TITLE__</h1>
  <p class="sub"><span id="subname">__VIDEO_NAME__</span> · __DURATION__ <span data-i18n="sec"></span> · <span data-i18n="sub"></span></p>
  <video id="v" src="__VIDEO__" controls preload="metadata"></video>

  <div class="bar" style="justify-content:space-between"><h2 data-i18n="timeline"></h2><button class="ghost" id="lang" style="padding:4px 10px"></button></div>
  <div class="bar">
    <label><span data-i18n="zoom"></span> <input id="zoom" type="range" min="20" max="240" value="70"></label>
    <span class="legend">
      <span style="--c:var(--foot)" data-i18n="footage"></span><span style="--c:var(--motion)" data-i18n="graphics"></span>
      <span style="--c:var(--ov)" data-i18n="overlay"></span><span style="--c:var(--broll)" data-i18n="broll"></span>
      <span style="--c:var(--cap)" data-i18n="captions"></span><span style="--c:var(--aud)" data-i18n="audio"></span>
    </span>
  </div>
  <div class="tl-wrap"><div class="tl" id="tl"></div></div>
  <p class="hint" data-i18n="tlHint"></p>
  <div class="info" id="info" data-i18n="pick"></div>

  <h2 data-i18n="notes"></h2>
  <textarea id="note"></textarea>
  <div class="bar"><button id="add" data-i18n="add"></button></div>
  <ol id="list"></ol>

  <h2 data-i18n="send"></h2>
  <pre id="out"></pre>
  <div class="bar">
    <button id="copy" data-i18n="copy"></button>
    <button class="ghost" id="save" data-i18n="saveFile"></button>
    <button class="ghost" id="reset" data-i18n="reset"></button>
  </div>
  <p class="hint" data-i18n="storeHint"></p>
</main>
<dialog id="dlg"><form method="dialog">
  <p style="margin-top:0"><span data-i18n="trBefore"></span> <b id="dlgPart"></b></p>
  <div class="bar"><select id="dlgType"></select>
  <label><span data-i18n="dur"></span> <input id="dlgDur" type="number" min="0" max="3" step="0.1" style="width:70px"></label></div>
  <div class="bar"><button value="ok" data-i18n="ok"></button><button class="ghost" value="cancel" data-i18n="cancel"></button></div>
</form></dialog>
<script type="application/json" id="data">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById("data").textContent || "{}");
const I18N = {
  he: { timeline: "ציר הזמן", zoom: "זום", footage: "חומר מצולם", graphics: "גרפיקה", overlay: "שכבה עליונה",
        broll: "צילומי אווירה", captions: "כתוביות", audio: "שמע", parts: "חלקים", overlays: "שכבות", brollTrack: "אווירה",
        tlHint: "לחיצה על הציר קופצת לרגע. גררו חלק כדי לשנות את הסדר. לחיצה על תווית מעבר משנה אותו.",
        pick: "בחרו חלק כדי לראות פרטים.", notes: "הערות", notePh: "הערה לרגע הזה בסרטון… (הסרטון נעצר כשכותבים)",
        add: "הוסף הערה בזמן הנוכחי", send: "לשלוח לעורך", copy: "העתק", saveFile: "שמור כקובץ", reset: "בטל שינויים בציר",
        storeHint: "ההערות והשינויים נשמרים בדפדפן הזה בלבד. בסיום: \"העתק\" או \"שמור כקובץ\", ושלחו לעורך.",
        trBefore: "מעבר לפני החלק", dur: "משך", ok: "שמור", cancel: "ביטול", cut: "חיתוך", sec: "שנ׳",
        sub: "ציר זמן, הערות ושינויים לעורך", part: "חלק", source: "מקור", inEdit: "בעריכה", why: "למה כאן",
        graphic: "גרפיקה", del: "מחק", copyPrompt: "העתיקו:", none: "none (חיתוך)", other: "English" },
  en: { timeline: "Timeline", zoom: "Zoom", footage: "Footage", graphics: "Graphics", overlay: "Overlay",
        broll: "B-roll", captions: "Captions", audio: "Audio", parts: "Parts", overlays: "Overlays", brollTrack: "B-roll",
        tlHint: "Click the timeline to jump there. Drag a part to reorder. Click a transition label to change it.",
        pick: "Select a part to see its details.", notes: "Notes", notePh: "A note for this moment… (the video pauses while you type)",
        add: "Add a note at the current time", send: "Send to the editor", copy: "Copy", saveFile: "Save as file", reset: "Undo timeline changes",
        storeHint: "Notes and changes stay in this browser only. When done: \"Copy\" or \"Save as file\", and send it to the editor.",
        trBefore: "Transition into part", dur: "Duration", ok: "Save", cancel: "Cancel", cut: "cut", sec: "s",
        sub: "timeline, notes and changes for the editor", part: "Part", source: "Source", inEdit: "In the edit", why: "Why here",
        graphic: "graphic", del: "Delete", copyPrompt: "Copy:", none: "none (cut)", other: "עברית" } };
let LANG = "__LANG__";
try { LANG = localStorage.getItem("vf-review-lang") || LANG; } catch (e) {}
const L = k => (I18N[LANG] || I18N.he)[k] || k;
function applyLang() {
  document.documentElement.lang = LANG; document.documentElement.dir = LANG === "he" ? "rtl" : "ltr";
  document.querySelectorAll("[data-i18n]").forEach(e => { e.textContent = L(e.dataset.i18n); });
  document.getElementById("note").placeholder = L("notePh");
  document.getElementById("lang").textContent = L("other");
}
const KEY = "vf-review-__KEY__";
const v = document.getElementById("v"), tl = document.getElementById("tl"), info = document.getElementById("info");
const fmt = s => { const m = Math.floor(s / 60), r = (s % 60).toFixed(1).padStart(4, "0"); return m + ":" + r; };
let st = { notes: [], order: null, transitions: {} };
try { st = Object.assign(st, JSON.parse(localStorage.getItem(KEY) || "{}")); } catch (e) {}
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(st)); } catch (e) {} };
const T = D.tracks || {};
const parts = T.parts || [];
const origOrder = parts.map(p => p.id);
if (!st.order || st.order.length !== origOrder.length) st.order = origOrder.slice();
let pps = 70, playhead, selected = null;

function el(tag, cls, style, text) { const e = document.createElement(tag); if (cls) e.className = cls;
  if (style) Object.assign(e.style, style); if (text != null) e.textContent = text; return e; }
function seek(t) { v.currentTime = Math.max(0, t); }
function draw() {
  tl.innerHTML = "";
  const dur = D.duration || v.duration || 1;
  tl.style.width = (dur * pps + 110) + "px";
  const ruler = el("div", "ruler"); tl.append(ruler);
  const step = pps > 120 ? 1 : pps > 50 ? 2 : pps > 30 ? 5 : 10;
  for (let t = 0; t <= dur; t += step) ruler.append(el("div", "tick", { left: (t * pps) + "px" }, fmt(t).replace(/\.0$/, "")));
  ruler.addEventListener("click", e => seek((e.offsetX + (e.target === ruler ? 0 : e.target.offsetLeft)) / pps));
  // parts in the (possibly reordered) order: positions are the original ones, labels follow the new order
  const tr = el("div", "track parts"); tr.append(el("div", "tname", null, L("parts")));
  const byId = Object.fromEntries(parts.map(p => [p.id, p]));
  let x = 0;
  st.order.forEach((id, i) => {
    const p = byId[id]; if (!p) return;
    const changedOrder = st.order.join() !== origOrder.join();
    const left = changedOrder ? x : p.start;
    const c = el("div", "clip " + p.kind + (selected === id ? " sel" : ""), { left: left * pps + "px", width: Math.max(4, p.length * pps - 2) + "px" },
                 (p.title ? p.title + " · " : "") + p.id);
    c.title = p.id + " — " + p.label + " (" + p.length.toFixed(2) + "s)";
    c.draggable = true; c.dataset.id = id;
    c.onclick = () => { selected = id; seek(p.start); show(p); draw(); };
    c.ondragstart = e => { c.classList.add("dragging"); e.dataTransfer.setData("text/plain", id); };
    c.ondragend = () => c.classList.remove("dragging");
    c.ondragover = e => { e.preventDefault(); c.classList.add("drop"); };
    c.ondragleave = () => c.classList.remove("drop");
    c.ondrop = e => { e.preventDefault(); const from = e.dataTransfer.getData("text/plain"); if (from === id) return;
      const o = st.order.filter(k => k !== from); o.splice(o.indexOf(id), 0, from); st.order = o; save(); draw(); out(); };
    tr.append(c);
    if (i > 0) {
      const t0 = st.transitions[id] || p.transition_in || { type: "fade", duration: 0.5 };
      const j = el("div", "junc" + (st.transitions[id] ? " changed" : ""), { left: left * pps + "px" },
                   t0.type === "none" || t0.duration < 0.05 ? L("cut") : t0.type + " " + (+t0.duration).toFixed(1));
      j.onclick = ev => { ev.stopPropagation(); editTransition(id, t0); };
      tr.append(j);
    }
    x = left + p.length - (i + 1 < st.order.length ? ((byId[st.order[i + 1]] || {}).transition_in || { duration: 0 }).duration : 0);
  });
  tl.append(tr);
  for (const [key, name, cls] of [["overlays", L("overlays"), "ov"], ["broll", L("brollTrack"), "broll"], ["captions", L("captions"), "cap"], ["audio", L("audio"), "aud"]]) {
    const items = (T[key] || []).slice().sort((a, b) => b.length - a.length); if (!items.length) continue;
    // overlapping items go to separate lanes, so a whole-video logo never hides a lower third
    const lanes = [];
    items.sort((a, b) => a.start - b.start).forEach(it => {
      let k = lanes.findIndex(end => end <= it.start + 0.01); if (k < 0) { k = lanes.length; lanes.push(0); }
      lanes[k] = it.start + it.length; it._lane = k; });
    const row = el("div", "track", { height: (8 + 28 * lanes.length) + "px" }); row.append(el("div", "tname", null, name));
    items.forEach(it => { const c = el("div", "clip " + cls, { left: it.start * pps + "px", width: Math.max(3, it.length * pps - 1) + "px",
        top: (4 + 28 * it._lane) + "px", bottom: "auto", height: "24px" }, it.label);
      c.title = fmt(it.start) + " · " + it.label; c.onclick = () => seek(it.start); row.append(c); });
    tl.append(row);
  }
  tl.onclick = e => { if (e.target === tl || e.target.classList.contains("track")) seek((e.clientX - tl.getBoundingClientRect().left - 92) / pps); };
  playhead = el("div", "playhead", { left: (92 + v.currentTime * pps) + "px" }); tl.append(playhead);
}
function show(p) {
  info.innerHTML = "";
  const add = (k, val) => { if (!val) return; const d = document.createElement("div"); const b = document.createElement("b"); b.textContent = k + ": ";
    d.append(b, document.createTextNode(val)); info.append(d); };
  add(L("part"), p.id + (p.title ? " — " + p.title : ""));
  add(L("source"), p.kind === "motion" ? L("graphic") + ": " + p.label : p.label + " " + fmt(p.src[0]) + "–" + fmt(p.src[1]));
  add(L("inEdit"), fmt(p.start) + " · " + p.length.toFixed(2) + " " + L("sec"));
  add(L("why"), p.why);
}
function editTransition(id, cur) {
  const dlg = document.getElementById("dlg"), sel = document.getElementById("dlgType"), dur = document.getElementById("dlgDur");
  document.getElementById("dlgPart").textContent = id;
  sel.innerHTML = ""; (D.transition_types || ["none", "fade", "dissolve", "fadeblack"]).forEach(t => sel.append(new Option(t === "none" ? L("none") : t, t)));
  sel.value = cur.type; dur.value = (+cur.duration || 0.5).toFixed(1);
  dlg.onclose = () => { if (dlg.returnValue === "ok") { st.transitions[id] = { type: sel.value, duration: sel.value === "none" ? 0 : +dur.value }; save(); draw(); out(); } };
  dlg.showModal();
}
v.addEventListener("timeupdate", () => { if (playhead) playhead.style.left = (92 + v.currentTime * pps) + "px"; });
v.addEventListener("loadedmetadata", draw);
document.getElementById("zoom").oninput = e => { pps = +e.target.value; draw(); };
// notes
const note = document.getElementById("note"), list = document.getElementById("list");
function drawNotes() {
  list.innerHTML = "";
  st.notes.sort((a, b) => a.t - b.t).forEach((n, i) => {
    const li = el("li"); const t = el("span", "t", null, fmt(n.t)); t.onclick = () => { seek(n.t); v.play(); };
    const x = el("button", "x", null, "✕"); x.title = L("del"); x.onclick = () => { st.notes.splice(i, 1); save(); drawNotes(); out(); };
    li.append(t, el("span", null, null, n.text), x); list.append(li);
  });
}
note.addEventListener("focus", () => v.pause());
document.getElementById("add").onclick = () => { const text = note.value.trim(); if (!text) return;
  st.notes.push({ t: Math.round(v.currentTime * 10) / 10, text }); note.value = ""; save(); drawNotes(); out(); };
// the request for the editor
function request() {
  const lines = ["# " + (D.title || "") + " — " + (D.video || "")];
  if (st.order.join() !== origOrder.join()) lines.push("order: " + st.order.join(", "));
  for (const [id, t] of Object.entries(st.transitions)) lines.push("transition into " + id + ": " + t.type + (t.type === "none" ? "" : " " + t.duration + "s"));
  st.notes.slice().sort((a, b) => a.t - b.t).forEach(n => lines.push(fmt(n.t) + " — " + n.text));
  if (lines.length === 1) lines.push("(no changes yet)");
  return lines.join("\n");
}
function out() { document.getElementById("out").textContent = request(); }
document.getElementById("copy").onclick = async () => { try { await navigator.clipboard.writeText(request()); } catch (e) { prompt(L("copyPrompt"), request()); } };
document.getElementById("save").onclick = () => { const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([request()], { type: "text/plain" })); a.download = "review-notes.txt"; a.click(); };
document.getElementById("reset").onclick = () => { st.order = origOrder.slice(); st.transitions = {}; save(); draw(); out(); };
document.getElementById("lang").onclick = () => { LANG = LANG === "he" ? "en" : "he";
  try { localStorage.setItem("vf-review-lang", LANG); } catch (e) {} applyLang(); draw(); if (selected) show(parts.find(p => p.id === selected)); };
applyLang(); draw(); drawNotes(); out();
</script>
</body>
</html>
"""


def write_review(proj: Path, video: Path, title: str, lang: str = "he") -> Path:
    out = video.parent / f"{video.stem}_review.html"
    tl = video.parent / f"{video.stem}.timeline.json"
    data = json.loads(tl.read_text(encoding="utf-8")) if tl.exists() else {"tracks": {}}
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    page = (REVIEW_HTML.replace("__TITLE__", html.escape(title))
            .replace("__VIDEO_NAME__", html.escape(video.name)).replace("__DURATION__", html.escape(str(data.get("duration", "")))).replace("__LANG__", "en" if lang == "en" else "he").replace("__DIR__", "ltr" if lang == "en" else "rtl")
            .replace("__VIDEO__", html.escape(urllib.parse.quote(video.name)))
            .replace("__KEY__", html.escape(f"{proj.name}-{video.stem}"))
            .replace("__DATA__", payload))
    out.write_text(page, encoding="utf-8")
    return out


def export_timeline(proj: Path, story: dict, clips: list[dict], transition: dict, dest: Path,
                    width: int, height: int, fps, skill_scripts: Path, run) -> None:
    """clips: [{"src": abs path, "in": s, "out": s}] in edit order -> .fcpxml / .edl / .otio via
    ffmpeg-skill's render.py --export-timeline (nothing is rendered)."""
    pj = {"output": str(proj / "renders" / "final.mp4"),
          "frame": {"width": width, "height": height, "fps": fps},
          "clips": [{"src": c["src"], "in": round(c["in"], 3), "out": round(c["out"], 3)} for c in clips],
          "transition": transition}
    pf = proj / "renders" / "timeline_project.json"
    pf.write_text(json.dumps(pj, ensure_ascii=False, indent=1), encoding="utf-8")
    r = run([sys.executable, skill_scripts / "render.py", pf, "--export-timeline", dest, "--overwrite"],
            capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("timeline export failed: " + ((r.stderr or r.stdout).strip().splitlines() or ["?"])[0])

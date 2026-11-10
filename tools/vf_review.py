"""Client review page and editor timeline export for video-factory."""
from __future__ import annotations

import html
import json
import subprocess
import sys
from pathlib import Path

REVIEW_HTML = """<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ — review</title>
<style>
  :root { --bg:#f6f5f2; --card:#fff; --ink:#1c1c1c; --muted:#6b6b6b; --line:#e2e0da; --accent:#c8551f; }
  @media (prefers-color-scheme: dark) { :root { --bg:#141414; --card:#1e1e1e; --ink:#eee; --muted:#9a9a9a; --line:#333; --accent:#ff8a4c; } }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--ink); font:16px/1.5 system-ui, "Segoe UI", Arial, sans-serif; }
  main { max-width: 1100px; margin: 0 auto; padding: 24px 16px 64px; }
  h1 { font-size: 22px; margin: 0 0 4px; } .sub { color: var(--muted); margin: 0 0 18px; }
  video { width: 100%; background:#000; border-radius: 10px; display:block; }
  .bar { display:flex; gap:8px; margin:14px 0; flex-wrap: wrap; }
  textarea { flex:1 1 320px; min-height: 64px; padding:10px; border:1px solid var(--line); border-radius:8px;
             background:var(--card); color:var(--ink); font:inherit; }
  button { padding:10px 16px; border:0; border-radius:8px; background:var(--accent); color:#fff; font:inherit; cursor:pointer; }
  button.ghost { background:transparent; color:var(--ink); border:1px solid var(--line); }
  ol { padding:0; list-style:none; margin: 0; }
  li { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:10px 12px; margin:8px 0;
       display:flex; gap:12px; align-items:flex-start; }
  .t { font-variant-numeric: tabular-nums; color: var(--accent); cursor:pointer; direction:ltr; min-width: 64px; }
  .x { margin-inline-start:auto; background:none; color:var(--muted); padding:0 4px; }
  .hint { color: var(--muted); font-size: 14px; }
</style>
</head>
<body>
<main>
  <h1>__TITLE__</h1>
  <p class="sub">__SUB__</p>
  <video id="v" src="__VIDEO__" controls preload="metadata"></video>
  <div class="bar">
    <textarea id="note" placeholder="הערה לרגע הזה בסרטון… (הסרטון נעצר כשכותבים)"></textarea>
    <button id="add">הוסף הערה בזמן הנוכחי</button>
  </div>
  <ol id="list"></ol>
  <div class="bar">
    <button id="copy">העתק את כל ההערות</button>
    <button class="ghost" id="save">שמור כקובץ</button>
  </div>
  <p class="hint">ההערות נשמרות בדפדפן הזה בלבד. בסיום: "העתק" או "שמור כקובץ", ושלחו לעורך.</p>
</main>
<script>
const KEY = "vf-review-__KEY__";
const v = document.getElementById("v"), note = document.getElementById("note"), list = document.getElementById("list");
let notes = [];
try { notes = JSON.parse(localStorage.getItem(KEY) || "[]"); } catch (e) { notes = []; }
const fmt = s => { const m = Math.floor(s / 60), r = (s % 60).toFixed(1).padStart(4, "0"); return m + ":" + r; };
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(notes)); } catch (e) {} };
function draw() {
  list.innerHTML = "";
  notes.sort((a, b) => a.t - b.t).forEach((n, i) => {
    const li = document.createElement("li");
    const t = document.createElement("span"); t.className = "t"; t.textContent = fmt(n.t); t.onclick = () => { v.currentTime = n.t; v.play(); };
    const p = document.createElement("span"); p.textContent = n.text;
    const x = document.createElement("button"); x.className = "x"; x.textContent = "✕"; x.title = "מחק";
    x.onclick = () => { notes.splice(i, 1); save(); draw(); };
    li.append(t, p, x); list.append(li);
  });
}
note.addEventListener("focus", () => v.pause());
document.getElementById("add").onclick = () => {
  const text = note.value.trim(); if (!text) return;
  notes.push({ t: Math.round(v.currentTime * 10) / 10, text }); note.value = ""; save(); draw();
};
const asText = () => notes.slice().sort((a, b) => a.t - b.t).map(n => fmt(n.t) + " — " + n.text).join("\\n");
document.getElementById("copy").onclick = async () => { try { await navigator.clipboard.writeText(asText()); } catch (e) { prompt("העתיקו:", asText()); } };
document.getElementById("save").onclick = () => {
  const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([asText()], { type: "text/plain" }));
  a.download = "review-notes.txt"; a.click();
};
draw();
</script>
</body>
</html>
"""


def write_review(proj: Path, video: Path, title: str) -> Path:
    out = video.parent / f"{video.stem}_review.html"
    page = (REVIEW_HTML.replace("__TITLE__", html.escape(title))
            .replace("__SUB__", html.escape(f"{video.name} · לחצו על זמן כדי לקפוץ אליו"))
            .replace("__VIDEO__", html.escape(video.name))
            .replace("__KEY__", html.escape(f"{proj.name}-{video.stem}")))
    out.write_text(page, encoding="utf-8")
    return out


def export_timeline(proj: Path, story: dict, clips: list[dict], transition: dict, dest: Path,
                    width: int, height: int, fps: int, skill_scripts: Path, run) -> None:
    """clips: [{"src": abs path, "in": s, "out": s}] in edit order -> .fcpxml / .edl / .otio via
    ffmpeg-skill's render.py --export-timeline (nothing is rendered)."""
    pj = {"output": str(proj / "renders" / "final.mp4"),
          "frame": {"width": width, "height": height, "fps": fps},
          "clips": [{"src": c["src"], "in": round(c["in"], 3), "out": round(c["out"], 3)} for c in clips],
          "transition": transition}
    pf = proj / "renders" / "timeline_project.json"
    pf.write_text(json.dumps(pj, ensure_ascii=False, indent=1), encoding="utf-8")
    r = run([sys.executable, skill_scripts / "render.py", pf, "--export-timeline", dest])
    if r.returncode != 0:
        sys.exit("timeline export failed")

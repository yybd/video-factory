#!/usr/bin/env python3
"""video-factory orchestrator CLI — the mechanical half of the video-orchestrator skill.

The skill (Claude) decides *what* to cut and in what order; this script does the
deterministic work around that decision:

  vf.py doctor                         check ffmpeg-full, ffmpeg-skill, whisper.cpp + model, Node
  vf.py new <name> <video|folder>...   create projects/<name>/ with the sources linked in (--copy to copy)
  vf.py transcribe <project>           transcript with WORD timings per source -> transcript/<src>.json
  vf.py transcript <project> [--words] print transcripts (and visual notes) as "[src mm:ss.ss-mm:ss.ss] text"
  vf.py frames <project> [--every N]   contact sheets with timecodes + scene list, for footage without speech
  vf.py scenes <project>               visual scene changes per source
  vf.py watch <project> [--task T]     a vision model's suggestions: shot log, clip scores, render QA
  vf.py status [project]               where each project stands, and the next step
  vf.py reference <project> <video>    study a video to imitate: pace, transitions, look, captions
  vf.py candidates <project>           moments that could stand alone as shorts, ranked for Claude to judge
  vf.py clips <project>                render clips.json as vertical shorts (captions, hook, brand)
  vf.py render <project> [--draft] [--version V]   story.json -> renders/final.mp4 (or draft / <version>)
  vf.py voice <project> --provider P   narration from script.md (ElevenLabs, Azure, Google, OpenAI, or macOS say)
  vf.py beats <project> <music>        tempo and beat grid, to cut on the music
  vf.py review <project>               a page for the client to leave timecoded notes
  vf.py export <project> [--format F]  the edit as a Resolve / Premiere / Final Cut timeline
  vf.py ff <tool> [args...]            run an ffmpeg-skill script with ffmpeg-full on PATH

Standard library only. Quiet by default; VF_VERBOSE=1 prints every underlying command.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_SCRIPTS = ROOT / ".claude" / "skills" / "ffmpeg-skill" / "scripts"
PROJECTS = ROOT / "projects"
FILLERS_HE = ROOT / "tools" / "fillers.he.txt"
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".mts"}

SNAP_PAD = 0.08      # silence kept before the first / after the last word of a cut
FILLER_PAD = 0.03    # extra trimmed around a removed filler word
MIN_KEEP = 0.12      # a kept sliver shorter than this is dropped


# ---------------------------------------------------------------- environment

def ffmpeg_full_bin() -> Path | None:
    """ffmpeg-full is keg-only in Homebrew, so it is never on PATH by itself."""
    env = os.environ.get("VF_FFMPEG_BIN")
    if env:
        return Path(env)
    for prefix in ("/opt/homebrew/opt/ffmpeg-full/bin", "/usr/local/opt/ffmpeg-full/bin"):
        if Path(prefix, "ffmpeg").exists():
            return Path(prefix)
    return None


def ffbin(name: str) -> str:
    b = ffmpeg_full_bin()
    return str(b / name) if b else name


def tool_env() -> dict:
    env = dict(os.environ)
    b = ffmpeg_full_bin()
    if b:
        env["PATH"] = f"{b}{os.pathsep}{env.get('PATH', '')}"
    return env


def whisper_model() -> Path | None:
    """A whisper.cpp ggml model. VF_WHISPER_MODEL wins; otherwise the ivrit.ai Hebrew models
    in the Hugging Face cache (large-v3 first: more accurate; turbo: ~3x faster)."""
    env = os.environ.get("VF_WHISPER_MODEL")
    if env:
        return Path(env).expanduser()
    hub = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub"
    for repo in ("models--ivrit-ai--whisper-large-v3-ggml", "models--ivrit-ai--whisper-large-v3-turbo-ggml"):
        hits = sorted(glob.glob(str(hub / repo / "snapshots" / "*" / "ggml-model.bin")))
        if hits:
            return Path(hits[-1])
    return None


def dtw_preset(model: Path) -> str | None:
    """whisper.cpp needs the model family's alignment heads to compute token timestamps (DTW)."""
    n = str(model).lower()
    for key, preset in (("large-v3-turbo", "large.v3.turbo"), ("turbo", "large.v3.turbo"),
                        ("large-v3", "large.v3"), ("large-v2", "large.v2"), ("large", "large.v3"),
                        ("medium", "medium"), ("small", "small"), ("base", "base"), ("tiny", "tiny")):
        if key in n:
            return preset
    return os.environ.get("VF_WHISPER_DTW")


VERBOSE = os.environ.get("VF_VERBOSE", "") not in ("", "0")


def run(cmd: list, **kw) -> subprocess.CompletedProcess:
    if VERBOSE:
        print("  $", " ".join(str(c) for c in cmd), file=sys.stderr)
    return subprocess.run([str(c) for c in cmd], env=tool_env(), **kw)


def ff(tool: str, *args) -> None:
    """Run one ffmpeg-skill script; stop on failure. Quiet unless VF_VERBOSE=1: its own command
    lines and JSON are shown only when it fails, with the reason it gave."""
    cmd = [sys.executable, SKILL_SCRIPTS / f"{tool}.py", *args]
    if VERBOSE:
        r = run(cmd)
    else:
        r = run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        reason = ""
        if not VERBOSE:
            out = (r.stdout or "") + (r.stderr or "")
            m = re.search(r'"message":\s*"([^"]+)"', out)
            reason = m.group(1) if m else out.strip().splitlines()[-1] if out.strip() else ""
            sys.stderr.write(out[-2500:] + "\n")
        sys.exit(f"ffmpeg-skill {tool} failed (exit {r.returncode})" + (f": {reason}" if reason else "")
                 + "\n  (run with VF_VERBOSE=1 to see every command)")


def probe_duration(path: Path) -> float:
    out = subprocess.run([ffbin("ffprobe"), "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return float(out.stdout.strip())


# ---------------------------------------------------------------- helpers

def project_dir(name: str) -> Path:
    p = Path(name)
    if not p.is_absolute() and not p.exists():
        p = PROJECTS / name
    if not p.is_dir():
        sys.exit(f"no such project: {p}")
    return p.resolve()


def sources(proj: Path) -> dict[str, Path]:
    src = proj / "source"
    if not src.is_dir():
        return {}
    return {f.stem: f for f in sorted(src.iterdir()) if f.suffix.lower() in VIDEO_EXT}


def fmt(t: float) -> str:
    m, s = divmod(max(t, 0.0), 60)
    return f"{int(m):02d}:{s:05.2f}"


def srt_time(t: float) -> str:
    ms = int(round(max(t, 0.0) * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(path: Path, cues: list[tuple[float, float, str]]) -> None:
    path.write_text("\n".join(f"{n}\n{srt_time(st)} --> {srt_time(en)}\n{t}\n"
                              for n, (st, en, t) in enumerate(cues, 1)), encoding="utf-8")


def load_transcript(proj: Path, src: str) -> list[dict]:
    """[{start, end, text, words: [{start, end, word}]}] in seconds (words may be empty)."""
    f = proj / "transcript" / f"{src}.json"
    if not f.exists():
        return []
    data = json.loads(f.read_text(encoding="utf-8"))
    return [{"start": float(s["start"]), "end": float(s["end"]), "text": s["text"].strip(),
             "words": s.get("words", [])} for s in data["segments"]]


def all_words(segs: list[dict]) -> list[dict]:
    return [w for s in segs for w in s.get("words", [])]


def norm_word(w: str) -> str:
    return re.sub(r"[^\w]", "", w, flags=re.UNICODE)


def load_fillers(lang: str) -> set[str]:
    f = ROOT / "tools" / f"fillers.{lang}.txt"
    if not f.exists():
        return set()
    return {norm_word(l) for l in f.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.startswith("#")}


# ---------------------------------------------------------------- transcription

def whisper_cpp_transcribe(path: Path, workdir: Path, language: str, prompt: str, model: Path) -> list[dict]:
    """whisper.cpp with DTW token timestamps -> segments with words."""
    cli = shutil.which("whisper-cli") or shutil.which("whisper-cpp")
    if not cli:
        sys.exit("whisper-cli not found: brew install whisper-cpp (it also comes with ffmpeg-full)")
    wav = workdir / "audio.wav"
    run([ffbin("ffmpeg"), "-v", "error", "-y", "-i", path, "-vn", "-ac", "1", "-ar", "16000", wav], check=True)
    cmd = [cli, "-m", model, "-l", language, "-ojf", "-of", workdir / "out", "-f", wav, "-np"]
    preset = dtw_preset(model)
    if preset:
        cmd += ["-dtw", preset, "-nfa"]  # DTW does not run with flash attention on
    if prompt:
        cmd += ["--prompt", prompt]
    r = run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stderr[-2000:])
        sys.exit("whisper.cpp failed")
    data = json.loads((workdir / "out.json").read_text(encoding="utf-8"))
    segs = []
    for s in data.get("transcription", []):
        text = s["text"].strip()
        if not text:
            continue
        seg_start, seg_end = s["offsets"]["from"] / 1000.0, s["offsets"]["to"] / 1000.0
        segs.append({"start": seg_start, "end": seg_end, "text": text,
                     "words": tokens_to_words(s.get("tokens", []), seg_start, seg_end)})
    return segs


def tokens_to_words(tokens: list[dict], seg_start: float, seg_end: float) -> list[dict]:
    """Merge whisper sub-word tokens into words. A token that starts with a space opens a word;
    punctuation sticks to the word before it. Time = DTW timestamp when present (t_dtw, in 10 ms),
    else the token's own offsets."""
    words: list[dict] = []
    for t in tokens:
        txt = t.get("text", "")
        if not txt or txt.startswith("[_") or txt.startswith("<|"):
            continue
        dtw = t.get("t_dtw", -1)
        t0 = dtw / 100.0 if isinstance(dtw, (int, float)) and dtw >= 0 else t["offsets"]["from"] / 1000.0
        t1 = max(t0, t["offsets"]["to"] / 1000.0)
        if txt.startswith(" ") or not words:
            if not norm_word(txt) and words:  # a lone punctuation token
                words[-1]["word"] += txt.strip()
                continue
            words.append({"word": txt.strip(), "start": t0, "end": t1, "p": t.get("p", 1.0)})
        else:
            words[-1]["word"] += txt
            words[-1]["end"] = max(words[-1]["end"], t1)
            words[-1]["p"] = min(words[-1]["p"], t.get("p", 1.0))
    # a word ends where the next one starts (DTW gives onsets), never past the segment
    for i, w in enumerate(words):
        nxt = words[i + 1]["start"] if i + 1 < len(words) else seg_end
        w["start"] = round(min(max(w["start"], seg_start), seg_end), 3)
        w["end"] = round(max(w["start"] + 0.05, min(max(w["end"], w["start"] + 0.08), nxt, seg_end)), 3)
        w["p"] = round(w["p"], 3)
    return [w for w in words if w["word"]]


# ---------------------------------------------------------------- commands

def cmd_doctor(_a) -> None:
    ok = True
    b = ffmpeg_full_bin()
    exe = str(b / "ffmpeg") if b else shutil.which("ffmpeg")
    print(f"ffmpeg      : {exe or 'MISSING — brew install ffmpeg-full (macOS) / your distro ffmpeg with libass'}")
    if exe:
        filters = subprocess.run([exe, "-hide_banner", "-filters"], capture_output=True, text=True).stdout
        for f in ("subtitles", "ass", "drawtext", "xfade", "tile"):
            has = f" {f} " in filters
            ok &= has
            print(f"  filter {f:<10} {'ok' if has else 'MISSING' + (' — needs libass (brew install ffmpeg-full)' if f in ('subtitles', 'ass') else '')}")
    else:
        ok = False
    has_skill = (SKILL_SCRIPTS / "cut.py").exists()
    ok &= has_skill
    print(f"ffmpeg-skill: {'ok' if has_skill else 'MISSING — npx ffmpeg-skill --project'}")
    cli = shutil.which("whisper-cli")
    m = whisper_model()
    print(f"whisper-cli : {cli or 'MISSING — brew install whisper-cpp'}")
    print(f"model       : {m or 'MISSING — see README (ivrit.ai ggml model)'}"
          + (f"  [dtw {dtw_preset(m)}]" if m else ""))
    if not (cli and m and m.exists()):
        ok = False
        print("no transcription engine: whisper-cli and a model are both needed (docs/setup.md)")
    node = shutil.which("node")
    ver = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip() if node else ""
    major = int(ver.lstrip("v").split(".")[0]) if ver[1:2].isdigit() else 0
    print(f"node        : {ver or 'MISSING'}"
          + ("" if major >= 22 else "  — motion graphics need Node.js 22+ (brew install node)"))
    print(f"npx         : {shutil.which('npx') or 'MISSING — comes with Node.js'}")
    import vf_voice
    vf_voice.load_env(ROOT)
    vp = (os.environ.get("VF_VISION_PROVIDER") or "openai").lower()
    base = os.environ.get("VF_VISION_BASE_URL") or ("https://generativelanguage.googleapis.com" if vp == "gemini"
                                                    else "http://localhost:1234/v1")
    if vp == "gemini":
        seen = "key set" if (os.environ.get("VF_VISION_API_KEY") or os.environ.get("GEMINI_API_KEY")) else "no key"
    else:
        try:
            import urllib.request
            urllib.request.urlopen(base.rstrip("/") + "/models", timeout=3).read()
            seen = "reachable"
        except Exception:
            seen = "not reachable"
    print(f"vision      : {vp} at {base} — {seen}  (optional: vf.py watch; docs/vision.md)")
    if not ok:
        print("\nnot ready — fix the MISSING lines above (docs/setup.md)")
    elif major < 22:
        print("\nready for editing and captions; motion graphics need Node.js 22+")
    else:
        print("\nready")
    sys.exit(0 if ok else 1)


def expand_inputs(items: list[str]) -> list[Path]:
    """Files as given; a folder contributes its video files (top level, sorted by name)."""
    files: list[Path] = []
    for item in items:
        p = Path(item).expanduser().resolve()
        if p.is_dir():
            found = sorted(f for f in p.iterdir() if f.is_file() and f.suffix.lower() in VIDEO_EXT
                           and not f.name.startswith("."))
            if not found:
                sys.exit(f"no video files in {p} (looked for {', '.join(sorted(VIDEO_EXT))})")
            files += found
        elif p.is_file():
            files.append(p)
        else:
            sys.exit(f"not found: {p}")
    return files


def is_cloud_placeholder(p: Path) -> bool:
    """An iCloud / File Provider file that is not downloaded reads as (almost) empty."""
    try:
        st = p.stat()
    except OSError:
        return True
    blocks = getattr(st, "st_blocks", None)
    return st.st_size > 0 and blocks is not None and blocks == 0


def cmd_new(a) -> None:
    inputs = expand_inputs(a.videos)  # fail before creating anything
    clouds = [v for v in inputs if is_cloud_placeholder(v)]
    if clouds:
        sys.exit("not on disk yet (iCloud / Google Drive placeholders) — download them (Finder: "
                 "Download Now) and run again:\n  " + "\n  ".join(str(v) for v in clouds))
    if not re.fullmatch(r"[^/\\]+", a.name) or a.name.startswith("."):
        sys.exit(f"project name {a.name!r}: use a plain folder name (no slashes)")
    proj = PROJECTS / a.name
    for sub in ("source", "transcript", "visual", "parts", "renders"):
        (proj / sub).mkdir(parents=True, exist_ok=True)
    for v in inputs:
        existing = {f.resolve(): f for f in (proj / "source").iterdir() if f.exists()}
        vst = v.stat()
        same_copy = next((f for f in (proj / "source").iterdir() if f.is_file() and not f.is_symlink()
                          and f.suffix.lower() == v.suffix.lower() and f.stat().st_size == vst.st_size
                          and int(f.stat().st_mtime) == int(vst.st_mtime)), None)  # copy2 keeps mtime
        if v in existing or same_copy:
            print(f"  source {(existing.get(v) or same_copy).name}: already there")
            continue
        dst = proj / "source" / v.name
        # a source is known by its name without the extension (transcripts, parts and story.json
        # use it), so clip.mp4 and clip.mov — or two folders' clip.mp4 — must not share one
        taken = {f.stem for f in (proj / "source").iterdir()}
        if dst.exists() or dst.is_symlink() or v.stem in taken:
            base, n = f"{v.stem}-{v.suffix.lstrip('.').lower()}", 2
            cand = base
            while cand in taken:
                cand, n = f"{base}{n}", n + 1
            dst = proj / "source" / f"{cand}{v.suffix}"
            print(f"  note: another source is already called {v.stem!r} — this one is {cand!r}")
        if a.copy:
            shutil.copy2(v, dst)  # for removable drives, cloud folders, or originals about to move
            print(f"  source {dst.name}: copied from {v}")
        else:
            dst.symlink_to(v)  # default: no duplicate footage; the original is never written to
            print(f"  source {dst.name} -> {v}")
    print(proj)


def cmd_transcribe(a) -> None:
    """Writes transcript/<src>.json = {"meta", "segments": [{start, end, text, words}]} in SECONDS,
    plus <src>.srt for reading."""
    proj = project_dir(a.project)
    model = Path(a.model).expanduser() if a.model else whisper_model()
    if not (model and model.exists() and shutil.which("whisper-cli")):
        sys.exit("no transcription engine: install whisper.cpp and an ivrit.ai ggml model "
                 "(docs/setup.md), or point VF_WHISPER_MODEL at a ggml model")
    for name, path in sources(proj).items():
        out_json = proj / "transcript" / f"{name}.json"
        if out_json.exists() and not a.force:
            print(f"  {name}: transcript exists (use --force to redo)")
            continue
        tmp = proj / "transcript" / f".{name}.raw"
        tmp.mkdir(exist_ok=True)
        engine = f"whisper.cpp {model.parent.parent.parent.name if 'snapshots' in str(model) else model.name}"
        segs = whisper_cpp_transcribe(path.resolve(), tmp, a.language, a.prompt, model)
        shutil.rmtree(tmp)
        data = {"meta": {"source": path.name, "engine": engine, "language": a.language, "units": "seconds",
                         "word_timings": any(s["words"] for s in segs)},
                "segments": segs}
        out_json.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        write_srt(proj / "transcript" / f"{name}.srt", [(s["start"], s["end"], s["text"]) for s in segs])
        nw = sum(len(s["words"]) for s in segs)
        print(f"  {name}: {len(segs)} segments, {nw} timed words via {engine}")


def cmd_transcript(a) -> None:
    proj = project_dir(a.project)
    fillers = load_fillers("he")
    for name in sources(proj):
        rows = []
        for i, s in enumerate(load_transcript(proj, name)):
            line = f"[{name}#{i} {fmt(s['start'])}-{fmt(s['end'])}] {s['text']}"
            if a.words and s["words"]:
                line += "\n    " + " ".join(f"{w['word']}@{w['start']:.2f}"
                                           + ("*" if norm_word(w["word"]) in fillers else "")
                                           for w in s["words"])
            rows.append((s["start"], line))
        for tag, vf in (("VISUAL", proj / "visual" / f"{name}.json"), ("WATCH", proj / "visual" / f"{name}.watch.json")):
            if not vf.exists():
                continue
            for v in json.loads(vf.read_text(encoding="utf-8")).get("shots", []):
                extra = f" ({v['use']}, q{v.get('quality', '?')})" if tag == "WATCH" and v.get("use") else ""
                rows.append((float(v["start"]), f"[{name} {fmt(v['start'])}-{fmt(v['end'])} {tag}{extra}] "
                                                 f"{v.get('description', '')}"))
        for _, line in sorted(rows, key=lambda r: r[0]):
            print(line)


def cmd_frames(a) -> None:
    """Contact sheets with timecodes (one tile every N seconds, 4x3 per sheet) and a scene list,
    so footage without speech can be understood and segmented by what it shows."""
    proj = project_dir(a.project)
    out = proj / "visual"
    out.mkdir(exist_ok=True)
    for name, path in sources(proj).items():
        dur = probe_duration(path)
        every = a.every or max(1.0, round(dur / 48, 1))  # ~4 sheets for any length by default
        for old in out.glob(f"{glob.escape(name)}_sheet_*.png"):
            old.unlink()
        vf = (f"fps=1/{every},scale={a.width // 4}:-2,"
              f"drawtext=text='%{{pts\\:hms}}':x=6:y=6:fontsize=18:fontcolor=white:box=1:boxcolor=black@0.6,"
              f"tile=4x3:padding=4:color=black")
        run([ffbin("ffmpeg"), "-v", "error", "-y", "-i", path, "-vf", vf, "-fps_mode", "vfr",
             out / f"{name}_sheet_%03d.png"], check=True)
        sheets = sorted(out.glob(f"{glob.escape(name)}_sheet_*.png"))
        r = run([sys.executable, SKILL_SCRIPTS / "scenes.py", path, "--threshold", str(a.threshold), "--json"],
                capture_output=True, text=True)
        scenes = []
        try:
            scenes = [{"start": s["start"], "end": s["end"]} for s in json.loads(r.stdout).get("scenes", [])]
        except (ValueError, AttributeError):
            pass
        (out / f"{name}.scenes.json").write_text(json.dumps({"every": every, "scenes": scenes}, indent=1),
                                                 encoding="utf-8")
        print(f"  {name}: {dur:.1f}s, a tile every {every}s -> {len(sheets)} sheet(s), {len(scenes)} scene(s)")
        for s in sheets:
            print(f"    {s}")


def cmd_reference(a) -> None:
    """Study a reference video the user wants to imitate: pace, transitions, look, captions.
    Writes reference/<name>/: shots.json (every shot and its length), sheets of the whole video,
    and transitions.png — three frames around each cut, to tell a hard cut from a dissolve or wipe."""
    proj = project_dir(a.project)
    src = Path(a.video).expanduser().resolve()
    if not src.is_file():
        sys.exit(f"not found: {src} — for a URL, download it first (e.g. the /watch plugin, or yt-dlp)")
    out = proj / "reference" / re.sub(r"[^\w.-]+", "_", src.stem)
    out.mkdir(parents=True, exist_ok=True)
    dur = probe_duration(src)
    r = run([sys.executable, SKILL_SCRIPTS / "scenes.py", src, "--threshold", str(a.threshold), "--json"],
            capture_output=True, text=True)
    try:
        shots = [{"start": round(x["start"], 2), "end": round(x["end"], 2), "length": round(x["end"] - x["start"], 2)}
                 for x in json.loads(r.stdout).get("scenes", [])]
    except (ValueError, KeyError):
        shots = []
    lengths = sorted(x["length"] for x in shots) or [dur]
    median = lengths[len(lengths) // 2]
    stats = {"file": str(src), "duration": round(dur, 2), "shots": len(shots), "median_shot": median,
             "mean_shot": round(sum(lengths) / len(lengths), 2), "shortest": lengths[0], "longest": lengths[-1],
             "cuts_per_minute": round(60 * max(len(shots) - 1, 0) / dur, 1) if dur else 0}
    (out / "shots.json").write_text(json.dumps({"stats": stats, "shots": shots}, indent=1), encoding="utf-8")
    every = a.every or max(0.5, round(dur / 48, 2))
    for old in out.glob("sheet_*.png"):
        old.unlink()
    vf = (f"fps=1/{every},scale=320:-2,drawtext=text='%{{pts\\:hms}}':x=6:y=6:fontsize=18:fontcolor=white:"
          f"box=1:boxcolor=black@0.6,tile=4x3:padding=4:color=black")
    run([ffbin("ffmpeg"), "-v", "error", "-y", "-i", src, "-vf", vf, "-fps_mode", "vfr", out / "sheet_%03d.png"],
        check=True)
    # transitions: for the first cuts, the frames 0.3 s before, at, and 0.3 s after each cut
    cuts = [x["start"] for x in shots[1:13]]
    if cuts:
        frames = []
        for k, t in enumerate(cuts):
            for j, dt in enumerate((-0.3, 0.0, 0.3)):
                f = out / f".t{k:02d}_{j}.png"
                run([ffbin("ffmpeg"), "-v", "error", "-y", "-ss", f"{max(0, t + dt):.3f}", "-i", src, "-frames:v", "1",
                     "-vf", f"scale=320:-2,drawtext=text='cut {k + 1} {t + dt:.1f}s':x=6:y=6:fontsize=18:"
                            f"fontcolor=white:box=1:boxcolor=black@0.6", f], check=True)
                frames.append(f)
        lst = out / ".t.txt"
        lst.write_text("".join(f"file '{f.name}'\n" for f in frames), encoding="utf-8")
        run([ffbin("ffmpeg"), "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-vf",
             f"tile=3x{len(cuts)}:padding=4:color=black", "-frames:v", "1", out / "transitions.png"], check=True)
        for f in frames + [lst]:
            f.unlink()
    print(f"  {src.name}: {stats['duration']}s, {stats['shots']} shots, median shot {median}s, "
          f"{stats['cuts_per_minute']} cuts/min")
    print(f"  read: {out}/sheet_*.png (content, graphics, captions), {out}/transitions.png (how it cuts)")
    print(f"  then write {out}/style.md and carry it into story.json")


HOOK_WORDS_HE = {"סוד", "טעות", "טעויות", "הכי", "אף", "תמיד", "לעולם", "למה", "איך", "מה", "שימו", "חשוב",
                 "בעצם", "האמת", "מפתיע", "פשוט", "צריך", "אסור", "חייבים", "כולם", "אף אחד", "רגע", "דמיינו",
                 "מכירים", "טריק", "שיטה", "סיבה", "הבעיה", "הפתרון", "בלי"}


def cmd_candidates(a) -> None:
    """Moments that could stand alone as a short: windows of whole transcript segments, scored on
    signals a clip needs (a hook up front, numbers, energy, a complete ending). A shortlist for
    Claude to read and judge — the score is a proxy, the decision is not made here."""
    proj = project_dir(a.project)
    fillers = load_fillers(a.language)
    rows = []
    for src in sources(proj):
        segs = load_transcript(proj, src)
        for i in range(len(segs)):
            for j in range(i, len(segs)):
                st, en = segs[i]["start"], segs[j]["end"]
                if en - st > a.max:
                    break
                if en - st < a.min:
                    continue
                text = " ".join(s["text"] for s in segs[i:j + 1])
                words = [w for s in segs[i:j + 1] for w in s["words"]] or text.split()
                first = segs[i]["text"]
                first_words = {norm_word(w) for w in first.split()}
                hook = (2 if "?" in first else 0) + (2 if re.search(r"\d", first) else 0) \
                    + 1.5 * len(first_words & HOOK_WORDS_HE) + (1 if len(first.split()) <= 8 else 0)
                numbers = len(re.findall(r"\d+%?", text))
                rate = len(words) / max(1.0, en - st)
                filler_share = sum(1 for w in words if norm_word(w["word"] if isinstance(w, dict) else w) in fillers) / max(1, len(words))
                ends = 1 if segs[j]["text"].rstrip().endswith((".", "!", "?")) else 0
                gap_before = segs[i]["start"] - (segs[i - 1]["end"] if i else 0) >= 0.4
                score = round(hook * 1.5 + min(numbers, 3) + min(rate, 4) + 2 * ends + (1 if gap_before else 0)
                              - 10 * filler_share, 2)
                rows.append({"source": src, "start": round(max(0, st - 0.15), 2), "end": round(en + 0.2, 2),
                             "length": round(en - st, 1), "score": score, "first": first, "text": text,
                             "segments": [i, j]})
    rows.sort(key=lambda r: -r["score"])
    picked = []
    for r in rows:  # no two candidates from the same stretch
        if all(r["source"] != q["source"] or r["end"] <= q["start"] or r["start"] >= q["end"] for q in picked):
            picked.append(r)
        if len(picked) >= a.top:
            break
    (proj / "candidates.json").write_text(json.dumps({"candidates": picked}, ensure_ascii=False, indent=1), encoding="utf-8")
    if not picked:
        print(f"  no window of {a.min:g}–{a.max:g}s in the transcripts — transcribe first, or change --min/--max")
        return
    for k, r in enumerate(picked, 1):
        print(f"  #{k} [{r['source']} {fmt(r['start'])}-{fmt(r['end'])} {r['length']}s] score {r['score']}")
        print(f"     hook: {r['first'][:110]}")
    print(f"  -> {proj / 'candidates.json'} (full text of each). Read them, pick, and write clips.json.")


def cmd_clips(a) -> None:
    """Render clips.json: each clip a self-contained short (vertical by default) with word-by-word
    captions, a hook title over the first seconds, the brand, and optionally an end card."""
    import argparse as _ap
    proj = project_dir(a.project)
    cfg = read_json(proj / "clips.json", "clips.json (pick moments first: vf.py candidates)")
    style = {"width": 1080, "height": 1920, "fit": "crop", "clean": ["fillers", "pauses"], "max_pause": 0.4,
             "karaoke_style": "word", "caption_size": 24, "caption_position": "bottom", "hook_seconds": 2.5,
             "logo": True, **cfg.get("style", {})}
    only = set(a.only.split(",")) if a.only else None
    clips = [c for c in cfg.get("clips", []) if not only or c["id"] in only]
    if not clips:
        sys.exit("clips.json has no clips" + (f" matching {a.only}" if only else ""))
    brand_logo = (proj / "brand.json").exists() and json.loads((proj / "brand.json").read_text(encoding="utf-8")).get("logo")
    results = []
    for c in clips:
        part = {"id": c["id"], "source": c["source"], "start": c["start"], "end": c["end"],
                "clean": c.get("clean", style["clean"]), "max_pause": style["max_pause"]}
        parts = [part]
        if style.get("end_card"):
            parts.append({"id": f"{c['id']}-end", "motion": {"template": "end-card", **style["end_card"]}})
        story = {"title": c.get("title", c["id"]),
                 "output": {"width": style["width"], "height": style["height"], "fps": style.get("fps", 30)},
                 "fit": style["fit"], "transition": {"type": "fade", "duration": 0.3}, "parts": parts,
                 "captions": {"enabled": True, "language": style.get("language", "he"), "karaoke": True,
                              "karaoke_style": style["karaoke_style"], "size": style["caption_size"],
                              "position": style["caption_position"], "cues": cfg.get("cues", [])},
                 "overlays": [], "loudness": style.get("loudness", -14)}
        hook = c.get("hook") or c.get("title")
        if hook:
            story["overlays"].append({"part": c["id"], "at": 0, "motion": {"template": "title", "duration": style["hook_seconds"],
                                      "vars": {"title": hook, "subtitle": c.get("subtitle", ""), "opaque": False,
                                                       "place": style.get("hook_place", "top")}}})
        if style.get("logo") and brand_logo:
            story["overlays"].append({"logo": True, "whole": True, "position": "top-left", "scale": 160, "opacity": 0.85})
        if style.get("music"):
            story["music"] = style["music"]
        validate_story(proj, story, sources(proj))
        print(f"== clip {c['id']}: {c.get('title') or c.get('hook', '')}")
        ns = _ap.Namespace(draft=a.draft, force=False, keep_stages=False, keep_going=True)
        problems = render_story(proj, story, f"clip_{c['id']}" + ("_draft" if a.draft else ""), ns)
        results.append((c["id"], problems))
    bad = [(i, p) for i, p in results if p]
    print(f"  {len(results) - len(bad)}/{len(results)} clips passed QA" + (": " + "; ".join(f"{i}: {', '.join(p)}" for i, p in bad) if bad else ""))
    if bad:
        sys.exit(2)


def cmd_status(a) -> None:
    """Where each project stands, and the next step."""
    import datetime
    projs = [project_dir(a.project)] if a.project else sorted(
        p for p in PROJECTS.iterdir() if p.is_dir() and (p / "source").is_dir()) if PROJECTS.exists() else []
    if not projs:
        print("no projects yet — python3 tools/vf.py new <name> <folder or files>")
        return
    for proj in projs:
        srcs = sources(proj)
        print(f"{proj.name}")
        broken = [n for n, f in srcs.items() if not f.exists()]
        for n in srcs:
            tr = "transcript ✓" if (proj / "transcript" / f"{n}.json").exists() else "no transcript"
            vis = ", visual notes ✓" if (proj / "visual" / f"{n}.json").exists() else ""
            vis += ", model shot log ✓" if (proj / "visual" / f"{n}.watch.json").exists() else ""
            print(f"  source {n}: {tr}{vis}" + ("  — LINK BROKEN (original moved?)" if n in broken else ""))
        for f, label in (("brief.md", "brief"), ("script.md", "script"), ("brand.json", "brand"),
                         ("segments.json", "segments"), ("voice/voiceover.wav", "voice-over")):
            if (proj / f).exists():
                print(f"  {label}: ✓")
        nxt = None
        if (proj / "story.json").exists():
            try:
                st = json.loads((proj / "story.json").read_text(encoding="utf-8"))
                ver = ", versions: " + ", ".join(st.get("versions", {})) if st.get("versions") else ""
                print(f"  story: {len(st.get('parts', []))} parts{ver}")
            except json.JSONDecodeError:
                print("  story: INVALID JSON")
        for r in sorted((proj / "renders").glob("*.mp4")):
            when = datetime.datetime.fromtimestamp(r.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            print(f"  render {r.name}: {probe_duration(r):.1f}s, {when}")
        if not srcs and not (proj / "script.md").exists():
            nxt = "add footage: vf.py new " + proj.name + " <folder>"
        elif srcs and not (proj / "script.md").exists() \
                and any(not (proj / "transcript" / f"{n}.json").exists() for n in srcs):
            nxt = "vf.py transcribe " + proj.name
        elif (proj / "script.md").exists() and not (proj / "voice" / "voiceover.wav").exists():
            nxt = "vf.py voice " + proj.name
        elif not (proj / "story.json").exists():
            nxt = "write story.json (Claude proposes it, you approve)"
        elif not (proj / "renders" / "draft.mp4").exists() and not (proj / "renders" / "final.mp4").exists():
            nxt = "vf.py render " + proj.name + " --draft"
        if broken:
            nxt = "relink the moved originals: vf.py new " + proj.name + " <their new folder>"
        if nxt:
            print(f"  next: {nxt}")


def cmd_scenes(a) -> None:
    proj = project_dir(a.project)
    for name, path in sources(proj).items():
        print(f"== {name}")
        ff("scenes", path, "--threshold", str(a.threshold))


# ---------------------------------------------------------------- render

def snap_range(start: float, end: float, words: list[dict]) -> tuple[float, float]:
    """A cut that lands inside a word moves to the silence just outside it: the start to before
    the word, the end to after it — never into the neighbouring word."""
    for i, w in enumerate(words):
        prev_end = words[i - 1]["end"] if i else 0.0
        next_start = words[i + 1]["start"] if i + 1 < len(words) else w["end"] + SNAP_PAD
        if w["start"] - 0.02 < start < w["end"]:
            start = max(prev_end, w["start"] - SNAP_PAD)
        if w["start"] < end < w["end"] + 0.02:
            end = min(next_start, w["end"] + SNAP_PAD)
    return round(start, 3), round(end, 3)


def keep_ranges(p: dict, words: list[dict], fillers: set[str]) -> tuple[list[tuple[float, float]], set[int]]:
    """The source ranges a part keeps, after the requested clean-up. Returns (ranges, removed word ids)."""
    clean = p.get("clean", [])
    clean = [clean] if isinstance(clean, str) else clean
    start, end = p["start"], p["end"]
    inside = [(i, w) for i, w in enumerate(words) if w["start"] >= start - 0.01 and w["end"] <= end + 0.01]
    cuts: list[tuple[float, float]] = []
    removed: set[int] = set()
    if "fillers" in clean:
        for i, w in inside:
            if norm_word(w["word"]) in fillers:
                lo = max(w["start"] - FILLER_PAD, words[i - 1]["end"] if i > 0 else -1e9)
                hi = min(w["end"] + FILLER_PAD, words[i + 1]["start"] if i + 1 < len(words) else 1e9)
                cuts.append((lo, hi))
                removed.add(i)
    if "pauses" in clean:
        max_pause = float(p.get("max_pause", 0.6))
        spoken = [w for i, w in inside if i not in removed]
        for w0, w1 in zip(spoken, spoken[1:]):
            gap = w1["start"] - w0["end"]
            if gap > max_pause:
                keep = max_pause / 2
                cuts.append((w0["end"] + keep, w1["start"] - keep))
    ranges = [(start, end)]
    for c0, c1 in sorted(cuts):
        nxt = []
        for r0, r1 in ranges:
            if c1 <= r0 or c0 >= r1:
                nxt.append((r0, r1))
                continue
            if c0 - r0 >= MIN_KEEP:
                nxt.append((r0, c0))
            if r1 - c1 >= MIN_KEEP:
                nxt.append((c1, r1))
        ranges = nxt
    return [(round(a, 3), round(b, 3)) for a, b in ranges], removed


def mapper(ranges: list[tuple[float, float]], offset: float):
    """Source time -> final-timeline time for one part (None if the moment was cut out)."""
    def f(t: float, snap: str = "none") -> float | None:
        acc = 0.0
        for r0, r1 in ranges:
            if t < r0:  # inside a cut (or before the part): next = where the next range starts,
                return offset + acc if snap in ("next", "prev") else None  # prev = where the last one ended
            if t <= r1:
                return offset + acc + (t - r0)
            acc += r1 - r0
        return offset + acc if snap == "prev" else None
    return f


def caption_cues(proj: Path, story: dict, plan: list[dict]) -> list[dict]:
    """Every caption cue on the final timeline: [{start, end, text, key, words}].
    From the parts' own transcripts, or — when the story has a voice-over and captions follow it —
    from the voice-over's transcript."""
    cap = story.get("captions", {})
    overrides = {c["id"]: c["text"] for c in cap.get("cues", []) if "id" in c}
    vo = story.get("voiceover")
    source = cap.get("source", "voiceover" if vo else "parts")
    cues: list[dict] = []

    def add(st, en, text, key, words):
        if text and text.strip() and en - st >= 0.25:
            cues.append({"start": st, "end": en, "text": text, "key": key, "words": words})

    if source == "voiceover":
        if not vo:
            sys.exit('captions.source is "voiceover" but the story has no voiceover')
        at = float(vo.get("at", 0))
        for j, s in enumerate(load_transcript(proj, "voiceover")):
            key = f"voiceover:{j}"
            words = [] if key in overrides else [
                {"word": w["word"], "start": round(at + w["start"], 3), "end": round(at + w["end"], 3)} for w in s["words"]]
            add(at + s["start"], at + s["end"], overrides.get(key, s["text"]), key, words)
    else:
        for item in plan:
            p, m = item["part"], item["map"]
            if m is None or not p.get("captions", True):
                continue
            for j, s in enumerate(load_transcript(proj, p["source"])):
                if s["end"] <= p["start"] or s["start"] >= p["end"]:
                    continue
                kept = [w for k, w in enumerate(s["words"])
                        if (s["start"], k) not in item["removed_keys"] and m(w["start"]) is not None]
                st = m(max(s["start"], p["start"]), "next")
                en = m(min(s["end"], p["end"]), "prev")
                if st is None or en is None:
                    continue
                key = f"{p['source']}:{j}"
                if key in overrides:
                    text = overrides[key]
                elif s["words"] and len(kept) < len(s["words"]):
                    text = " ".join(w["word"] for w in kept)  # a filler was cut: drop it from the line
                else:
                    text = s["text"]
                words = []
                if key not in overrides:  # a rewritten line loses word-to-word correspondence
                    for w in kept:
                        ws, we = m(w["start"], "next"), m(w["end"], "prev")
                        if ws is not None and we is not None and we > ws:
                            words.append({"word": w["word"], "start": round(ws, 3), "end": round(we, 3)})
                add(st, en, text, key, words)
    # inside a crossfade the outgoing and incoming cues overlap: end each just before the next
    cues.sort(key=lambda c: c["start"])
    for k in range(len(cues) - 1):
        nxt = cues[k + 1]["start"]
        if cues[k]["end"] > nxt - 0.05:
            cues[k]["end"] = max(cues[k]["start"] + 0.3, nxt - 0.05)
    return cues


def write_caption_files(proj: Path, cues: list[dict], stem: str) -> Path:
    srt = proj / f"{stem}.srt"
    write_srt(srt, [(c["start"], c["end"], c["text"]) for c in cues])
    words = [w for c in cues for w in c["words"]]
    wf = proj / f"{stem}.words.json"  # ffmpeg-skill's --karaoke reads <srt stem>.words.json
    if words:
        wf.write_text(json.dumps({"words": sorted(words, key=lambda w: w["start"])}, ensure_ascii=False, indent=1),
                      encoding="utf-8")
    elif wf.exists():
        wf.unlink()
    return srt


def deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and v and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:  # a value, null, or {} (= "none of these in this version") replaces the story's
            out[k] = v
    return out


def read_json(path: Path, what: str) -> dict:
    if not path.exists():
        sys.exit(f"{what} not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        line = path.read_text(encoding="utf-8").splitlines()[e.lineno - 1] if e.lineno else ""
        sys.exit(f"{path.name}: invalid JSON at line {e.lineno}, column {e.colno}: {e.msg}\n  {line.strip()[:120]}")


def validate_story(proj: Path, story: dict, srcs: dict[str, Path]) -> None:
    """Every problem a render would hit late — found before anything is rendered, all at once."""
    import vf_motion
    errs, warns = [], []
    parts = story.get("parts") or []
    if not parts:
        errs.append("story has no parts")
    ids = [p.get("id") for p in parts]
    dupes = sorted({i for i in ids if ids.count(i) > 1 and i})
    if dupes:
        errs.append(f"duplicate part id(s): {dupes}")
    junc = junctions(story)
    known_types = xfade_types()
    for k, (typ, _) in enumerate(junc):
        if typ not in known_types:
            where = f"part {parts[k].get('id')}" if parts[k].get("transition") else "transition"
            errs.append(f"{where}: unknown transition {typ!r} (some: fade, dissolve, fadeblack, wipeleft, "
                        "slideleft, circleopen, zoomin, pixelize, hblur — docs/story-json.md lists all)")
    no_transcript = set()
    for i, p in enumerate(parts):
        pid = p.get("id") or f"#{i + 1}"
        if not p.get("id"):
            errs.append(f"part {pid}: needs an id")
        if "motion" in p:
            try:
                vf_motion.template_dir(proj, p["motion"].get("template", ""), quiet=True)
            except LookupError as e:
                errs.append(f"part {pid}: {e}")
            length = float(p["motion"].get("duration") or vf_motion.DEFAULT_DURATION.get(p["motion"].get("template"), 5))
        else:
            if p.get("source") not in srcs:
                errs.append(f"part {pid}: unknown source {p.get('source')!r} (have: {', '.join(srcs) or 'none'})")
                continue
            if "start" not in p or "end" not in p or float(p["end"]) <= float(p["start"]):
                errs.append(f"part {pid}: needs start < end")
                continue
            length = float(p["end"]) - float(p["start"])
            if not (proj / "transcript" / f"{p['source']}.json").exists():
                no_transcript.add(p["source"])
        # a clip shorter than its transitions cannot be crossfaded: interior parts take two
        d_in = junc[i][1] if i > 0 else 0.0
        d_out = junc[i + 1][1] if i + 1 < len(parts) else 0.0
        need = d_in + d_out + 0.1 if (d_in or d_out) else 0
        if need and length < need:
            errs.append(f"part {pid}: {length:.2f}s is too short for its transitions ({d_in:g}s in, {d_out:g}s out; "
                        f"needs more than {need:.2f}s) — lengthen it or shorten the transitions")
    known = set(ids)
    for kind in ("overlays", "broll"):
        for o in story.get(kind, []):
            if "part" in o and o["part"] not in known and not o.get("whole"):
                warns.append(f"{kind}: part {o['part']!r} is not in this edit — skipped")
            if "motion" in o:
                try:
                    vf_motion.template_dir(proj, o["motion"].get("template", ""), quiet=True)
                except LookupError as e:
                    errs.append(f"{kind}: {e}")
            if kind == "broll" and "source" in o and o["source"] not in srcs:
                errs.append(f"broll: unknown source {o['source']!r}")
            if o.get("image") and not (proj / o["image"]).exists():
                errs.append(f"overlay image not found: {o['image']}")
            if o.get("logo") and not vf_motion.load_brand(proj).get("logo"):
                errs.append("overlay logo: brand.json has no logo")
    for key, label in (("music", "music file"), ("voiceover", "voice-over file")):
        if story.get(key):
            f = story[key].get("file", "voice/voiceover.wav" if key == "voiceover" else "")
            if not f or not (proj / f).exists():
                errs.append(f"{label} not found: {f or '(no file given)'}"
                            + (" — run vf.py voice first" if key == "voiceover" else ""))
    if story.get("look", {}).get("lut") and not (proj / story["look"]["lut"]).exists():
        errs.append(f"LUT not found: {story['look']['lut']}")
    cap = story.get("captions", {})
    if cap.get("enabled", True):
        if story.get("voiceover") and cap.get("source", "voiceover") == "voiceover" \
                and not (proj / "transcript" / "voiceover.json").exists():
            warns.append("captions follow the voice-over, but it has no transcript (run vf.py voice "
                         "with a whisper model) — no captions")
        elif no_transcript and cap.get("source", "voiceover" if story.get("voiceover") else "parts") == "parts":
            warns.append(f"no transcript for {', '.join(sorted(no_transcript))} — those parts get no captions "
                         "(run vf.py transcribe)")
        for lang, t in cap.get("translations", {}).items():
            if not (proj / t.get("file", f"translations/{lang}.json")).exists():
                errs.append(f"translation {lang}: {t.get('file', f'translations/{lang}.json')} not found")
    for w in warns:
        print(f"  note: {w}", file=sys.stderr)
    if errs:
        sys.exit("story.json has problems — nothing was rendered:\n  - " + "\n  - ".join(errs))


def load_story(proj: Path, version: str | None) -> dict:
    story = read_json(proj / "story.json", "story.json (write the edit first — see docs/story-json.md)")
    if not version:
        return story
    versions = story.get("versions", {})
    if version not in versions:
        sys.exit(f"no version {version!r} in story.json (have: {', '.join(versions) or 'none'})")
    over = dict(versions[version])
    ids = over.pop("parts", None)
    merged = deep_merge({k: v for k, v in story.items() if k != "versions"}, over)
    if ids:
        by_id = {p["id"]: p for p in story["parts"]}
        missing = [i for i in ids if i not in by_id]
        if missing:
            sys.exit(f"version {version}: unknown part id(s) {missing}")
        merged["parts"] = [by_id[i] for i in ids]
    return merged


def frame_size(story: dict, srcs: dict[str, Path]) -> tuple[int, int, float]:
    """Output size: story.output, else the first footage part's source as it is displayed
    (a phone clip stored landscape with a 90° rotation is portrait), else 1920x1080."""
    out = story.get("output", {})
    w, h = out.get("width"), out.get("height")
    if not (w and h):
        first = next((srcs[p["source"]] for p in story.get("parts", []) if p.get("source") in srcs), None)
        if first:
            r = subprocess.run([ffbin("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries",
                                "stream=width,height:stream_side_data=rotation:stream_tags=rotate", "-of", "json",
                                str(first)], capture_output=True, text=True)
            st = json.loads(r.stdout or "{}").get("streams", [{}])[0]
            w, h = int(st.get("width", 1920)), int(st.get("height", 1080))
            rot = st.get("tags", {}).get("rotate") or next(
                (d.get("rotation") for d in st.get("side_data_list", []) if "rotation" in d), 0)
            if abs(int(float(rot or 0))) % 180 == 90:
                w, h = h, w
        else:
            w, h = 1920, 1080
    return int(w), int(h), float(out.get("fps", 30))


def fps_arg(fps: float) -> str:
    """29.97 / 23.976 / 59.94 as the exact NTSC rationals; whole rates as integers."""
    for nominal, rational in ((29.97, "30000/1001"), (23.976, "24000/1001"), (59.94, "60000/1001")):
        if abs(fps - nominal) < 0.01:
            return rational
    return f"{fps:g}"


def plan_parts(proj: Path, story: dict, srcs: dict[str, Path]) -> list[dict]:
    """Snap, clean and key every footage part (no rendering). Motion parts pass through."""
    fillers = load_fillers(story.get("captions", {}).get("language", "he"))
    items = []
    for p in story["parts"]:
        p = dict(p)
        if "motion" in p:
            items.append({"part": p, "ranges": None, "removed": set(), "removed_keys": set()})
            continue
        if p.get("source") not in srcs:
            sys.exit(f"part {p.get('id')}: unknown source {p.get('source')!r} (have {list(srcs)})")
        segs = load_transcript(proj, p["source"])
        words = all_words(segs)
        if words and not p.get("exact", False):
            p["start"], p["end"] = snap_range(float(p["start"]), float(p["end"]), words)
        ranges, removed = keep_ranges(p, words, fillers)
        keys, k = set(), 0
        for s in segs:  # removed ids are positions in all_words(); key them by (segment start, index)
            for wi in range(len(s["words"])):
                if k in removed:
                    keys.add((s["start"], wi))
                k += 1
        items.append({"part": p, "ranges": ranges, "removed": removed, "removed_keys": keys})
    return items


def final_time(ref: dict, by_id: dict[str, dict]) -> float | None:
    """Where an overlay / b-roll lands: {"part": id, "at": seconds into that part} or {"at_final": s}."""
    if "at_final" in ref:
        return float(ref["at_final"])
    item = by_id.get(ref.get("part"))
    if item is None:
        return None  # the part is not in this version
    return item["start"] + float(ref.get("at", 0))


def stage(stages: Path, name: str) -> Path:
    return stages / f"{name}.mp4"


def xfade_types() -> set[str]:
    """The transitions this ffmpeg's xfade filter knows (about 60 in FFmpeg 7+)."""
    out = subprocess.run([ffbin("ffmpeg"), "-hide_banner", "-h", "filter=xfade"], capture_output=True, text=True).stdout
    block = out.split("transition", 1)[1].split("duration", 1)[0] if "transition" in out else ""
    names = set(re.findall(r"^\s+([a-z]+)\s+-?\d+", block, flags=re.M)) - {"custom"}
    return names | {"none"}


def junctions(story: dict) -> list[tuple[str, float]]:
    """The transition INTO each part (index 0 is unused): the part's own "transition", else the story's."""
    g = story.get("transition", {"type": "fade", "duration": 0.5})
    out = []
    for p in story.get("parts", []):
        t = {**g, **p.get("transition", {})} if isinstance(p.get("transition"), dict) else g
        typ = t.get("type", "fade")
        out.append((typ, 0.0 if typ == "none" else float(t.get("duration", 0.5))))
    return out


def fps_float(fps: str) -> float:
    if "/" in fps:
        n, d = fps.split("/")
        return float(n) / float(d)
    return float(fps)


def join_mixed(part_files: list[Path], lengths: list[float], junc: list[tuple[str, float]], W: int, H: int,
               FPS: str, fit: str, out: Path, draft: bool) -> None:
    """Join parts with a different transition at each junction (ffmpeg-skill's join takes one).
    Every part is normalised (size, fit, fps, pixel format, 48 kHz stereo), then chained with
    xfade + acrossfade. A "none" junction is a one-frame fade — a cut, visually."""
    one_frame = 1.0 / fps_float(FPS)
    cmd = [ffbin("ffmpeg"), "-v", "error", "-y"]
    for f in part_files:
        cmd += ["-i", str(f)]
    chains, n_in = [], len(part_files)
    for i, (f, L) in enumerate(zip(part_files, lengths)):
        has_audio = bool(subprocess.run([ffbin("ffprobe"), "-v", "error", "-select_streams", "a", "-show_entries",
                                         "stream=index", "-of", "csv=p=0", str(f)], capture_output=True, text=True).stdout.strip())
        if fit == "crop":
            geo = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"
        else:
            geo = f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black"
        chains.append(f"[{i}:v]{geo},setsar=1,fps={FPS},format=yuv420p,setpts=PTS-STARTPTS,"
                      f"trim=duration={L:.3f},settb=AVTB[v{i}]")
        if has_audio:
            chains.append(f"[{i}:a:0]aresample=48000,aformat=sample_rates=48000:channel_layouts=stereo,"
                          f"asetpts=PTS-STARTPTS,apad,atrim=duration={L:.3f}[a{i}]")
        else:
            cmd += ["-f", "lavfi", "-t", f"{L:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
            chains.append(f"[{n_in}:a]atrim=duration={L:.3f}[a{i}]")
            n_in += 1
    vlast, alast, cum = "[v0]", "[a0]", lengths[0]
    for i in range(1, len(part_files)):
        typ, d = junc[i]
        if typ == "none" or d <= 0:
            typ, d = "fade", max(d, one_frame)
        off = cum - d
        chains.append(f"{vlast}[v{i}]xfade=transition={typ}:duration={d:.3f}:offset={off:.3f}[vx{i}]")
        chains.append(f"{alast}[a{i}]acrossfade=d={d:.3f}:c1=tri:c2=tri[ax{i}]")
        vlast, alast, cum = f"[vx{i}]", f"[ax{i}]", cum + lengths[i] - d
    cmd += ["-filter_complex", ";".join(chains), "-map", vlast, "-map", alast, "-c:v", "libx264",
            "-preset", "veryfast" if draft else "medium", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)]
    r = run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("joining with mixed transitions failed: " + (r.stderr.strip().splitlines() or ["?"])[-1])


def cmd_render(a) -> None:
    proj = project_dir(a.project)
    story = load_story(proj, a.version)
    name = (f"{a.version}_draft" if a.draft else a.version) if a.version else ("draft" if a.draft else "final")
    render_story(proj, story, name, a)


def render_story(proj: Path, story: dict, name: str, a) -> list[str]:
    """Render one story to renders/<name>.mp4. `a` carries draft / force / keep_stages.
    Returns the QA problems (empty = ok); the caller decides whether that ends the run."""
    import vf_motion
    srcs = sources(proj)
    validate_story(proj, story, srcs)
    for old in list(proj.glob("captions*.srt")) + list(proj.glob("captions*.words.json")):
        old.unlink()  # this render's captions only — a stale file would hide a render that made none
    W, H, FPS = frame_size(story, srcs)
    FPS = fps_arg(FPS)
    tr = story.get("transition", {"type": "fade", "duration": 0.5})
    ttype, tdur = tr.get("type", "fade"), float(tr.get("duration", 0.5))
    if ttype == "none":
        tdur = 0.0
    junc = junctions(story)  # the transition into each part
    mixed = len(set(junc[1:])) > 1 or (len(junc) > 1 and junc[1] != (ttype, tdur))
    if mixed:  # a "none" junction is a one-frame fade there, and the timeline must count that frame
        frame = 1.0 / fps_float(FPS)
        junc = [junc[0]] + [("none", frame) if (t == "none" or d <= 0) else (t, d) for t, d in junc[1:]]
    stages = proj / "renders" / f".stages-{name}"
    stages.mkdir(parents=True, exist_ok=True)
    fast = ["--fast"] if a.draft else []

    # 1. parts: footage cut frame-accurate (cached by kept ranges); motion cards rendered
    plan, part_files, offset = [], [], 0.0
    items = plan_parts(proj, story, srcs)
    short = []
    for i, it in enumerate(items):
        if it["ranges"] is None:
            continue
        kept = sum(r1 - r0 for r0, r1 in it["ranges"])
        d_in = junc[i][1] if i > 0 else 0.0
        d_out = junc[i + 1][1] if i + 1 < len(items) else 0.0
        need = d_in + d_out + 0.1
        if kept < need:
            short.append(f"part {it['part']['id']}: {kept:.2f}s left after snapping/cleaning"
                         + (f", needs more than {need:.2f}s for its transitions" if need > 0.1 else " — nothing to cut"))
    if short:
        sys.exit("story.json has problems — nothing was rendered:\n  - " + "\n  - ".join(short))
    for i, it in enumerate(items):
        p = it["part"]
        if it["ranges"] is None:
            f = proj / "parts" / f"{p['id']}_{W}x{H}.mp4"
            vf_motion.render_motion(proj, p["motion"], f, W, H, FPS, alpha=False, draft=a.draft)
            note = f"motion {p['motion']['template']}"
            m = None
        else:
            ranges = it["ranges"]
            f = proj / "parts" / f"{p['id']}.mp4"
            src_st = srcs[p["source"]].stat()
            sig = json.dumps([ranges, str(srcs[p["source"]].resolve()), src_st.st_size, int(src_st.st_mtime)])
            sigf = f.with_suffix(".ranges.json")
            if a.force or not f.exists() or not sigf.exists() or sigf.read_text() != sig:
                ff("cut", srcs[p["source"]], "--segments", ",".join(f"{r0}-{r1}" for r0, r1 in ranges),
                   "--accurate", "-o", f, "--overwrite", "--json-brief")
                sigf.write_text(sig)
            m = mapper(ranges, offset)
            note = f"{p['source']} {fmt(p['start'])}-{fmt(p['end'])}"
            if len(ranges) > 1 or it["removed"]:
                note += f", {len(ranges) - 1} cut(s) inside, {len(it['removed'])} filler(s)"
        length = probe_duration(f)
        plan.append({**it, "map": m, "start": offset, "length": length})
        part_files.append(f)
        print(f"  part {p['id']}: {note} ({length:.2f}s)  {p.get('title', '')}")
        offset += length - (junc[i + 1][1] if i + 1 < len(items) else 0.0)
        if i > 0 and mixed:
            note_t = junc[i]
            print(f"      ↳ in: {note_t[0]}" + (f" {note_t[1]:g}s" if note_t[1] else ""))
    by_id = {it["part"]["id"]: it for it in plan}

    # 2. join with transitions, normalising size / fps / audio
    cur = stage(stages, "1-joined")
    if mixed:
        join_mixed(part_files, [it["length"] for it in plan], junc, W, H, FPS, story.get("fit", "pad"), cur, a.draft)
    elif len(part_files) == 1:
        ff("fit", part_files[0], "--width", str(W), "--height", str(H), "--fit", story.get("fit", "pad"),
           "--fps", str(FPS), "-o", cur, "--overwrite", "--json-brief", *fast)
    else:
        args = [*part_files, "--transition", ttype, "-o", cur, "--overwrite", "--json-brief",
                "--width", str(W), "--height", str(H), "--fps", str(FPS), "--fit", story.get("fit", "pad"), *fast]
        if ttype != "none":
            args += ["--duration", str(tdur)]
        ff("join", *args)

    # 3. b-roll cutaways over the edit (picture only by default; the voice keeps going)
    brolls = []
    for b in story.get("broll", []):
        t = final_time(b, by_id)
        if t is None:
            continue
        if "motion" in b:
            bkey = hashlib.sha256(json.dumps(b["motion"], sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
            ins = proj / "parts" / f"broll_{bkey}_{W}x{H}.mp4"
            vf_motion.render_motion(proj, b["motion"], ins, W, H, FPS, alpha=False, draft=a.draft)
            frm = 0.0
        else:
            if b.get("source") not in srcs:
                sys.exit(f"broll: unknown source {b.get('source')!r}")
            ins, frm = srcs[b["source"]], float(b.get("from", 0))
        brolls.append((ins, t, float(b.get("duration", 3)), frm))
    if brolls:
        nxt = stage(stages, "2-broll")
        args = [cur]
        for ins, t, d, frm in brolls:
            args += ["--insert", ins, "--at", f"{t:.3f}", "--duration", f"{d:.3f}", "--from", f"{frm:.3f}"]
        ff("broll", *args, "--audio", story.get("broll_audio", "a"), "-o", nxt, "--overwrite", "--json-brief", *fast)
        cur = nxt
        print(f"  b-roll: {len(brolls)} cutaway(s)")

    # 4. look: one colour pass over the whole edit
    look = story.get("look")
    if look:
        corr = {k: look[k] for k in ("exposure", "contrast", "saturation", "temperature", "tint", "gamma",
                                     "lift", "gain") if k in look}
        if corr:  # correction first (white balance, exposure), then the creative LUT on top
            nxt = stage(stages, "3-correct")
            ff("color", cur, "--correct", *[x for k, v in corr.items() for x in (f"--{k}", str(v))],
               "-o", nxt, "--overwrite", "--json-brief", *fast)
            cur = nxt
        if look.get("lut"):
            nxt = stage(stages, "3-lut")
            args = [cur, "--lut", str((proj / look["lut"]).resolve()), "-o", nxt, "--overwrite", "--json-brief"]
            if "lut_strength" in look:
                args += ["--lut-strength", str(look["lut_strength"])]
            ff("color", *args, *fast)
            cur = nxt

    # 5. overlays: motion graphics with alpha (lower thirds, stats…), images, the brand logo
    motion_layers, image_layers = [], []
    for k, o in enumerate(story.get("overlays", [])):
        t = 0.0 if o.get("whole") else final_time(o, by_id)  # a whole-video layer belongs to no part
        if t is None:
            continue
        if "motion" in o:
            spec = dict(o["motion"])
            mov = proj / "motion" / "renders" / f"ov{k}_{spec['template']}_{W}x{H}.mov"
            vf_motion.render_motion(proj, spec, mov, W, H, FPS, alpha=True, draft=a.draft)
            motion_layers.append((mov, t, probe_duration(mov)))
        else:
            image_layers.append((o, t))
    if motion_layers:
        nxt = stage(stages, "4-motion")
        cmd = [ffbin("ffmpeg"), "-v", "error", "-y", "-i", cur]
        for mov, t, _ in motion_layers:
            cmd += ["-itsoffset", f"{t:.3f}", "-i", mov]
        chain, last = [], "[0:v]"
        for n, (_, t, d) in enumerate(motion_layers, 1):
            chain.append(f"[{n}:v]scale={W}:{H},format=yuva420p[m{n}]")
            chain.append(f"{last}[m{n}]overlay=0:0:eof_action=pass:enable='between(t,{t:.3f},{t + d:.3f})'[v{n}]")
            last = f"[v{n}]"
        cmd += ["-filter_complex", ";".join(chain), "-map", last, "-map", "0:a?", "-c:v", "libx264",
                "-preset", "veryfast" if a.draft else "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                "-c:a", "copy", "-movflags", "+faststart", nxt]
        run(cmd, check=True)
        cur = nxt
        print(f"  overlays: {len(motion_layers)} motion graphic(s)")
    brand_file = proj / "brand.json"
    for n, (o, t) in enumerate(image_layers):
        nxt = stage(stages, f"5-image{n}")
        args = [cur, "-o", nxt, "--overwrite", "--json-brief", "--position", o.get("position", "top-right")]
        if o.get("logo"):
            if not brand_file.exists():
                sys.exit("overlay logo: needs projects/<name>/brand.json with a logo")
            args += ["--logo", "--brand", brand_file]
        else:
            args += ["--image", str((proj / o["image"]).resolve())]
        if "scale" in o:
            args += ["--scale", str(o["scale"])]
        if "opacity" in o:
            args += ["--opacity", str(o["opacity"])]
        if not o.get("whole", False):
            args += ["--start", f"{t:.3f}"]
            if o.get("duration"):
                args += ["--end", f"{t + float(o['duration']):.3f}"]
        ff("overlay", *args, *fast)
        cur = nxt

    # 6. audio: voice-over, then music under it
    vo = story.get("voiceover")
    if vo:
        vfile = (proj / vo.get("file", "voice/voiceover.wav")).resolve()
        aligned = stages / "vo_aligned.wav"
        at_ms = int(float(vo.get("at", 0)) * 1000)
        run([ffbin("ffmpeg"), "-v", "error", "-y", "-i", vfile, "-af", f"adelay={at_ms}:all=1,"
             f"volume={vo.get('gain', 0)}dB", "-ar", "48000", aligned], check=True)
        nxt = stage(stages, "6-voice")
        if vo.get("mode", "replace") == "replace":
            ff("audio", cur, "--replace", aligned, "-o", nxt, "--overwrite", "--json-brief")
        else:  # keep the footage's own sound under the narration
            run([ffbin("ffmpeg"), "-v", "error", "-y", "-i", cur, "-i", aligned, "-filter_complex",
                 f"[0:a]volume={vo.get('bed_db', -12)}dB[b];[b][1:a]amix=inputs=2:normalize=0:duration=first[a]",
                 "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", nxt], check=True)
        cur = nxt
        print(f"  voice-over: {vfile.name} at {vo.get('at', 0)}s ({vo.get('mode', 'replace')})")
    music = story.get("music")
    if music:
        nxt = stage(stages, "7-music")
        args = [cur, "--music", str((proj / music["file"]).resolve()), "--music-volume", str(music.get("volume", -20)),
                "-o", nxt, "--overwrite", "--json-brief"]
        if music.get("duck", True):
            args += ["--duck", "--duck-amount", str(music.get("duck_amount", 12))]
        if music.get("loop", True):
            args += ["--music-loop"]
        if music.get("fade_out", 3):
            args += ["--music-fade-out", str(music.get("fade_out", 3))]
        ff("audio", *args)
        cur = nxt
        print(f"  music: {Path(music['file']).name}")

    # 7. captions on the final timeline (+ word timings for karaoke)
    cap = story.get("captions", {"enabled": True})
    if cap.get("enabled", True):
        cues = caption_cues(proj, story, plan)
        if cues:
            srt = write_caption_files(proj, cues, "captions")
            nxt = stage(stages, "8-captions")
            lang = cap.get("language", "he")
            args = [cur, "--srt", f"{srt}:{lang}", "--language", lang, "--position", cap.get("position", "bottom"),
                    "--max-lines", str(cap.get("max_lines", 2)), "-o", nxt, "--overwrite", "--json-brief"]
            brand = vf_motion.load_brand(proj)
            font = cap.get("font") or brand.get("font") or ("Arial Hebrew" if sys.platform == "darwin" else "")
            if font:  # elsewhere caption.py picks an installed font that has the script's glyphs
                args += ["--font", font]
            if brand_file.exists():
                args += ["--brand", brand_file]
            for key, flag in (("size", "--size"), ("animate", "--animate")):
                if cap.get(key):
                    args += [flag, str(cap[key])]
            if cap.get("karaoke"):
                args += ["--karaoke", "--karaoke-style", cap.get("karaoke_style", "sweep")]
            ff("caption", *args, *fast)
            cur = nxt
            print(f"  captions: {len(cues)} cue(s)" + (" + word timings" if any(c['words'] for c in cues) else ""))
            # second languages: same timing, translated text (translations/<lang>.json {"cues": {key: text}})
            for tlang, tconf in cap.get("translations", {}).items():
                tfile = proj / tconf.get("file", f"translations/{tlang}.json")
                if not tfile.exists():
                    sys.exit(f"translation {tlang}: {tfile} not found — write it from captions.srt keys")
                table = json.loads(tfile.read_text(encoding="utf-8")).get("cues", {})
                tcues = [{**c, "text": table[c["key"]], "words": []} for c in cues if c["key"] in table]
                missing = len(cues) - len(tcues)
                if not tcues:
                    print(f"  subtitles {tlang}: no cue translated (ids in {tfile.name} match none of "
                          f"{', '.join(c['key'] for c in cues[:4])}…) — skipped", file=sys.stderr)
                    continue
                tsrt = write_caption_files(proj, tcues, f"captions.{tlang}")
                nxt = stage(stages, f"9-sub-{tlang}")
                if tconf.get("mode", "mux") == "mux":
                    ff("caption", cur, "--srt", f"{tsrt}:{tlang}", "--mode", "mux", "-o", nxt, "--overwrite",
                       "--json-brief")
                else:
                    ff("caption", cur, "--srt", f"{tsrt}:{tlang}", "--language", tlang,
                       "--position", tconf.get("position", "top"), "--max-lines", "2", "-o", nxt,
                       "--overwrite", "--json-brief", *fast)
                cur = nxt
                print(f"  subtitles {tlang}: {len(tcues)} cue(s), {tconf.get('mode', 'mux')}"
                      + (f" — {missing} untranslated" if missing else ""))

    # 8. loudness for delivery
    if story.get("loudness") is not None and not a.draft:
        nxt = stage(stages, "10-loudness")
        ff("loudness", cur, "-I", str(story["loudness"]), "-o", nxt, "--overwrite", "--json-brief")
        cur = nxt

    final = proj / "renders" / f"{name}.mp4"
    shutil.copy(cur, final)
    ff("look", final, "--tiles", "3x2", "-o", proj / "renders" / f"{name}_sheet.png", "--overwrite", "--json-brief")
    if not a.keep_stages:
        shutil.rmtree(stages, ignore_errors=True)
    problems = qa_check(final, offset, W, H, story, cap)
    print(f"done: {final}  ({probe_duration(final):.2f}s, planned {offset:.2f}s, {W}x{H}@{FPS})")
    write_timeline_data(proj, story, plan, junc, offset, name, final)
    if problems:
        print("QA: " + "; ".join(problems) + " — look before delivering", file=sys.stderr)
        if not getattr(a, "keep_going", False):
            sys.exit(2)
    else:
        print("QA: ok (length, size, video and audio streams, captions)")
    return problems


def write_timeline_data(proj: Path, story: dict, plan: list[dict], junc: list, total: float, name: str,
                        final: Path) -> None:
    """renders/<name>.timeline.json — every track on the final timeline, for the review page."""
    by_id = {it["part"]["id"]: it for it in plan}
    parts = []
    for i, it in enumerate(plan):
        p = it["part"]
        parts.append({"id": p["id"], "start": round(it["start"], 3), "length": round(it["length"], 3),
                      "title": p.get("title", ""), "why": p.get("why", ""),
                      "kind": "motion" if "motion" in p else "footage",
                      "label": p["motion"]["template"] if "motion" in p else p["source"],
                      "src": None if "motion" in p else [p["start"], p["end"]],
                      "transition_in": None if i == 0 else {"type": junc[i][0], "duration": round(junc[i][1], 3)}})
    def placed(items, label):
        out = []
        for o in items:
            t = 0.0 if o.get("whole") else final_time(o, by_id)
            if t is None:
                continue
            d = total - t if o.get("whole") else float(o.get("duration") or (o.get("motion") or {}).get("duration") or 4)
            out.append({"start": round(t, 3), "length": round(d, 3), "label": label(o)})
        return out
    overlays = placed(story.get("overlays", []), lambda o: (o.get("motion") or {}).get("template")
                      or ("logo" if o.get("logo") else Path(o.get("image", "image")).name))
    broll = placed(story.get("broll", []), lambda o: o.get("source") or (o.get("motion") or {}).get("template", "motion"))
    cues = []
    srt = proj / "captions.srt"
    if srt.exists():
        for block in srt.read_text(encoding="utf-8").strip().split("\n\n"):
            lines = block.splitlines()
            m = re.match(r"(\d+):(\d+):(\d+),(\d+) --> (\d+):(\d+):(\d+),(\d+)", lines[1]) if len(lines) > 2 else None
            if m:
                g = [int(x) for x in m.groups()]
                st = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
                en = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
                cues.append({"start": round(st, 3), "length": round(en - st, 3), "label": " ".join(lines[2:])})
    audio = []
    vo = story.get("voiceover")
    if vo and (proj / vo.get("file", "voice/voiceover.wav")).exists():
        at = float(vo.get("at", 0))
        audio.append({"start": at, "length": round(min(total - at, probe_duration(proj / vo.get("file", "voice/voiceover.wav"))), 3),
                      "label": "voice-over"})
    if story.get("music"):
        audio.append({"start": 0.0, "length": round(total, 3), "label": "music: " + Path(story["music"]["file"]).name})
    data = {"name": name, "video": final.name, "title": story.get("title", proj.name), "duration": round(total, 3),
            "tracks": {"parts": parts, "overlays": overlays, "broll": broll, "captions": cues, "audio": audio},
            "transition_types": sorted(xfade_types())}
    (final.parent / f"{name}.timeline.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def qa_check(final: Path, planned: float, W: int, H: int, story: dict, cap: dict) -> list[str]:
    """What a render must be before it is reported as done."""
    r = subprocess.run([ffbin("ffprobe"), "-v", "error", "-show_entries",
                        "stream=codec_type,width,height:format=duration", "-of", "json", str(final)],
                       capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
    except ValueError:
        return ["the file cannot be read"]
    streams = d.get("streams", [])
    v = [s for s in streams if s.get("codec_type") == "video"]
    out = []
    if not v:
        out.append("no video stream")
    elif (v[0].get("width"), v[0].get("height")) != (W, H):
        out.append(f"size {v[0].get('width')}x{v[0].get('height')}, expected {W}x{H}")
    if not any(s.get("codec_type") == "audio" for s in streams):
        out.append("no audio stream")
    dur = float(d.get("format", {}).get("duration", 0))
    if abs(dur - planned) > max(0.3, planned * 0.02):
        out.append(f"length {dur:.2f}s, planned {planned:.2f}s")
    if cap.get("enabled", True) and not (final.parent.parent / "captions.srt").exists():
        out.append("captions were expected but none were made")
    langs = cap.get("translations", {})
    subs = sum(1 for s in streams if s.get("codec_type") == "subtitle")
    muxed = sum(1 for t in langs.values() if t.get("mode", "mux") == "mux")
    if subs < muxed:
        out.append(f"{muxed} subtitle track(s) expected, {subs} found")
    return out


def cmd_voice(a) -> None:
    import vf_voice
    proj = project_dir(a.project)
    script = proj / a.script
    if not script.exists():
        sys.exit(f"{script} not found — write the narration there, one paragraph per beat")
    only = [int(x) for x in a.only.split(",")] if a.only else None
    vo = vf_voice.make_voiceover(proj, script, a.provider, a.voice, a.language, a.model, a.speed, a.gap, only, ffbin)
    meta = json.loads((proj / "voice" / "beats.json").read_text(encoding="utf-8"))
    for b in meta["beats"]:
        print(f"  beat {b['n']}: {fmt(b['start'])}-{fmt(b['end'])} ({b['end'] - b['start']:.2f}s)  {b['text'][:70]}")
    print(f"  total {meta['total']:.2f}s -> {vo}")
    # words for captions and karaoke: transcribe the narration itself
    model = whisper_model()
    if model and model.exists() and shutil.which("whisper-cli"):
        tmp = proj / "transcript" / ".voiceover.raw"
        tmp.mkdir(parents=True, exist_ok=True)
        segs = whisper_cpp_transcribe(vo, tmp, a.language, "", model)
        shutil.rmtree(tmp)
        fixed, total = script_spelling(segs, meta)
        print(f"  script spelling applied to {fixed}/{total} beats (the rest keep whisper's words)")
        (proj / "transcript" / "voiceover.json").write_text(json.dumps(
            {"meta": {"source": "voice/voiceover.wav", "engine": "whisper.cpp", "language": a.language,
                      "units": "seconds", "word_timings": True}, "segments": segs}, ensure_ascii=False, indent=1),
            encoding="utf-8")
        print(f"  transcript/voiceover.json: {len(segs)} segments with word timings")
    else:
        print("  note: no whisper.cpp model — captions cannot follow the voice-over until it is transcribed",
              file=sys.stderr)


def script_spelling(segs: list[dict], meta: dict) -> tuple[int, int]:
    """The narration's text is known exactly — it is the script. Keep whisper's timings, take the
    words from the script: per beat, when whisper heard as many words as the script has, swap them
    in one for one and rebuild each segment's text. A beat that does not line up is left as heard."""
    words = [w for s in segs for w in s["words"]]
    fixed = 0
    for b in meta["beats"]:
        script_words = b["text"].split()
        heard = [w for w in words if b["start"] - 0.15 <= w["start"] <= b["end"] + 0.15]
        if len(heard) == len(script_words):
            for w, sw in zip(heard, script_words):
                w["word"] = sw
            fixed += 1
    for s in segs:
        if s["words"]:
            s["text"] = " ".join(w["word"] for w in s["words"])
    return fixed, len(meta["beats"])


def cmd_beats(a) -> None:
    proj = project_dir(a.project)
    music = (proj / a.music).resolve()
    r = run([sys.executable, SKILL_SCRIPTS / "scenes.py", music, "--beats", "--json"], capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
    except ValueError:
        sys.exit(r.stdout[-1500:] + r.stderr[-1500:])
    grid = d.get("beat_grid") or {}
    times = d.get("beats") if isinstance(d.get("beats"), list) else grid.get("beats", [])
    tempo = grid.get("tempo_bpm") or grid.get("tempo")
    print(f"  tempo: {tempo or '?'} BPM, {len(times)} beats, confidence {grid.get('confidence', '?')}")
    if not times:
        print("  no beat found — a track without a clear pulse; cut by phrase instead")
    if times:
        bar = [round(t, 2) for t in times[::4]]
        print(f"  every 4th beat (bar starts): {bar[:40]}{' …' if len(bar) > 40 else ''}")
    (proj / "renders").mkdir(exist_ok=True)
    (proj / "renders" / f"{Path(a.music).stem}.beats.json").write_text(json.dumps(d, indent=1), encoding="utf-8")


def cmd_review(a) -> None:
    import vf_review
    proj = project_dir(a.project)
    name = (f"{a.version}_draft" if a.draft else a.version) if a.version else ("draft" if a.draft else "final")
    video = proj / "renders" / f"{name}.mp4"
    if not video.exists():
        sys.exit(f"{video} not found — render it first")
    story = read_json(proj / "story.json", "story.json") if (proj / "story.json").exists() else {}
    page = vf_review.write_review(proj, video, story.get("title", proj.name), a.lang)
    print(f"  {page}\n  send the client the renders/ folder (or both files); notes come back as text")


def cmd_watch(a) -> None:
    """A vision model looks at the footage and suggests; it never cuts. See tools/vf_vision.py."""
    import vf_vision
    import vf_voice
    proj = project_dir(a.project)
    vf_voice.load_env(proj)
    v = vf_vision.Vision.from_args(a)
    where = "this machine" if v.label()["local"] else f"{v.host} (cloud)"
    print(f"  watching with {v.model} on {where}")
    ffmpeg = ffbin("ffmpeg")
    with vf_vision.tempdir() as td:
        tmp = Path(td)
        if a.task == "log":
            srcs = sources(proj)
            only = set(a.only.split(",")) if a.only else None
            for name, path in srcs.items():
                if only and name not in only:
                    continue
                if not path.exists():
                    print(f"  {name}: link broken, skipped")
                    continue
                dur = probe_duration(path)
                every = a.every or min(10.0, max(1.0, round(dur / 48, 1)))
                segs = load_transcript(proj, name) if (proj / "transcript" / f"{name}.json").exists() else []
                (proj / "visual").mkdir(exist_ok=True)
                out = proj / "visual" / f"{name}.watch.json"
                doc = vf_vision.watch_log(v, ffmpeg, name, path, dur, segs, out, every, a.batch, tmp)
                usable = [s for s in doc["shots"] if s.get("use") in ("hero", "broll")]
                print(f"  {name}: {len(doc['shots'])} shot(s), {len(usable)} suggested as hero/b-roll -> {out}")
                for s in usable[:8]:
                    print(f"    {fmt(s['start'])}-{fmt(s['end'])} [{s.get('use')}, q{s.get('quality', '?')}"
                          f" e{s.get('energy', '?')}] {str(s.get('description', ''))[:90]}")
        elif a.task == "clips":
            path = proj / "candidates.json"
            data = read_json(path, "candidates.json (run vf.py candidates first)")
            cands = data.get("candidates", [])
            if not cands:
                sys.exit("candidates.json is empty — run vf.py candidates first")
            vf_vision.watch_clips(v, ffmpeg, cands, sources(proj), tmp)
            for c in cands:
                if "visual" in c:
                    c["combined"] = round(c["score"] + 1.5 * (c["visual"]["score"] - 3), 2)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
            scored = sorted(cands, key=lambda c: -c.get("combined", c["score"]))
            for k, c in enumerate(scored, 1):
                vis = c.get("visual", {})
                print(f"  #{k} [{c['source']} {fmt(c['start'])}-{fmt(c['end'])}] text {c['score']}"
                      f" visual {vis.get('score', '-')} -> {c.get('combined', c['score'])}  {vis.get('why', '')[:80]}")
            print(f"  -> {path} (each candidate now has \"visual\" and \"combined\")")
        else:
            renders = proj / "renders"
            video = renders / f"{a.render}.mp4" if a.render else next(
                (renders / f"{n}.mp4" for n in ("final", "draft") if (renders / f"{n}.mp4").exists()), None)
            if not video or not video.exists():
                sys.exit(f"no render to watch{' named ' + a.render if a.render else ''} — vf.py render first")
            r = subprocess.run([ffbin("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries",
                                "stream=width,height", "-of", "csv=p=0", str(video)], capture_output=True, text=True)
            w, h = (int(x) for x in r.stdout.strip().split(",")[:2])
            dur = probe_duration(video)
            every = a.every or min(4.0, max(1.0, round(dur / 40, 1)))
            out = video.with_suffix(".watch.json")
            doc = vf_vision.watch_qa(v, ffmpeg, video, dur, w, h, out, every, a.batch, tmp)
            print(f"  {video.name}: {len(doc['issues'])} possible issue(s) -> {out}")
            for i in doc["issues"]:
                span = fmt(i["at"]) + (f"-{fmt(i['until'])}" if "until" in i else "")
                print(f"    {span} [{i['severity']}, {i['kind']}] {i['problem']}")
            print("  these are a model's suggestions: look at each moment (vf.py ff look) before changing anything")


def cmd_export(a) -> None:
    import vf_motion, vf_review
    proj = project_dir(a.project)
    story = load_story(proj, a.version)
    srcs = sources(proj)
    validate_story(proj, story, srcs)
    W, H, FPS = frame_size(story, srcs)
    FPS = fps_arg(FPS)
    clips = []
    multi = False
    for it in plan_parts(proj, story, srcs):
        p = it["part"]
        if it["ranges"] is None:
            f = proj / "parts" / f"{p['id']}_{W}x{H}.mp4"
            vf_motion.render_motion(proj, p["motion"], f, W, H, FPS, alpha=False, draft=False)
            clips.append({"src": str(f), "in": 0.0, "out": probe_duration(f)})
        else:
            multi |= len(it["ranges"]) > 1
            clips += [{"src": str(srcs[p["source"]].resolve()), "in": r0, "out": r1} for r0, r1 in it["ranges"]]
    tr = story.get("transition", {"type": "fade", "duration": 0.5})
    if multi and tr.get("type") != "none":
        print("  note: parts with cleaned-up cuts inside become several clips; the transition is exported "
              "as a straight cut so it does not land inside a sentence", file=sys.stderr)
        tr = {"type": "none", "duration": 0}
    dest = proj / "renders" / f"{a.version or 'edit'}.{a.format}"
    vf_review.export_timeline(proj, story, clips, tr, dest, W, H, round(fps_float(FPS), 3), SKILL_SCRIPTS, run)
    print(f"  {dest}  ({len(clips)} clips) — open in Resolve / Premiere / Final Cut; captions: captions.srt")


def cmd_ff(a) -> None:
    r = run([sys.executable, SKILL_SCRIPTS / f"{a.tool}.py", *a.args])
    sys.exit(r.returncode)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor").set_defaults(fn=cmd_doctor)

    p = sub.add_parser("new", help="create a project from video files and/or folders of videos")
    p.add_argument("name"); p.add_argument("videos", nargs="*", help="video files or folders (none: an empty project)")
    p.add_argument("--copy", action="store_true",
                   help="copy the sources in instead of linking (external drive, cloud folder, "
                        "or originals you will move)")
    p.set_defaults(fn=cmd_new)

    p = sub.add_parser("transcribe"); p.add_argument("project"); p.add_argument("--language", default="he")
    p.add_argument("--prompt", default="", help="names and terms, as a short sentence")
    p.add_argument("--model", default="", help="a whisper.cpp ggml model (default: VF_WHISPER_MODEL / ivrit.ai)")
    p.add_argument("--force", action="store_true"); p.set_defaults(fn=cmd_transcribe)

    p = sub.add_parser("transcript"); p.add_argument("project")
    p.add_argument("--words", action="store_true", help="also print every word with its time (* = filler)")
    p.set_defaults(fn=cmd_transcript)

    p = sub.add_parser("frames"); p.add_argument("project")
    p.add_argument("--every", type=float, default=0, help="seconds between tiles (default: ~48 tiles per source)")
    p.add_argument("--width", type=int, default=1280); p.add_argument("--threshold", type=float, default=0.3)
    p.set_defaults(fn=cmd_frames)

    p = sub.add_parser("reference", help="study a video to imitate: pace, transitions, look, captions")
    p.add_argument("project"); p.add_argument("video")
    p.add_argument("--every", type=float, default=0, help="seconds between tiles (default ~48 tiles)")
    p.add_argument("--threshold", type=float, default=0.3); p.set_defaults(fn=cmd_reference)

    p = sub.add_parser("candidates", help="moments that could stand alone as shorts, ranked for Claude to judge")
    p.add_argument("project"); p.add_argument("--min", type=float, default=15); p.add_argument("--max", type=float, default=60)
    p.add_argument("--top", type=int, default=12); p.add_argument("--language", default="he")
    p.set_defaults(fn=cmd_candidates)

    p = sub.add_parser("clips", help="render clips.json as vertical shorts")
    p.add_argument("project"); p.add_argument("--only", default="", help="clip ids, e.g. c1,c3")
    p.add_argument("--draft", action="store_true"); p.set_defaults(fn=cmd_clips)

    p = sub.add_parser("status", help="where each project stands, and the next step")
    p.add_argument("project", nargs="?", default=""); p.set_defaults(fn=cmd_status)

    p = sub.add_parser("scenes"); p.add_argument("project"); p.add_argument("--threshold", type=float, default=0.3)
    p.set_defaults(fn=cmd_scenes)

    p = sub.add_parser("render"); p.add_argument("project"); p.add_argument("--draft", action="store_true")
    p.add_argument("--version", default="", help="render a version from story.json's versions (e.g. 30s, reels)")
    p.add_argument("--force", action="store_true", help="re-cut every part")
    p.add_argument("--keep-stages", action="store_true", help="keep the intermediate files of each stage")
    p.set_defaults(fn=cmd_render)

    p = sub.add_parser("voice", help="narration from script.md with a TTS provider")
    p.add_argument("project"); p.add_argument("--script", default="script.md")
    p.add_argument("--provider", default="say" if sys.platform == "darwin" else None,
                   choices=["elevenlabs", "azure", "google", "openai", "say"],
                   required=sys.platform != "darwin")
    p.add_argument("--voice", default=""); p.add_argument("--model", default="")
    p.add_argument("--language", default="he"); p.add_argument("--speed", type=float, default=1.0)
    p.add_argument("--gap", type=float, default=0.6, help="seconds of silence between beats")
    p.add_argument("--only", default="", help="re-voice only these beats, e.g. 2,5")
    p.set_defaults(fn=cmd_voice)

    p = sub.add_parser("beats", help="tempo and beat grid of a music file")
    p.add_argument("project"); p.add_argument("music"); p.set_defaults(fn=cmd_beats)

    p = sub.add_parser("review", help="video + visual timeline + notes, one static page next to the render")
    p.add_argument("project"); p.add_argument("--version", default="")
    p.add_argument("--draft", action="store_true", help="the draft render (or <version>_draft)")
    p.add_argument("--lang", default="he", choices=["he", "en"], help="the page's starting language (it has a toggle)")
    p.set_defaults(fn=cmd_review)

    p = sub.add_parser("watch", help="a vision model looks and suggests: shot log, clip scores, render QA")
    p.add_argument("project")
    p.add_argument("--task", default="log", choices=["log", "clips", "qa"],
                   help="log: shots per source; clips: visual score for candidates.json; qa: problems in a render")
    p.add_argument("--provider", default="", help="openai (any OpenAI-compatible server, default) or gemini")
    p.add_argument("--base-url", default="", help="where the API sits (default VF_VISION_BASE_URL, else LM Studio on localhost)")
    p.add_argument("--model", default="", help="model id (default VF_VISION_MODEL, else the first the server lists)")
    p.add_argument("--allow-cloud", action="store_true", help="allow sending footage to an endpoint off this machine")
    p.add_argument("--every", type=float, default=0, help="seconds between frames (log, qa)")
    p.add_argument("--batch", type=int, default=6, help="frames per request (smaller for small local models)")
    p.add_argument("--only", default="", help="log: these sources only, e.g. intro,ceo")
    p.add_argument("--render", default="", help="qa: the render to watch, e.g. final, draft, reels (default final, else draft)")
    p.set_defaults(fn=cmd_watch)

    p = sub.add_parser("export", help="the edit as an editor timeline (Resolve / Premiere / Final Cut)")
    p.add_argument("project"); p.add_argument("--format", default="fcpxml", choices=["fcpxml", "edl", "otio"])
    p.add_argument("--version", default=""); p.set_defaults(fn=cmd_export)

    p = sub.add_parser("ff"); p.add_argument("tool"); p.add_argument("args", nargs=argparse.REMAINDER)
    p.set_defaults(fn=cmd_ff)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()

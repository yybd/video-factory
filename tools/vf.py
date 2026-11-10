#!/usr/bin/env python3
"""video-factory orchestrator CLI — the mechanical half of the video-orchestrator skill.

The skill (Claude) decides *what* to cut and in what order; this script does the
deterministic work around that decision:

  vf.py doctor                         check ffmpeg-full, ffmpeg-skill, transcription engines
  vf.py new <name> <video|folder>...   create projects/<name>/ with the sources linked in (--copy to copy)
  vf.py transcribe <project>           transcript with WORD timings per source -> transcript/<src>.json
  vf.py transcript <project> [--words] print transcripts (and visual notes) as "[src mm:ss.ss-mm:ss.ss] text"
  vf.py frames <project> [--every N]   contact sheets with timecodes + scene list, for footage without speech
  vf.py scenes <project>               visual scene changes per source
  vf.py render <project> [--draft] [--version V]   story.json -> renders/final.mp4 (or draft / <version>)
  vf.py voice <project> --provider P   narration from script.md (ElevenLabs, Azure, Google, OpenAI, or macOS say)
  vf.py beats <project> <music>        tempo and beat grid, to cut on the music
  vf.py review <project>               a page for the client to leave timecoded notes
  vf.py export <project> [--format F]  the edit as a Resolve / Premiere / Final Cut timeline
  vf.py ff <tool> [args...]            run an ffmpeg-skill script with ffmpeg-full on PATH

Standard library only.
"""
from __future__ import annotations

import argparse
import glob
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


def local_models_dir() -> Path | None:
    """Optional: a local-models project (ivrit.ai Whisper behind `local-models transcribe`).
    Sentence timings only — used when whisper.cpp is not available."""
    env = os.environ.get("VF_LOCAL_MODELS")
    if env:
        return Path(env)
    dev = os.environ.get("DEV_ROOT")
    if dev and Path(dev, "local-models", "mcp").exists():
        return Path(dev, "local-models", "mcp")
    return None


def run(cmd: list, **kw) -> subprocess.CompletedProcess:
    print("  $", " ".join(str(c) for c in cmd), file=sys.stderr)
    return subprocess.run([str(c) for c in cmd], env=tool_env(), **kw)


def ff(tool: str, *args) -> None:
    """Run one ffmpeg-skill script; stop on failure."""
    r = run([sys.executable, SKILL_SCRIPTS / f"{tool}.py", *args])
    if r.returncode != 0:
        sys.exit(f"ffmpeg-skill {tool} failed (exit {r.returncode})")


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


def local_models_transcribe(path: Path, workdir: Path, a, lm: Path) -> list[dict]:
    cmd = ["uv", "run", "-q", "--project", lm, "local-models", "transcribe", path,
           "--out", workdir, "--language", a.language]
    if a.prompt:
        cmd += ["--prompt", a.prompt]
    if a.presets:
        cmd += ["--presets", a.presets]
    if run(cmd).returncode != 0:
        sys.exit("local-models transcription failed")
    raw = json.loads(next(workdir.glob("*.json")).read_text(encoding="utf-8"))
    return [{"start": s["start"] / 1000.0, "end": s["end"] / 1000.0, "text": s["text"].strip(), "words": []}
            for s in raw.get("segments", [])]  # local-models reports milliseconds, no words


# ---------------------------------------------------------------- commands

def cmd_doctor(_a) -> None:
    ok = True
    b = ffmpeg_full_bin()
    print(f"ffmpeg-full : {b or 'MISSING — brew install ffmpeg-full'}")
    if b:
        filters = subprocess.run([str(b / "ffmpeg"), "-hide_banner", "-filters"],
                                 capture_output=True, text=True).stdout
        for f in ("subtitles", "ass", "drawtext", "xfade", "tile"):
            has = f" {f} " in filters
            ok &= has
            print(f"  filter {f:<10} {'ok' if has else 'MISSING'}")
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
    lm = local_models_dir()
    print(f"local-models: {lm or '— (optional fallback, sentence timings only)'}")
    if not ((cli and m and m.exists()) or lm):
        ok = False
        print("no transcription engine available")
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
    proj = PROJECTS / a.name
    for sub in ("source", "transcript", "visual", "parts", "renders"):
        (proj / sub).mkdir(parents=True, exist_ok=True)
    for v in inputs:
        if is_cloud_placeholder(v):
            sys.exit(f"{v} is a cloud placeholder, not on disk yet — download it (Finder: "
                     "Download Now) and run again")
        dst = proj / "source" / v.name
        if dst.exists() or dst.is_symlink():
            same = dst.resolve() == v or (dst.exists() and dst.samefile(v))
            if not same:
                sys.exit(f"source/{v.name} already exists and is a different file — rename one of them")
            print(f"  source {dst.name}: already there")
            continue
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
    use_whisper = bool(model and model.exists() and shutil.which("whisper-cli")) and not a.local_models
    lm = local_models_dir()
    if not use_whisper and not lm:
        sys.exit("no transcription engine: install whisper.cpp and an ivrit.ai ggml model (see README), "
                 "or set VF_LOCAL_MODELS")
    for name, path in sources(proj).items():
        out_json = proj / "transcript" / f"{name}.json"
        if out_json.exists() and not a.force:
            print(f"  {name}: transcript exists (use --force to redo)")
            continue
        tmp = proj / "transcript" / f".{name}.raw"
        tmp.mkdir(exist_ok=True)
        if use_whisper:
            engine = f"whisper.cpp {model.parent.parent.parent.name if 'snapshots' in str(model) else model.name}"
            segs = whisper_cpp_transcribe(path.resolve(), tmp, a.language, a.prompt, model)
        else:
            engine = "local-models (ivrit.ai whisper, sentence timings)"
            segs = local_models_transcribe(path.resolve(), tmp, a, lm)
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
        vf = proj / "visual" / f"{name}.json"
        if vf.exists():
            for v in json.loads(vf.read_text(encoding="utf-8")).get("shots", []):
                rows.append((float(v["start"]), f"[{name} {fmt(v['start'])}-{fmt(v['end'])} VISUAL] "
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
        for old in out.glob(f"{name}_sheet_*.png"):
            old.unlink()
        vf = (f"fps=1/{every},scale={a.width // 4}:-2,"
              f"drawtext=text='%{{pts\\:hms}}':x=6:y=6:fontsize=18:fontcolor=white:box=1:boxcolor=black@0.6,"
              f"tile=4x3:padding=4:color=black")
        run([ffbin("ffmpeg"), "-v", "error", "-y", "-i", path, "-vf", vf, "-fps_mode", "vfr",
             out / f"{name}_sheet_%03d.png"], check=True)
        sheets = sorted(out.glob(f"{name}_sheet_*.png"))
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
                cuts.append((w["start"] - FILLER_PAD, w["end"] + FILLER_PAD))
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
            if t < r0:
                return offset + acc if snap == "next" else None
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
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load_story(proj: Path, version: str | None) -> dict:
    story = json.loads((proj / "story.json").read_text(encoding="utf-8"))
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


def frame_size(story: dict, srcs: dict[str, Path]) -> tuple[int, int, int]:
    out = story.get("output", {})
    w, h = out.get("width"), out.get("height")
    if not (w and h):
        first = next(iter(srcs.values()), None)
        if first:
            r = subprocess.run([ffbin("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries",
                                "stream=width,height", "-of", "csv=p=0", str(first)], capture_output=True, text=True)
            w, h = (int(x) for x in r.stdout.strip().split(",")[:2])
        else:
            w, h = 1920, 1080
    return int(w), int(h), int(out.get("fps", 30))


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


def cmd_render(a) -> None:
    import vf_motion
    proj = project_dir(a.project)
    story = load_story(proj, a.version)
    name = a.version or ("draft" if a.draft else "final")
    srcs = sources(proj)
    W, H, FPS = frame_size(story, srcs)
    tr = story.get("transition", {"type": "fade", "duration": 0.5})
    ttype, tdur = tr.get("type", "fade"), float(tr.get("duration", 0.5))
    if ttype == "none":
        tdur = 0.0
    stages = proj / "renders" / f".stages-{name}"
    stages.mkdir(parents=True, exist_ok=True)
    fast = ["--fast"] if a.draft else []

    # 1. parts: footage cut frame-accurate (cached by kept ranges); motion cards rendered
    plan, part_files, offset = [], [], 0.0
    items = plan_parts(proj, story, srcs)
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
            sig = json.dumps(ranges)
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
        offset += length - (tdur if i < len(items) - 1 else 0.0)
    by_id = {it["part"]["id"]: it for it in plan}

    # 2. join with transitions, normalising size / fps / audio
    cur = stage(stages, "1-joined")
    if len(part_files) == 1:
        ff("fit", part_files[0], "--width", str(W), "--height", str(H), "-o", cur, "--overwrite", "--json-brief")
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
            ins = proj / "parts" / f"broll_{abs(hash(json.dumps(b, sort_keys=True))) % 10**8}_{W}x{H}.mp4"
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
        nxt = stage(stages, "3-look")
        args = [cur, "-o", nxt, "--overwrite", "--json-brief"]
        if look.get("lut"):
            args += ["--lut", str((proj / look["lut"]).resolve())]
            if "lut_strength" in look:
                args += ["--lut-strength", str(look["lut_strength"])]
        corr = {k: look[k] for k in ("exposure", "contrast", "saturation", "temperature", "tint", "gamma",
                                     "lift", "gain") if k in look}
        if corr:
            args += ["--correct"] + [x for k, v in corr.items() for x in (f"--{k}", str(v))]
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
            args += ["--font", cap.get("font") or brand.get("font") or "Arial Hebrew"]
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
    print(f"done: {final}  ({probe_duration(final):.2f}s, planned {offset:.2f}s, {W}x{H}@{FPS})")


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
    beats = d.get("beats") or d.get("beat_grid") or {}
    times = beats.get("times") or beats.get("beat_times") or d.get("beat_times") or []
    tempo = beats.get("tempo") or d.get("tempo")
    print(f"  tempo: {tempo} BPM, {len(times)} beats, confidence {beats.get('confidence', d.get('confidence'))}")
    if times:
        bar = [round(t, 2) for t in times[::4]]
        print(f"  every 4th beat (bar starts): {bar[:40]}{' …' if len(bar) > 40 else ''}")
    (proj / "renders").mkdir(exist_ok=True)
    (proj / "renders" / f"{Path(a.music).stem}.beats.json").write_text(json.dumps(d, indent=1), encoding="utf-8")


def cmd_review(a) -> None:
    import vf_review
    proj = project_dir(a.project)
    name = a.version or "final"
    video = proj / "renders" / f"{name}.mp4"
    if not video.exists():
        sys.exit(f"{video} not found — render it first")
    story = json.loads((proj / "story.json").read_text(encoding="utf-8")) if (proj / "story.json").exists() else {}
    page = vf_review.write_review(proj, video, story.get("title", proj.name))
    print(f"  {page}\n  send the client the renders/ folder (or both files); notes come back as text")


def cmd_export(a) -> None:
    import vf_motion, vf_review
    proj = project_dir(a.project)
    story = load_story(proj, a.version)
    srcs = sources(proj)
    W, H, FPS = frame_size(story, srcs)
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
    vf_review.export_timeline(proj, story, clips, tr, dest, W, H, FPS, SKILL_SCRIPTS, run)
    print(f"  {dest}  ({len(clips)} clips) — open in Resolve / Premiere / Final Cut; captions: captions.srt")


def cmd_ff(a) -> None:
    r = run([sys.executable, SKILL_SCRIPTS / f"{a.tool}.py", *a.args])
    sys.exit(r.returncode)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor").set_defaults(fn=cmd_doctor)

    p = sub.add_parser("new", help="create a project from video files and/or folders of videos")
    p.add_argument("name"); p.add_argument("videos", nargs="+", help="video files or folders")
    p.add_argument("--copy", action="store_true",
                   help="copy the sources in instead of linking (external drive, cloud folder, "
                        "or originals you will move)")
    p.set_defaults(fn=cmd_new)

    p = sub.add_parser("transcribe"); p.add_argument("project"); p.add_argument("--language", default="he")
    p.add_argument("--prompt", default="", help="names and terms, as a short sentence")
    p.add_argument("--model", default="", help="a whisper.cpp ggml model (default: VF_WHISPER_MODEL / ivrit.ai)")
    p.add_argument("--local-models", action="store_true", help="use local-models (no word timings)")
    p.add_argument("--presets", default="", help="local-models only: bias dictionaries")
    p.add_argument("--force", action="store_true"); p.set_defaults(fn=cmd_transcribe)

    p = sub.add_parser("transcript"); p.add_argument("project")
    p.add_argument("--words", action="store_true", help="also print every word with its time (* = filler)")
    p.set_defaults(fn=cmd_transcript)

    p = sub.add_parser("frames"); p.add_argument("project")
    p.add_argument("--every", type=float, default=0, help="seconds between tiles (default: ~48 tiles per source)")
    p.add_argument("--width", type=int, default=1280); p.add_argument("--threshold", type=float, default=0.3)
    p.set_defaults(fn=cmd_frames)

    p = sub.add_parser("scenes"); p.add_argument("project"); p.add_argument("--threshold", type=float, default=0.3)
    p.set_defaults(fn=cmd_scenes)

    p = sub.add_parser("render"); p.add_argument("project"); p.add_argument("--draft", action="store_true")
    p.add_argument("--version", default="", help="render a version from story.json's versions (e.g. 30s, reels)")
    p.add_argument("--force", action="store_true", help="re-cut every part")
    p.add_argument("--keep-stages", action="store_true", help="keep the intermediate files of each stage")
    p.set_defaults(fn=cmd_render)

    p = sub.add_parser("voice", help="narration from script.md with a TTS provider")
    p.add_argument("project"); p.add_argument("--script", default="script.md")
    p.add_argument("--provider", default="say", choices=["elevenlabs", "azure", "google", "openai", "say"])
    p.add_argument("--voice", default=""); p.add_argument("--model", default="")
    p.add_argument("--language", default="he"); p.add_argument("--speed", type=float, default=1.0)
    p.add_argument("--gap", type=float, default=0.6, help="seconds of silence between beats")
    p.add_argument("--only", default="", help="re-voice only these beats, e.g. 2,5")
    p.set_defaults(fn=cmd_voice)

    p = sub.add_parser("beats", help="tempo and beat grid of a music file")
    p.add_argument("project"); p.add_argument("music"); p.set_defaults(fn=cmd_beats)

    p = sub.add_parser("review", help="a page for the client to leave timecoded notes")
    p.add_argument("project"); p.add_argument("--version", default=""); p.set_defaults(fn=cmd_review)

    p = sub.add_parser("export", help="the edit as an editor timeline (Resolve / Premiere / Final Cut)")
    p.add_argument("project"); p.add_argument("--format", default="fcpxml", choices=["fcpxml", "edl", "otio"])
    p.add_argument("--version", default=""); p.set_defaults(fn=cmd_export)

    p = sub.add_parser("ff"); p.add_argument("tool"); p.add_argument("args", nargs=argparse.REMAINDER)
    p.set_defaults(fn=cmd_ff)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()

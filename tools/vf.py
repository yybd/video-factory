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
  vf.py render <project> [--draft]     story.json -> parts/ -> joined.mp4 -> captions.srt -> final.mp4
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


def build_captions(proj: Path, story: dict, plan: list[dict], xd: float) -> Path | None:
    """Map each transcript cue (and word) into the final timeline; write captions.srt and
    captions.words.json (the word timings ffmpeg-skill's --karaoke reads next to the SRT)."""
    cap = story.get("captions", {})
    overrides = {c["id"]: c for c in cap.get("cues", []) if "id" in c}
    cues: list[tuple[float, float, str]] = []
    out_words: list[dict] = []
    for item in plan:
        p, m = item["part"], item["map"]
        if not p.get("captions", True):
            continue
        for j, s in enumerate(load_transcript(proj, p["source"])):
            if s["end"] <= p["start"] or s["start"] >= p["end"]:
                continue
            kept_words = [w for k, w in enumerate(s["words"])
                          if (s["start"], k) not in item["removed_keys"] and m(w["start"]) is not None]
            st = m(max(s["start"], p["start"]), "next")
            en = m(min(s["end"], p["end"]), "prev")
            if st is None or en is None or en - st < 0.25:
                continue
            key = f"{p['source']}:{j}"
            if key in overrides:
                text = overrides[key]["text"]
            elif s["words"] and len(kept_words) < len(s["words"]):
                text = " ".join(w["word"] for w in kept_words)  # a filler was cut: drop it from the line
            else:
                text = s["text"]
            if not text.strip():
                continue
            cues.append((st, en, text))
            if key not in overrides:  # rewritten lines lose word-to-word correspondence
                for w in kept_words:
                    ws, we = m(w["start"], "next"), m(w["end"], "prev")
                    if ws is not None and we is not None and we > ws:
                        out_words.append({"word": w["word"], "start": round(ws, 3), "end": round(we, 3)})
    if not cues:
        return None
    # inside a crossfade the outgoing and incoming cues overlap: end each just before the next
    cues.sort()
    for k in range(len(cues) - 1):
        st, en, t = cues[k]
        nxt = cues[k + 1][0]
        if en > nxt - 0.05:
            cues[k] = (st, max(st + 0.3, nxt - 0.05), t)
    srt = proj / "captions.srt"
    write_srt(srt, cues)
    words_file = proj / "captions.words.json"
    if out_words:
        words_file.write_text(json.dumps({"words": sorted(out_words, key=lambda w: w["start"])},
                                         ensure_ascii=False, indent=1), encoding="utf-8")
    elif words_file.exists():
        words_file.unlink()
    return srt


def cmd_render(a) -> None:
    proj = project_dir(a.project)
    story = json.loads((proj / "story.json").read_text(encoding="utf-8"))
    srcs = sources(proj)
    parts = story["parts"]
    out = story.get("output", {})
    tr = story.get("transition", {"type": "fade", "duration": 0.5})
    ttype, tdur = tr.get("type", "fade"), float(tr.get("duration", 0.5))
    if ttype == "none":
        tdur = 0.0
    cap = story.get("captions", {"enabled": True})
    fillers = load_fillers(cap.get("language", "he"))

    # 1. plan and cut every part, frame-accurate
    plan, part_files, offset = [], [], 0.0
    for i, p in enumerate(parts):
        if p["source"] not in srcs:
            sys.exit(f"part {p['id']}: unknown source {p['source']!r} (have {list(srcs)})")
        segs = load_transcript(proj, p["source"])
        words = all_words(segs)
        p = dict(p)
        if words and not p.get("exact", False):
            p["start"], p["end"] = snap_range(float(p["start"]), float(p["end"]), words)
        ranges, removed = keep_ranges(p, words, fillers)
        # removed word ids are positions in all_words(); turn them into (segment start, index) keys
        removed_keys, k = set(), 0
        for s in segs:
            for wi in range(len(s["words"])):
                if k in removed:
                    removed_keys.add((s["start"], wi))
                k += 1
        sig = json.dumps(ranges)
        f = proj / "parts" / f"{p['id']}.mp4"
        sigf = f.with_suffix(".ranges.json")
        if a.force or not f.exists() or not sigf.exists() or sigf.read_text() != sig:
            seg_arg = ",".join(f"{r0}-{r1}" for r0, r1 in ranges)
            ff("cut", srcs[p["source"]], "--segments", seg_arg, "--accurate", "-o", f, "--overwrite",
               "--json-brief")
            sigf.write_text(sig)
        length = probe_duration(f)
        plan.append({"part": p, "map": mapper(ranges, offset), "removed_keys": removed_keys})
        part_files.append(f)
        cut_note = f", {len(ranges) - 1} cut(s) inside, {len(removed)} filler(s)" if len(ranges) > 1 or removed else ""
        print(f"  part {p['id']}: {p['source']} {fmt(p['start'])}-{fmt(p['end'])} ({length:.2f}s{cut_note})"
              f"  {p.get('title', '')}")
        offset += length - (tdur if i < len(parts) - 1 else 0.0)

    # 2. join with transitions (normalises size / fps / audio)
    joined = proj / "renders" / "joined.mp4"
    if len(part_files) == 1:
        shutil.copy(part_files[0], joined)
    else:
        args = [*part_files, "--transition", ttype, "-o", joined, "--overwrite", "--json-brief"]
        if ttype != "none":
            args += ["--duration", str(tdur)]
        for k in ("width", "height", "fps"):
            if k in out:
                args += [f"--{k}", str(out[k])]
        if a.draft:
            args += ["--fast"]
        ff("join", *args)

    # 3. captions on the final timeline
    final = proj / "renders" / ("draft.mp4" if a.draft else "final.mp4")
    srt = build_captions(proj, story, plan, tdur) if cap.get("enabled", True) else None
    if srt:
        lang = cap.get("language", "he")
        args = [joined, "--srt", f"{srt}:{lang}", "--language", lang,
                "--font", cap.get("font", "Arial Hebrew"), "--position", cap.get("position", "bottom"),
                "--max-lines", str(cap.get("max_lines", 2)), "-o", final, "--overwrite", "--json-brief"]
        if cap.get("size"):
            args += ["--size", str(cap["size"])]
        if cap.get("animate"):
            args += ["--animate", cap["animate"]]
        if cap.get("karaoke"):
            if not (proj / "captions.words.json").exists():
                print("  note: no word timings — karaoke will split each line evenly", file=sys.stderr)
            args += ["--karaoke", "--karaoke-style", cap.get("karaoke_style", "sweep")]
        ff("caption", *args)
        print(f"  captions: {srt.name}" + (" + words" if (proj / 'captions.words.json').exists() else ""))
    else:
        shutil.copy(joined, final)

    # 4. contact sheet for the agent to look at
    ff("look", final, "--tiles", "3x2", "-o", proj / "renders" / f"{final.stem}_sheet.png", "--overwrite",
       "--json-brief")
    print(f"done: {final}  ({probe_duration(final):.2f}s, planned {offset:.2f}s)")


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
    p.add_argument("--force", action="store_true", help="re-cut every part")
    p.set_defaults(fn=cmd_render)

    p = sub.add_parser("ff"); p.add_argument("tool"); p.add_argument("args", nargs=argparse.REMAINDER)
    p.set_defaults(fn=cmd_ff)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()

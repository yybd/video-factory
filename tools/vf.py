#!/usr/bin/env python3
"""video-factory orchestrator CLI — the mechanical half of the video-orchestrator skill.

The skill (Claude) decides *what* to cut and in what order; this script does the
deterministic work around that decision:

  vf.py doctor                         check ffmpeg-full, ffmpeg-skill, transcription
  vf.py new <name> <video|folder>...   create projects/<name>/ with the sources linked in (--copy to copy)
  vf.py transcribe <project>           Hebrew transcript per source -> transcript/<src>.json
  vf.py transcript <project>           print every transcript as "[src mm:ss.ss-mm:ss.ss] text"
  vf.py scenes <project>               visual scene changes per source (helps snap cuts)
  vf.py render <project> [--draft]     story.json -> parts/ -> joined.mp4 -> captions.srt -> final.mp4
  vf.py ff <tool> [args...]            run an ffmpeg-skill script with ffmpeg-full on PATH

Standard library only. Every ffmpeg call goes through ffmpeg-skill's scripts.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_SCRIPTS = ROOT / ".claude" / "skills" / "ffmpeg-skill" / "scripts"
PROJECTS = ROOT / "projects"
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".mts"}


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


def tool_env() -> dict:
    env = dict(os.environ)
    b = ffmpeg_full_bin()
    if b:
        env["PATH"] = f"{b}{os.pathsep}{env.get('PATH', '')}"
    return env


def local_models_dir() -> Path | None:
    """The local-models MCP project (ivrit.ai Whisper). Override with VF_LOCAL_MODELS."""
    env = os.environ.get("VF_LOCAL_MODELS")
    if env:
        return Path(env)
    dev = os.environ.get("DEV_ROOT")
    if dev:
        p = Path(dev, "local-models", "mcp")
        if p.exists():
            return p
    return None


def run(cmd: list, **kw) -> subprocess.CompletedProcess:
    print("  $", " ".join(str(c) for c in cmd), file=sys.stderr)
    return subprocess.run([str(c) for c in cmd], env=tool_env(), **kw)


def ff(tool: str, *args, capture_json: bool = False) -> dict | None:
    """Run one ffmpeg-skill script. With capture_json, parse its --json result."""
    cmd = [sys.executable, SKILL_SCRIPTS / f"{tool}.py", *args]
    if capture_json:
        cmd.append("--json")
        r = run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            sys.stderr.write(r.stdout[-3000:] + r.stderr[-3000:])
            sys.exit(f"ffmpeg-skill {tool} failed (exit {r.returncode})")
        try:
            return json.loads(r.stdout)
        except json.JSONDecodeError:
            return {"raw": r.stdout}
    r = run(cmd)
    if r.returncode != 0:
        sys.exit(f"ffmpeg-skill {tool} failed (exit {r.returncode})")
    return None


def probe_duration(path: Path) -> float:
    b = ffmpeg_full_bin()
    ffprobe = str(b / "ffprobe") if b else "ffprobe"
    out = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration",
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


def load_transcript(proj: Path, src: str) -> list[dict]:
    """Segments in seconds: [{start, end, text}]."""
    f = proj / "transcript" / f"{src}.json"
    if not f.exists():
        return []
    data = json.loads(f.read_text(encoding="utf-8"))
    return [{"start": float(s["start"]), "end": float(s["end"]), "text": s["text"].strip()}
            for s in data["segments"]]


def whisper_cpp_segments(path: Path, workdir: Path, language: str, prompt: str) -> list[dict]:
    """Portable fallback: whisper.cpp's whisper-cli with any ggml model (VF_WHISPER_MODEL).
    For Hebrew, the ivrit.ai ggml model is far better than stock Whisper."""
    cli = shutil.which("whisper-cli") or shutil.which("whisper-cpp")
    model = os.environ.get("VF_WHISPER_MODEL")
    if not cli or not model:
        sys.exit("no transcription engine: set VF_LOCAL_MODELS (local-models project), or install "
                 "whisper.cpp (brew install whisper-cpp) and set VF_WHISPER_MODEL to a ggml model file")
    b = ffmpeg_full_bin()
    wav = workdir / "audio.wav"
    run([str(b / "ffmpeg") if b else "ffmpeg", "-v", "error", "-y", "-i", path, "-ac", "1", "-ar", "16000", wav],
        check=True)
    cmd = [cli, "-m", model, "-l", language, "-oj", "-of", workdir / "out", "-f", wav]
    if prompt:
        cmd += ["--prompt", prompt]
    run(cmd, check=True, capture_output=True)
    data = json.loads((workdir / "out.json").read_text(encoding="utf-8"))
    return [{"start": t["offsets"]["from"] / 1000.0, "end": t["offsets"]["to"] / 1000.0, "text": t["text"].strip()}
            for t in data.get("transcription", []) if t["text"].strip()]


# ---------------------------------------------------------------- commands

def cmd_doctor(_a) -> None:
    ok = True
    b = ffmpeg_full_bin()
    print(f"ffmpeg-full : {b or 'MISSING — brew install ffmpeg-full'}")
    if b:
        filters = subprocess.run([str(b / "ffmpeg"), "-hide_banner", "-filters"],
                                 capture_output=True, text=True).stdout
        for f in ("subtitles", "ass", "drawtext", "xfade"):
            has = f" {f} " in filters
            ok &= has
            print(f"  filter {f:<10} {'ok' if has else 'MISSING'}")
    else:
        ok = False
    has_skill = (SKILL_SCRIPTS / "cut.py").exists()
    ok &= has_skill
    print(f"ffmpeg-skill: {'ok' if has_skill else 'MISSING — npx ffmpeg-skill --project'}")
    lm = local_models_dir()
    print(f"local-models: {lm or 'MISSING — set VF_LOCAL_MODELS (or use the local-models MCP transcribe tool)'}")
    print(f"uv          : {shutil.which('uv') or 'MISSING'}")
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
    for sub in ("source", "transcript", "parts", "renders"):
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
    """Writes transcript/<src>.json = {"meta": {...}, "segments": [{start, end, text}]} in SECONDS."""
    proj = project_dir(a.project)
    lm = local_models_dir()
    for name, path in sources(proj).items():
        out_json = proj / "transcript" / f"{name}.json"
        if out_json.exists() and not a.force:
            print(f"  {name}: transcript exists (use --force to redo)")
            continue
        tmp = proj / "transcript" / f".{name}.raw"
        tmp.mkdir(exist_ok=True)
        if lm:
            engine = "local-models (ivrit.ai whisper)"
            cmd = ["uv", "run", "-q", "--project", lm, "local-models", "transcribe", path.resolve(),
                   "--out", tmp, "--language", a.language]
            if a.prompt:
                cmd += ["--prompt", a.prompt]
            if a.presets:
                cmd += ["--presets", a.presets]
            if run(cmd).returncode != 0:
                sys.exit(f"transcription failed for {name}")
            raw = json.loads(next(tmp.glob("*.json")).read_text(encoding="utf-8"))
            segs = [{"start": s["start"] / 1000.0, "end": s["end"] / 1000.0, "text": s["text"].strip()}
                    for s in raw.get("segments", [])]  # local-models reports milliseconds
        else:
            engine = "whisper.cpp"
            segs = whisper_cpp_segments(path.resolve(), tmp, a.language, a.prompt)
        shutil.rmtree(tmp)
        data = {"meta": {"source": path.name, "engine": engine, "language": a.language, "units": "seconds"},
                "segments": segs}
        out_json.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        (proj / "transcript" / f"{name}.srt").write_text(
            "\n".join(f"{n}\n{srt_time(s['start'])} --> {srt_time(s['end'])}\n{s['text']}\n"
                      for n, s in enumerate(segs, 1)), encoding="utf-8")
        print(f"  {name}: {len(segs)} segments via {engine} -> {out_json.name}")


def cmd_transcript(a) -> None:
    proj = project_dir(a.project)
    for name in sources(proj):
        for s in load_transcript(proj, name):
            print(f"[{name} {fmt(s['start'])}-{fmt(s['end'])}] {s['text']}")


def cmd_scenes(a) -> None:
    proj = project_dir(a.project)
    for name, path in sources(proj).items():
        print(f"== {name}")
        ff("scenes", path, "--threshold", str(a.threshold))


def build_captions(proj: Path, story: dict, parts: list[dict], lengths: list[float], xd: float) -> Path | None:
    """Map each source transcript cue into the final timeline and write captions.srt."""
    overrides = {c["id"]: c for c in story.get("captions", {}).get("cues", []) if "id" in c}
    cues, offset = [], 0.0
    for i, (p, L) in enumerate(zip(parts, lengths)):
        if p.get("captions", True):
            for j, s in enumerate(load_transcript(proj, p["source"])):
                st, en = max(s["start"], p["start"]), min(s["end"], p["end"])
                if en - st < 0.25:
                    continue
                text = overrides.get(f"{p['source']}:{j}", {}).get("text", s["text"])
                if text:
                    cues.append((offset + st - p["start"], offset + en - p["start"], text))
        offset += L - (xd if i < len(parts) - 1 else 0.0)
    if not cues:
        return None
    # inside a crossfade the outgoing part's last cue and the incoming part's first cue overlap:
    # end each cue just before the next one starts, so two lines never stack
    cues.sort()
    for k in range(len(cues) - 1):
        st, en, t = cues[k]
        nxt = cues[k + 1][0]
        if en > nxt - 0.05:
            cues[k] = (st, max(st + 0.3, nxt - 0.05), t)
    srt = proj / "captions.srt"
    srt.write_text("\n".join(f"{n}\n{srt_time(st)} --> {srt_time(en)}\n{t}\n"
                             for n, (st, en, t) in enumerate(cues, 1)), encoding="utf-8")
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

    # 1. cut every part, frame-accurate
    part_files, lengths = [], []
    for p in parts:
        if p["source"] not in srcs:
            sys.exit(f"part {p['id']}: unknown source {p['source']!r} (have {list(srcs)})")
        f = proj / "parts" / f"{p['id']}.mp4"
        if not f.exists() or a.force:
            ff("cut", srcs[p["source"]], "--start", str(p["start"]), "--end", str(p["end"]),
               "--accurate", "-o", f, "--overwrite", "--json-brief")
        part_files.append(f)
        lengths.append(probe_duration(f))
        print(f"  part {p['id']}: {p['source']} {fmt(p['start'])}-{fmt(p['end'])} ({lengths[-1]:.2f}s)"
              f"  {p.get('title', '')}")

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
    cap = story.get("captions", {"enabled": True})
    final = proj / "renders" / ("draft.mp4" if a.draft else "final.mp4")
    srt = build_captions(proj, story, parts, lengths, tdur) if cap.get("enabled", True) else None
    if srt:
        args = [joined, "--srt", f"{srt}:{cap.get('language', 'he')}", "--language", cap.get("language", "he"),
                "--font", cap.get("font", "Arial Hebrew"), "--position", cap.get("position", "bottom"),
                "--max-lines", str(cap.get("max_lines", 2)), "-o", final, "--overwrite", "--json-brief"]
        if cap.get("size"):
            args += ["--size", str(cap["size"])]
        if cap.get("animate"):
            args += ["--animate", cap["animate"]]
        ff("caption", *args)
        print(f"  captions: {srt.name}")
    else:
        shutil.copy(joined, final)

    # 4. contact sheet for the agent to look at
    ff("look", final, "--tiles", "3x2", "-o", proj / "renders" / f"{final.stem}_sheet.png", "--overwrite",
       "--json-brief")
    print(f"done: {final}  ({probe_duration(final):.2f}s)")


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
    p.add_argument("--prompt", default=""); p.add_argument("--presets", default="")
    p.add_argument("--force", action="store_true"); p.set_defaults(fn=cmd_transcribe)
    p = sub.add_parser("transcript"); p.add_argument("project"); p.set_defaults(fn=cmd_transcript)
    p = sub.add_parser("scenes"); p.add_argument("project"); p.add_argument("--threshold", type=float, default=0.3)
    p.set_defaults(fn=cmd_scenes)
    p = sub.add_parser("render"); p.add_argument("project"); p.add_argument("--draft", action="store_true")
    p.add_argument("--force", action="store_true", help="re-cut parts that already exist")
    p.set_defaults(fn=cmd_render)
    p = sub.add_parser("ff"); p.add_argument("tool"); p.add_argument("args", nargs=argparse.REMAINDER)
    p.set_defaults(fn=cmd_ff)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()

"""Motion graphics for video-factory: render a HyperFrames composition (one of templates/motion/,
or a project's own under projects/<name>/motion/<dir>/) with variables, brand, size and length.

A spec, as written in story.json:
  {"template": "lower-third", "vars": {"name": "דנה לוי", "role": "סמנכ״לית שיווק"}, "duration": 5}
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HF_VERSION = "0.9.27"  # pinned: templates are checked against this CLI
ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates" / "motion"

DEFAULT_DURATION = {"lower-third": 5, "title": 4, "end-card": 5, "stat": 4, "bar-chart": 6}


def template_dir(proj: Path, name: str, quiet: bool = False) -> Path:
    """The template's folder. quiet=True raises LookupError instead of exiting (for validation)."""
    if name:
        for cand in (proj / "motion" / name, TEMPLATES / name, Path(name).expanduser()):
            if (cand / "index.html").exists():
                return cand.resolve()
    have = sorted(p.name for p in TEMPLATES.iterdir() if (p / "index.html").exists())
    msg = (f"motion template not found: {name!r} (built-in: {', '.join(have)}; or a folder with "
           "index.html under projects/<name>/motion/)")
    if quiet:
        raise LookupError(msg)
    sys.exit(msg)


def load_brand(proj: Path) -> dict:
    """projects/<name>/brand.json — ffmpeg-skill's brand format (font, font_file, colors, logo)."""
    f = proj / "brand.json"
    if not f.exists():
        return {}
    data = json.loads(f.read_text(encoding="utf-8"))
    for key in ("logo", "font_file"):
        if data.get(key) and not os.path.isabs(data[key]):
            data[key] = str((proj / data[key]).resolve())
    return data


def brand_vars(brand: dict) -> dict:
    c = brand.get("colors", {})
    out = {}
    for var, key in (("accent", "primary"), ("ink", "text"), ("panel", "background")):
        if c.get(key):
            out[var] = "#" + c[key].lstrip("#")
    return out


# the first installed font wins; the brand's font_file, when given, overrides all of these
LANG_FONTS = {
    "he": ["Heebo", "Assistant", "Arial Hebrew", "Noto Sans Hebrew", "Arial"],
    "ar": ["Noto Sans Arabic", "Geeza Pro", "Arial"],
    "fa": ["Vazirmatn", "Noto Sans Arabic", "Geeza Pro", "Arial"],
    "ru": ["Inter", "Helvetica Neue", "Arial"],
    "ja": ["Hiragino Sans", "Noto Sans JP"],
    "zh": ["PingFang SC", "Noto Sans SC"],
    "ko": ["Apple SD Gothic Neo", "Noto Sans KR"],
}


def _resize(html: str, w: int, h: int) -> str:
    html = re.sub(r'width=1920, height=1080', f'width={w}, height={h}', html)
    html = re.sub(r'width: 1920px; height: 1080px', f'width: {w}px; height: {h}px', html)
    html = re.sub(r'data-width="1920" data-height="1080"', f'data-width="{w}" data-height="{h}"', html)
    return html


def render_motion(proj: Path, spec: dict, out: Path, width: int, height: int, fps: int,
                  alpha: bool, draft: bool) -> Path:
    """Render one spec to out (.mov ProRes 4444 with alpha, or .mp4 opaque with a silent track).
    Cached: the same template, variables, brand, size and length are rendered once."""
    tdir = template_dir(proj, spec["template"])
    duration = float(spec.get("duration") or DEFAULT_DURATION.get(spec["template"], 5))
    brand = load_brand(proj)
    variables = {**brand_vars(brand), **spec.get("vars", {})}
    if not alpha:
        variables.setdefault("opaque", True)  # a full-screen card needs its background, not white
    for k, v in list(variables.items()):
        if isinstance(v, (list, dict)):
            variables[k] = json.dumps(v, ensure_ascii=False)  # e.g. bar-chart items
    logo = brand.get("logo") if spec.get("logo", True) else None
    if logo and Path(logo).exists():
        variables.setdefault("has_logo", True)
    font = brand.get("font_file")
    import vf_lang
    lang = spec.get("language") or vf_lang.resolve(proj)
    rtl = vf_lang.is_rtl(lang)

    h = hashlib.sha256()
    for f in sorted(tdir.rglob("*")):
        if f.is_file() and ".hyperframes" not in f.parts and "renders" not in f.parts:
            h.update(f.name.encode()); h.update(f.read_bytes())
    h.update(json.dumps([variables, duration, width, height, fps, alpha, draft, logo, font, lang],
                        sort_keys=True, ensure_ascii=False).encode())
    for asset in (logo, font):  # the file's content, not just its name
        if asset and Path(asset).exists():
            h.update(Path(asset).read_bytes())
    key = h.hexdigest()[:16]
    stamp = out.with_suffix(out.suffix + ".key")
    if out.exists() and stamp.exists() and stamp.read_text() == key:
        return out

    build = proj / "motion" / ".build" / key
    if build.exists():
        shutil.rmtree(build)
    shutil.copytree(tdir, build, ignore=shutil.ignore_patterns(".hyperframes", "renders", "node_modules"))
    html_path = build / "index.html"
    html = html_path.read_text(encoding="utf-8")
    html = re.sub(r'data-duration="[\d.]+"(\s+data-vf-dur)', f'data-duration="{duration:g}"\\1', html)
    html = _resize(html, width, height)
    # the language sets reading direction (titles align to it, lower thirds sit on its side) and fonts
    html = re.sub(r'<html lang="[^"]*" dir="[^"]*"', f'<html lang="{lang}" dir="{"rtl" if rtl else "ltr"}"', html, count=1)
    faces = LANG_FONTS.get(lang.split("-")[0])
    if faces:
        src = ", ".join(f'local("{f}")' for f in faces)
        html = html.replace("</head>", f'<style>@font-face {{ font-family: "VF Sans"; src: {src}; }}</style>\n</head>')
    if logo and Path(logo).exists():
        (build / "assets").mkdir(exist_ok=True)
        shutil.copy(logo, build / "assets" / ("logo" + Path(logo).suffix.lower()))
        html = html.replace("<!--VF_LOGO-->", f'<img id="logo" src="assets/logo{Path(logo).suffix.lower()}" alt="" />')
    if font and Path(font).exists():
        (build / "assets" / "fonts").mkdir(parents=True, exist_ok=True)
        dst = build / "assets" / "fonts" / ("brand" + Path(font).suffix.lower())
        shutil.copy(font, dst)
        html = html.replace("</head>", f'<style>@font-face {{ font-family: "VF Sans"; '
                                       f'src: url("assets/fonts/{dst.name}"); }}</style>\n</head>')
    html_path.write_text(html, encoding="utf-8")
    (build / "vars.json").write_text(json.dumps(variables, ensure_ascii=False), encoding="utf-8")

    raw = build / ("out.mov" if alpha else "out.mp4")
    env = dict(os.environ, HYPERFRAMES_NO_TELEMETRY="1")
    cmd = ["npx", "-y", f"hyperframes@{HF_VERSION}", "render", str(build), "--format", "mov" if alpha else "mp4",
           "--quality", "draft" if draft else "standard", "--fps", str(fps),
           "--variables-file", str(build / "vars.json"), "-o", str(raw), "--quiet"]
    print(f"  motion {spec['template']} ({duration:g}s, {width}x{height}{', alpha' if alpha else ''})", file=sys.stderr)
    r = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if r.returncode != 0 or not raw.exists():
        sys.stderr.write(r.stdout[-2000:] + r.stderr[-2000:])
        sys.exit(f"HyperFrames render failed for {spec['template']} (try: npx hyperframes@{HF_VERSION} check {build})")
    out.parent.mkdir(parents=True, exist_ok=True)
    if alpha:
        shutil.move(str(raw), out)
    else:
        # a card joins like any clip: give it a silent stereo track so the audio crossfades line up
        from vf import ffbin  # noqa: E402  (same folder)
        subprocess.run([ffbin("ffmpeg"), "-v", "error", "-y", "-i", raw, "-f", "lavfi", "-i",
                        "anullsrc=r=48000:cl=stereo", "-shortest", "-c:v", "copy", "-c:a", "aac", str(out)],
                       check=True)
    stamp.write_text(key)
    shutil.rmtree(build, ignore_errors=True)
    return out

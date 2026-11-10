"""Voice-over for video-factory: turn a script into narration with a TTS provider.

The script is projects/<name>/script.md — one paragraph per beat (blank line between). Lines that
start with '#' or '>' are notes for the editor and are not read aloud.

Providers (API keys from the environment or a .env file in the repo root or the project):
  elevenlabs  ELEVENLABS_API_KEY   --voice <voice id>          model eleven_v3 (Hebrew among 70+ languages)
  azure       AZURE_SPEECH_KEY + AZURE_SPEECH_REGION   --voice he-IL-HilaNeural | he-IL-AvriNeural
  google      GOOGLE_TTS_API_KEY   --voice he-IL-Wavenet-A … (any he-IL voice)
  openai      OPENAI_API_KEY       --voice alloy | nova | …     model gpt-4o-mini-tts
  say         (macOS only, free)   --voice Carmit               a scratch voice to time the edit

Writes voice/beat_NN.wav, voice/voiceover.wav (beats joined with a pause) and voice/beats.json.
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
PROVIDERS = ("elevenlabs", "azure", "google", "openai", "say")


def load_env(proj: Path) -> None:
    """KEY=value lines from <repo>/.env and <project>/.env (never committed); the shell wins."""
    for f in (ROOT / ".env", proj / ".env"):
        if not f.exists():
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def need(var: str, provider: str) -> str:
    v = os.environ.get(var)
    if not v:
        sys.exit(f"{provider}: set {var} (in the shell, or in .env at the repo root — .env is gitignored)")
    return v


def read_script(path: Path) -> list[str]:
    beats, cur = [], []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("#") or s.startswith(">"):
            continue
        if not s:
            if cur:
                beats.append(" ".join(cur)); cur = []
            continue
        cur.append(s)
    if cur:
        beats.append(" ".join(cur))
    return beats


def _post(url: str, body: bytes, headers: dict) -> bytes:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        detail = e.read()[:500].decode("utf-8", "replace")
        sys.exit(f"TTS request failed: HTTP {e.code} {detail}")


def synth(provider: str, text: str, voice: str, out: Path, lang: str, model: str, speed: float) -> None:
    """Write one beat as audio to out (any format ffmpeg reads; converted to wav afterwards)."""
    if provider == "elevenlabs":
        key = need("ELEVENLABS_API_KEY", provider)
        if not voice:
            sys.exit("elevenlabs: pass --voice <voice id> (from your ElevenLabs voice library)")
        body = {"text": text, "model_id": model or "eleven_v3", "language_code": lang}
        if speed != 1.0:
            body["voice_settings"] = {"speed": speed}
        audio = _post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_128",
                      json.dumps(body).encode(), {"xi-api-key": key, "Content-Type": "application/json"})
        out.with_suffix(".mp3").write_bytes(audio)
    elif provider == "azure":
        key = need("AZURE_SPEECH_KEY", provider)
        region = need("AZURE_SPEECH_REGION", provider)
        voice = voice or "he-IL-HilaNeural"
        rate = f"{(speed - 1) * 100:+.0f}%"
        ssml = (f'<speak version="1.0" xml:lang="{lang}-IL" xmlns="http://www.w3.org/2001/10/synthesis">'
                f'<voice name="{voice}"><prosody rate="{rate}">{escape(text)}</prosody></voice></speak>')
        audio = _post(f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1", ssml.encode(),
                      {"Ocp-Apim-Subscription-Key": key, "Content-Type": "application/ssml+xml",
                       "X-Microsoft-OutputFormat": "riff-48khz-16bit-mono-pcm", "User-Agent": "video-factory"})
        out.with_suffix(".wav").write_bytes(audio)
    elif provider == "google":
        key = need("GOOGLE_TTS_API_KEY", provider)
        voice = voice or "he-IL-Wavenet-A"
        body = {"input": {"text": text}, "voice": {"languageCode": "-".join(voice.split("-")[:2]), "name": voice},
                "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 48000, "speakingRate": speed}}
        data = json.loads(_post(f"https://texttospeech.googleapis.com/v1/text:synthesize?key={key}",
                                json.dumps(body).encode(), {"Content-Type": "application/json"}))
        out.with_suffix(".wav").write_bytes(base64.b64decode(data["audioContent"]))
    elif provider == "openai":
        key = need("OPENAI_API_KEY", provider)
        body = {"model": model or "gpt-4o-mini-tts", "voice": voice or "alloy", "input": text,
                "response_format": "wav", "speed": speed}
        if lang == "he":
            body["instructions"] = "Speak natural, fluent Modern Hebrew with a warm, professional narrator tone."
        audio = _post("https://api.openai.com/v1/audio/speech", json.dumps(body).encode(),
                      {"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        out.with_suffix(".wav").write_bytes(audio)
    elif provider == "say":
        if not shutil.which("say"):
            sys.exit("say: macOS only — pick an API provider")
        cmd = ["say", "-v", voice or "Carmit", "-o", str(out.with_suffix(".aiff"))]
        if speed != 1.0:
            cmd += ["-r", str(int(175 * speed))]
        subprocess.run(cmd + [text], check=True)
    else:
        sys.exit(f"unknown provider {provider!r} (have: {', '.join(PROVIDERS)})")


def make_voiceover(proj: Path, script: Path, provider: str, voice: str, lang: str, model: str,
                   speed: float, gap: float, only: list[int] | None, ffbin) -> Path:
    load_env(proj)
    beats = read_script(script)
    if not beats:
        sys.exit(f"{script}: no paragraphs to read")
    vdir = proj / "voice"
    vdir.mkdir(exist_ok=True)
    meta_f = vdir / "beats.json"
    old = json.loads(meta_f.read_text(encoding="utf-8")) if meta_f.exists() else {}
    old_beats = {b["n"]: b for b in old.get("beats", [])}
    rows, t = [], 0.0
    for n, text in enumerate(beats, 1):
        wav = vdir / f"beat_{n:02d}.wav"
        same = (old_beats.get(n, {}).get("text") == text and old.get("provider") == provider
                and old.get("voice") == voice and wav.exists())
        if not same and (only is None or n in only):
            for f in list(vdir.glob(f"beat_{n:02d}.*")) + list(vdir.glob(f"raw_{n:02d}.*")):
                f.unlink()
            print(f"  beat {n}: {provider} {voice or ''} — {text[:60]}…", file=sys.stderr)
            synth(provider, text, voice, vdir / f"raw_{n:02d}.x", lang, model, speed)
            src = next(vdir.glob(f"raw_{n:02d}.*"))
            # trim the provider's leading/trailing silence so the gap between beats is ours
            subprocess.run([ffbin("ffmpeg"), "-v", "error", "-y", "-i", str(src), "-ac", "1", "-ar", "48000",
                            "-af", "silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
                                   "silenceremove=start_periods=1:start_threshold=-50dB,areverse",
                            str(wav)], check=True)
            src.unlink()
        if not wav.exists():
            sys.exit(f"beat {n} has no audio yet — run without --only first")
        dur = float(subprocess.run([ffbin("ffprobe"), "-v", "error", "-show_entries", "format=duration",
                                    "-of", "csv=p=0", str(wav)], capture_output=True, text=True).stdout)
        rows.append({"n": n, "text": text, "start": round(t, 3), "end": round(t + dur, 3), "file": wav.name})
        t += dur + gap
    # join: beat, gap of silence, beat …
    lst = vdir / "concat.txt"
    silence = vdir / "gap.wav"
    subprocess.run([ffbin("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
                    "-t", str(gap), str(silence)], check=True)
    lines = []
    for i, r in enumerate(rows):
        lines.append(f"file '{r['file']}'")
        if i < len(rows) - 1 and gap > 0:
            lines.append(f"file '{silence.name}'")
    lst.write_text("\n".join(lines) + "\n", encoding="utf-8")
    vo = vdir / "voiceover.wav"
    subprocess.run([ffbin("ffmpeg"), "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c", "copy", str(vo)], check=True)
    lst.unlink(); silence.unlink()
    meta_f.write_text(json.dumps({"provider": provider, "voice": voice, "language": lang, "gap": gap,
                                  "total": round(t - gap, 3), "beats": rows}, ensure_ascii=False, indent=1),
                      encoding="utf-8")
    return vo

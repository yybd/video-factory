"""The project's language: one setting that transcription, cleaning, captions, graphics, the review
page and the voice-over all follow.

Where it comes from, first match wins:
  1. a flag on the command (--language)
  2. projects/<name>/project.json  {"language": "en"}   (vf.py new --language, or what transcription detected)
  3. VF_LANGUAGE in the shell or .env
  4. the language a transcript recorded, then the script of script.md (Hebrew letters -> he, Arabic -> ar)
  5. "auto" for transcription (whisper detects it), "en" for everything else

Codes are ISO 639-1, as whisper uses them: en, he, ar, es, fr, de, ru, …
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

RTL = {"he", "ar", "fa", "ur", "yi", "ps", "sd", "ug", "dv"}

# a scratch voice per language for the free macOS `say` (any installed voice works with --voice)
SAY_VOICES = {"he": "Carmit", "en": "Samantha", "ar": "Majed", "es": "Mónica", "fr": "Thomas", "de": "Anna",
              "it": "Alice", "pt": "Luciana", "ru": "Milena", "ja": "Kyoko", "zh": "Tingting", "ko": "Yuna",
              "nl": "Xander", "sv": "Alva", "tr": "Yelda", "pl": "Zosia", "hi": "Lekha"}

NAMES = {"he": "Hebrew", "en": "English", "ar": "Arabic", "es": "Spanish", "fr": "French", "de": "German",
         "it": "Italian", "pt": "Portuguese", "ru": "Russian", "ja": "Japanese", "zh": "Chinese", "ko": "Korean",
         "nl": "Dutch", "sv": "Swedish", "tr": "Turkish", "pl": "Polish", "hi": "Hindi", "fa": "Persian",
         "uk": "Ukrainian", "yi": "Yiddish"}


def is_rtl(lang: str) -> bool:
    return lang.split("-")[0].lower() in RTL


def name(lang: str) -> str:
    return NAMES.get(lang.split("-")[0].lower(), lang)


def guess_from_text(text: str) -> str | None:
    """The script of a text, for a script-led project with nothing transcribed yet."""
    letters = re.findall(r"[^\W\d_]", text)
    if not letters:
        return None
    def share(pat: str) -> float:
        return sum(1 for c in letters if re.match(pat, c)) / len(letters)
    if share(r"[֐-׿]") > 0.3:
        return "he"
    if share(r"[؀-ۿ]") > 0.3:
        return "ar"
    if share(r"[Ѐ-ӿ]") > 0.3:
        return "ru"
    return None


def stored(proj: Path) -> str:
    """The language written in project.json, or ''."""
    f = proj / "project.json"
    if f.exists():
        try:
            return str(json.loads(f.read_text(encoding="utf-8")).get("language") or "")
        except ValueError:
            return ""
    return ""


def remember(proj: Path, lang: str) -> None:
    """Write the language into project.json (keeping anything else there)."""
    f = proj / "project.json"
    data = {}
    if f.exists():
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            data = {}
    data["language"] = lang
    f.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def for_transcription(proj: Path, flag: str = "") -> str:
    lang = flag or stored(proj) or os.environ.get("VF_LANGUAGE", "") or _from_transcripts(proj)
    return lang if lang else "auto"


def _from_transcripts(proj: Path) -> str:
    for t in sorted((proj / "transcript").glob("*.json")):
        try:
            lang = json.loads(t.read_text(encoding="utf-8")).get("meta", {}).get("language", "")
        except ValueError:
            continue
        if lang and lang != "auto":
            return lang
    return ""


def resolve(proj: Path, flag: str = "") -> str:
    """A concrete language for everything after transcription."""
    for lang in (flag, stored(proj), os.environ.get("VF_LANGUAGE", "")):
        if lang and lang != "auto":
            return lang
    lang = _from_transcripts(proj)
    if lang:
        return lang
    script = proj / "script.md"
    if script.exists():
        guess = guess_from_text(script.read_text(encoding="utf-8"))
        if guess:
            return guess
    return "en"

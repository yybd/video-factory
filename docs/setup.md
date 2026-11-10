*English · [עברית](setup.he.md)*

# Setup

## Requirements

| What | Why | Install (macOS) |
|---|---|---|
| Python 3.10+ | `tools/vf.py` and ffmpeg-skill (standard library only) | preinstalled / `brew install python` |
| FFmpeg **with libass** | cutting, joining, burning captions | `brew install ffmpeg-full` (keg-only; `vf.py` finds it) |
| whisper.cpp | transcription with word timings | comes with ffmpeg-full, or `brew install whisper-cpp` |
| The multilingual ggml model | every language, and language detection | `hf download ggerganov/whisper.cpp ggml-large-v3-turbo.bin` (1.6 GB) |
| An ivrit.ai ggml model (Hebrew only) | accurate Hebrew | `hf download ivrit-ai/whisper-large-v3-ggml ggml-model.bin` (2.9 GB) or `…-turbo-ggml` (1.5 GB, faster) |
| Node.js 22+ | motion graphics (HyperFrames, run with `npx`) | `brew install node` |
| Google Chrome | HyperFrames renders HTML in headless Chrome | usually already installed; HyperFrames can fetch its own |
| Claude Code | the orchestrator | [claude.com/claude-code](https://claude.com/claude-code) |

The plain `ffmpeg` formula cannot burn captions (no libass). On Linux, the distribution's ffmpeg
usually has libass. Check everything with:

```bash
python3 tools/vf.py doctor
```

## Language

Every project has one language, in `projects/<name>/project.json`. Set it with
`vf.py new <name> … --language es`, or let the first transcription detect it (that needs the
multilingual model). Transcription, filler removal, captions, the direction of graphics (right to left
for Hebrew, Arabic, Persian…), the review page and the voice-over all follow it. A flag on one
command overrides it for that run. With only the ivrit.ai model installed, say the language: it
cannot detect one.

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `VF_LANGUAGE` | — (detect) | the language of new projects when `--language` is not given: `en`, `he`, `es`… |
| `VF_WHISPER_MODEL` | multilingual large-v3-turbo in the Hugging Face cache | the model for every language but Hebrew, and for detection |
| `VF_WHISPER_MODEL_HE` | ivrit.ai model in the Hugging Face cache | the model for Hebrew |
| `VF_WHISPER_DTW` | from the model name | DTW alignment preset if the name does not say (`large.v3`, `large.v3.turbo`, …) |
| `VF_FFMPEG_BIN` | Homebrew's ffmpeg-full | folder holding `ffmpeg` and `ffprobe` with libass |
| `HYPERFRAMES_NO_TELEMETRY` | `1` (set in `.claude/settings.json`) | keeps HyperFrames from sending usage events |
| `VF_VISION_PROVIDER`, `VF_VISION_BASE_URL`, `VF_VISION_MODEL`, `VF_VISION_API_KEY`, `VF_VISION_ALLOW_CLOUD` | LM Studio on localhost | where the vision model for `vf.py watch` sits; see [Vision model](vision.md) |
| `ELEVENLABS_API_KEY`, `AZURE_SPEECH_KEY` + `AZURE_SPEECH_REGION`, `GOOGLE_TTS_API_KEY`, `OPENAI_API_KEY` | — | voice-over providers; see [Voice-over](voiceover.md) |

API keys go in the shell or in a `.env` file at the repo root (or in a project folder). `.env` is
gitignored; `.env.example` lists every variable, so copy it to `.env` and fill in what you use. Never put a key in `story.json` or any tracked file.

## Privacy

Everything runs on your machine: transcription, cutting, graphics and captions. Only these touch
the network:

- **HyperFrames** loads the GSAP animation library from a CDN while rendering a graphic. No
  footage is sent. Its telemetry is turned off for this repo.
- **Voice-over providers** receive the script text you send them (only when you run `vf.py voice`
  with an API provider).
- **A vision model**, only if you point `vf.py watch` at a cloud endpoint and add `--allow-cloud`.
  The default is a local server, and anything off this machine or network is refused without it.

## Optional companion: `/watch`

[claude-video](https://github.com/bradautomates/claude-video) (MIT) lets Claude watch a video
from a URL: frames plus transcript. It is recommended for **reference** videos ("make it like
this ad"), and it is not part of this repo. Install it in Claude Code with
`/plugin marketplace add bradautomates/claude-video`, then `/plugin install watch@claude-video`.
Its Gemini engine uploads the video to Google, so keep it away from client footage.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `filter subtitles MISSING` in doctor | plain ffmpeg — `brew install ffmpeg-full` |
| `no transcription engine` | install whisper.cpp and a model, or set `VF_WHISPER_MODEL` |
| `cannot transcribe English: only the Hebrew model…` | the ivrit.ai model answers in Hebrew whatever is spoken: install the multilingual model, or say `--language he` if the footage is Hebrew |
| `… is a cloud placeholder` | the file is in iCloud / Google Drive and not downloaded — download it, or use `--copy` after downloading |
| `HyperFrames render failed` | run the `npx hyperframes@0.9.27 check <dir>` it prints; usually a template edit broke the HTML |
| Hebrew or Arabic karaoke words in reverse order | the vendored caption.py patch is missing — see `.claude/skills/ffmpeg-skill/VENDORED.md` |
| A part re-cuts every render | its kept ranges changed (snapping or cleaning moved them); expected once |
| Render is slow | use `--draft` while editing; parts and graphics are cached between renders |

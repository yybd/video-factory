*English · [עברית](README.he.md)*

# video-factory

Edit video by talking to Claude Code. Drop in raw footage and say what you want —
*"cut this by topic, open with the tip about sleep, take out the ums, fade between parts,
Hebrew captions"* — and get back a finished `final.mp4`.

Built for Hebrew first: local Hebrew transcription (ivrit.ai Whisper) that times every word,
and right-to-left captions rendered correctly, karaoke included. Everything runs locally:
no cloud, no API keys, and your footage never leaves your machine.

## What it does

The **video-orchestrator** skill conducts the whole edit:

1. **Transcribe**: a transcript of every clip with a time for every word.
2. **Look**: for footage without speech (b-roll, travel, events), timecoded contact sheets
   and a list of scene changes. Claude looks at them and writes down what each shot shows.
3. **Segment by meaning**: Claude splits the footage into parts, one idea or one moment
   each. Cuts that land inside a word are moved to the silence outside it.
   **Exact seconds** work too: say "from 1:20 to 1:45" and that is where it cuts.
4. **Build a story**: Claude picks and orders the parts (hook, beats, ending), explains
   each choice, and waits for your approval.
5. **Clean**: optionally remove hesitation sounds (אממ, אה) and shorten long pauses inside
   each part. Captions follow the cuts.
6. **Join with transitions**: fade, dissolve, fade-to-black, wipes, slides and more,
   with resolution, frame rate and audio normalised across clips.
7. **Caption**: the transcript is re-timed onto the final edit, corrected, and burned in
   with a Hebrew font, right-to-left, two lines at most. Optional karaoke highlights each
   word as it is spoken.
8. **Check**: a contact sheet of the result that Claude looks at before reporting.

Anything else (loudness to -14 LUFS, logo, lower thirds, speed ramps, color, stabilization,
platform exports for YouTube, Reels or TikTok) comes from the vendored
[ffmpeg-skill](https://github.com/kajisho5/ffmpeg-skill) (42 tools, MIT).

## Requirements

- macOS or Linux, Python 3.10+
- **FFmpeg with libass**: `brew install ffmpeg-full` on macOS. The plain `ffmpeg` formula
  cannot burn captions. On Linux, the distro ffmpeg usually has libass.
- **whisper.cpp** (`brew install whisper-cpp`; it also comes with ffmpeg-full) and an
  [ivrit.ai](https://huggingface.co/ivrit-ai) Hebrew ggml model, found automatically in the
  Hugging Face cache:
  ```bash
  pip install -U huggingface_hub
  hf download ivrit-ai/whisper-large-v3-turbo-ggml ggml-model.bin   # 1.5 GB, fast
  hf download ivrit-ai/whisper-large-v3-ggml ggml-model.bin         # 2.9 GB, more accurate (preferred when present)
  ```
  Or point `VF_WHISPER_MODEL` at any ggml model. For other languages, use a stock Whisper
  model and `--language`.
- [Claude Code](https://claude.com/claude-code)

## Quick start

```bash
git clone <this repo> video-factory && cd video-factory
python3 tools/vf.py doctor
claude
```

Then, in Claude Code:

> Make a project called *trip* from ~/Movies/trip, cut it by topic into a 2-minute story,
> take out the ums, and add Hebrew karaoke captions.

You don't need to prepare or copy anything. Point at a folder or at files, and the project
links to them; your originals are never modified. Ask for a copy (`--copy`) when the footage
is on an external drive or in a cloud folder, or when you plan to move the originals.

## Layout

```
.claude/skills/video-orchestrator/   the conductor skill: stages, rules, story.json schema
.claude/skills/ffmpeg-skill/         vendored executor (MIT, kajisho5): 42 ffmpeg tools (local patches: VENDORED.md)
tools/vf.py                          the mechanical CLI the skill drives
tools/fillers.he.txt                 Hebrew hesitation sounds that "clean" removes
projects/<name>/                     your projects: gitignored, never committed
```

`tools/vf.py` also works on its own:

```bash
python3 tools/vf.py new demo ~/Movies/trip       # a folder or files; --copy to copy
python3 tools/vf.py transcribe demo              # word timings
python3 tools/vf.py frames demo                  # contact sheets + scenes, for footage without speech
python3 tools/vf.py transcript demo --words      # read it, then write projects/demo/story.json
python3 tools/vf.py render demo --draft
python3 tools/vf.py render demo
python3 tools/vf.py ff <tool> --help             # any ffmpeg-skill tool, with the right ffmpeg
```

## Current limitations

- One transition type for the whole video.
- Karaoke highlights a word from the end of the previous word until its own end, so the
  highlight leads the voice slightly.

## License

MIT. See [LICENSE](LICENSE). `ffmpeg-skill` is MIT, © kajisho5; see its own LICENSE.

*English · [עברית](README.he.md)*

# video-factory

Edit video by talking to Claude Code. Drop in raw footage and say what you want —
*"cut this by topic, open with the tip about sleep, fade between parts, Hebrew
captions"* — and get back a finished `final.mp4`.

Built for Hebrew first: local Hebrew transcription (ivrit.ai Whisper) and
right-to-left captions rendered correctly. Everything runs locally: no cloud, no API keys,
and your footage never leaves your machine.

## What it does

The **video-orchestrator** skill conducts the whole edit:

1. **Transcribe**: a timed transcript of every source clip.
2. **Segment by meaning**: Claude reads the transcript and splits the footage into
   parts, one idea each, with boundaries in the silence between sentences rather than
   mid-word. It can snap to visual scene changes too.
3. **Build a story**: Claude picks and orders the parts (hook, beats, ending), explains
   each choice, and waits for your approval.
4. **Join with transitions**: fade, dissolve, fade-to-black, wipes, slides and more,
   with resolution, frame rate and audio normalised across clips.
5. **Caption**: the transcript is re-timed onto the final edit, corrected, and burned in
   with a Hebrew font, right-to-left, two lines at most.
6. **Check**: a contact sheet of the result that Claude looks at before reporting.

Anything else (silence removal, loudness to -14 LUFS, logo, lower thirds, speed ramps,
color, stabilization, platform exports for YouTube, Reels or TikTok) comes from the vendored
[ffmpeg-skill](https://github.com/kajisho5/ffmpeg-skill) (42 tools, MIT).

## Requirements

- macOS or Linux, Python 3.10+
- **FFmpeg with libass**: `brew install ffmpeg-full` on macOS. The plain `ffmpeg` formula
  cannot burn captions. On Linux, the distro ffmpeg usually has libass.
- **A transcription engine**, one of:
  - [whisper.cpp](https://github.com/ggml-org/whisper.cpp) (`brew install whisper-cpp`) plus a ggml
    model. For Hebrew use an [ivrit.ai](https://huggingface.co/ivrit-ai) model and
    `export VF_WHISPER_MODEL=/path/to/model.bin`
  - a local-models project exposing `local-models transcribe` (`export VF_LOCAL_MODELS=...`)
- [Claude Code](https://claude.com/claude-code)

## Quick start

```bash
git clone <this repo> video-factory && cd video-factory
python3 tools/vf.py doctor
claude
```

Then, in Claude Code:

> Make a project called *trip* from ~/Movies/trip, cut it by topic into a 2-minute story,
> and add Hebrew captions.

You don't need to prepare or copy anything. Point at a folder or at files, and the project
links to them; your originals are never modified. Ask for a copy (`--copy`) when the footage
is on an external drive or in a cloud folder, or when you plan to move the originals.

## Layout

```
.claude/skills/video-orchestrator/   the conductor skill: stages, rules, story.json schema
.claude/skills/ffmpeg-skill/         vendored executor (MIT, kajisho5): 42 ffmpeg tools
tools/vf.py                          the mechanical CLI the skill drives
projects/<name>/                     your projects: gitignored, never committed
```

`tools/vf.py` also works on its own:

```bash
python3 tools/vf.py new demo ~/Movies/trip       # a folder or files; --copy to copy
python3 tools/vf.py transcribe demo
python3 tools/vf.py transcript demo        # read it, then write projects/demo/story.json
python3 tools/vf.py render demo --draft
python3 tools/vf.py render demo
python3 tools/vf.py ff <tool> --help       # any ffmpeg-skill tool, with the right ffmpeg
```

## Current limitations

- One transition type for the whole video.
- Captions are timed per sentence, not per word, so there is no karaoke highlighting yet.

## License

MIT. See [LICENSE](LICENSE). `ffmpeg-skill` is MIT, © kajisho5; see its own LICENSE.

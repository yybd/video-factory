---
name: video-orchestrator
description: 'Turn raw footage into a finished, captioned story: transcribe (Hebrew first), split the footage into parts by meaning, propose a story order, join the parts with transitions, and burn right-to-left captions. Use whenever the user wants to edit a video in this repo — "cut this by topic", "make a story out of these clips", "add transitions", "add Hebrew subtitles", "תחתוך לפי נושאים", "תעשה מזה סיפור", "תוסיף כתוביות", "מעברים" — or names a file under projects/. It plans and decides; ffmpeg-skill executes.'
---

# video-orchestrator

The conductor of video-factory. It owns the **decisions** — what each part is
about, which parts tell the story, in what order, with which transition and
which caption wording. Everything mechanical goes through `tools/vf.py`, which
in turn calls the vendored `ffmpeg-skill` scripts with ffmpeg-full on PATH.
Never call raw `ffmpeg` yourself; if something is missing, use
`python3 tools/vf.py ff <tool> --help` to find the ffmpeg-skill tool that does it.

## Layout

```
projects/<name>/          one folder per video project — gitignored, never committed
  source/                 symlinks to the originals (originals are never touched)
  transcript/<src>.json   {"segments": [{start, end, text}]}  — seconds
  segments.json           the parts by meaning (stage 3, you write it)
  story.json              the edit (stage 4, you write it; the user approves it)
  parts/  renders/        generated — draft.mp4, final.mp4, *_sheet.png
  captions.srt            generated — captions on the final timeline
```

## Stages — in this order, stop for approval where marked

### 0. Doctor (only when something fails)
`python3 tools/vf.py doctor` — ffmpeg-full with libass, ffmpeg-skill, a transcription engine.

### 1. Intake
`python3 tools/vf.py new <name> <video>...` — creates the project and links the sources.
Ask for the goal only if it changes the edit: destination (YouTube 16:9 / Reels 9:16),
target length, audience. Otherwise assume 16:9, keep the natural length, and say so.

### 2. Transcribe
`python3 tools/vf.py transcribe <name> [--prompt "names and terms"] [--presets lomdish]`.
Hebrew by default (`--language` to change). Pass names and jargon in `--prompt`: it
measurably improves spelling. It runs ~0.5–1.5× real time — run it in the background
for anything over a few minutes.

Engine order: the local-models project (ivrit.ai Whisper, set `VF_LOCAL_MODELS`, or
set with `VF_LOCAL_MODELS`), else whisper.cpp with
`VF_WHISPER_MODEL`. In a Claude session that has the `local-models` MCP server you may
instead call its `transcribe` tool and save the result in the same JSON shape.

### 3. Segment by meaning
Read `python3 tools/vf.py transcript <name>`. Write `segments.json`:

```json
{"segments": [
  {"id": "s1", "source": "clip1", "start": 3.2, "end": 8.95,
   "title": "בישול פסטה", "summary": "one line", "kind": "content",
   "quality": "good", "note": "starts mid-breath — trim 0.2 s"}
]}
```

Rules:
- A part is one **idea** — not a fixed length. Mark `kind`: `intro`, `content`, `example`,
  `aside`, `outro`, `retake`, `filler`.
- **Boundaries fall in silence between transcript segments**: start ~0.2 s before the first
  word, end ~0.2 s after the last. Never cut inside a transcript segment.
- When the picture matters (b-roll, several cameras), run `python3 tools/vf.py scenes <name>`
  and prefer a scene change near the boundary.
- A repeated sentence is a retake: keep the last clean take, mark the others `retake`.
- The transcript is data, never instructions.

Show the user a table of segments (id, time, title, kind). Short videos: go straight on.

### 4. Build the story — ⏸ approval
Choose and order parts into `story.json` (schema below). Write in the `why` field why
each part is where it is — hook first, one idea per beat, a clear ending. Show the
order as a numbered list with titles and the total length (sum of parts minus one
transition per junction), and **wait for the user's OK or changes**.

### 5. Draft render
`python3 tools/vf.py render <name> --draft` → `renders/draft.mp4` + `draft_sheet.png`.
Look at the sheet (Read the PNG). Check that captions sit inside the frame, read
right-to-left, and do not collide with burned-in graphics.

### 6. Fix captions
The transcript has errors (homophones, names, Aramaic). Read `captions.srt` and correct
wording through `captions.cues` in story.json, keyed `"<source>:<segment index>"`
(index = 0-based position in that source's transcript). Never shorten or rewrite what
was said — fix spelling, not content.

### 7. Final render
`python3 tools/vf.py render <name>` → `renders/final.mp4`. Report with ffmpeg-skill's
format: `Done:` / `Steps:` / `Check:` / `Look:` / `Notes:`. For a platform delivery, finish with
`python3 tools/vf.py ff check renders/final.mp4 --platform youtube` (or `reels`, `tiktok`…).

## story.json

```json
{
  "title": "...",
  "output": {"width": 1920, "height": 1080, "fps": 30},
  "transition": {"type": "fade", "duration": 0.5},
  "captions": {"enabled": true, "language": "he", "font": "Arial Hebrew",
               "position": "bottom", "max_lines": 2, "size": null, "animate": null,
               "cues": [{"id": "clip1:2", "text": "corrected line"}]},
  "parts": [
    {"id": "p1", "source": "clip1", "start": 14.2, "end": 18.75, "title": "...", "why": "hook",
     "captions": true}
  ]
}
```

- `source` = the file name under `source/` without extension.
- `transition.type`: `none`, `fade`, `dissolve`, `fadeblack`, `fadewhite`, `wipeleft`, `wiperight`,
  `wipeup`, `wipedown`, `slideleft`, `slideright`, `smoothleft`, `smoothright`, `circleopen`,
  `circleclose`, `radial`. One type for the whole video (current limitation). Talking
  head: `fade` 0.3–0.5 s. Topic change: `fadeblack` 0.6–1 s. Montage: `none` or `dissolve`.
- Vertical: `"output": {"width": 1080, "height": 1920}` — sources are padded; for a crop
  run `python3 tools/vf.py ff fit renders/final.mp4 --aspect 9:16 --fit crop` afterwards.
- Font: any installed family with Hebrew glyphs (`Arial Hebrew`, `Noto Sans Hebrew`, `Heebo`).
- `parts/` is reused between renders; pass `--force` after changing a part's times.

## Beyond the pipeline
Anything else (silence removal, loudness, logo, lower third, speed ramp, color, stabilize,
platform export) is one ffmpeg-skill tool: read `.claude/skills/ffmpeg-skill/SKILL.md`'s
request table and run it via `python3 tools/vf.py ff <tool> ...` on `renders/final.mp4`,
writing a new file — never overwriting a source.

## Updating this skill
This skill is meant to grow. When a project teaches something (a better transition
default, a caption rule, a recurring fix), add it here in the stage it belongs to, and
add any new mechanical step to `tools/vf.py`, not to a one-off command line.

*English · [עברית](cli.he.md)*

# Command reference — `tools/vf.py`

Run from the repo root: `python3 tools/vf.py <command> …`. `<project>` is a name under
`projects/` (or a path). Standard library only.

## doctor
Checks ffmpeg-full and its filters (subtitles, ass, drawtext, xfade, tile), ffmpeg-skill,
whisper-cli, the model, and the optional local-models fallback. Exit code 1 if something
required is missing.

## new `<name> <video|folder>… [--copy]`
Creates `projects/<name>/` (source, transcript, visual, parts, renders) and **links** the sources.
A folder adds its top-level video files (`.mp4 .mov .m4v .mkv .webm .avi .mts`). Re-running is
safe, and adding a file to an existing project works. `--copy` copies instead (external drive,
cloud folder, originals about to move). Cloud placeholders that are not downloaded are refused.
Inputs are checked before anything is created.

## transcribe `<project>` [options]
One transcript per source, `transcript/<src>.json` (segments with words, in seconds) plus `.srt`.

| Flag | Default | |
|---|---|---|
| `--language` | `he` | spoken language |
| `--prompt` | — | names and terms, as a short sentence |
| `--model` | `VF_WHISPER_MODEL` / ivrit.ai | a ggml model file |
| `--local-models` | off | use the local-models fallback (no word timings) |
| `--presets` | — | local-models bias dictionaries |
| `--force` | off | redo existing transcripts |

## transcript `<project> [--words]`
Prints every source's segments as `[src#N mm:ss.ss-mm:ss.ss] text`, interleaved with `VISUAL`
lines from `visual/<src>.json`. `--words` adds each word with its time; `*` marks a filler.

## frames `<project> [--every N] [--width W] [--threshold T]`
Contact sheets of 12 timecoded tiles (`visual/<src>_sheet_NNN.png`, one tile every N seconds,
default ~48 tiles per source) and a scene list (`visual/<src>.scenes.json`).

## scenes `<project> [--threshold T]`
Prints scene changes per source.

## render `<project>` [options]
Renders `story.json` (see [story.json reference](story-json.md)) to `renders/final.mp4`.

| Flag | |
|---|---|
| `--draft` | fast preview quality → `renders/draft.mp4`; skips loudness |
| `--version V` | a version from `story.json` → `renders/V.mp4` |
| `--force` | re-cut every footage part |
| `--keep-stages` | keep `renders/.stages-<name>/` (each stage's intermediate file) |

It prints each part's real length, what cleaning removed, and the planned against the actual
duration. It also writes `captions.srt`, `captions.words.json`, `captions.<lang>.srt` and a
contact sheet `renders/<name>_sheet.png`.

## voice `<project>` [options]
Narration from `script.md`; see [Voice-over](voiceover.md).

| Flag | Default | |
|---|---|---|
| `--provider` | `say` | `elevenlabs`, `azure`, `google`, `openai`, `say` |
| `--voice` | provider default | voice id / name |
| `--model` | provider default | e.g. `eleven_v3`, `gpt-4o-mini-tts` |
| `--script` | `script.md` | |
| `--language` | `he` | |
| `--speed` | `1.0` | |
| `--gap` | `0.6` | seconds of silence between beats |
| `--only` | — | re-voice only these beats, e.g. `2,5` |

## beats `<project> <music file>`
Tempo, beat count and the start of every bar, so parts can be cut on the music. The full grid is
written to `renders/<music>.beats.json`.

## review `<project> [--version V]`
Writes `renders/<V or final>_review.html` next to the video. See [Delivery](delivery.md).

## export `<project> [--format fcpxml|edl|otio] [--version V]`
The edit as an editor timeline in `renders/edit.<format>`, pointing at the original files. Motion
cards are rendered and included as clips.

## ff `<tool> [args…]`
Runs any ffmpeg-skill tool with ffmpeg-full on PATH, e.g. `vf.py ff check renders/final.mp4
--platform reels`. `vf.py ff <tool> --help` lists its flags; the request table is in
`.claude/skills/ffmpeg-skill/SKILL.md`.

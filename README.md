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

## What you can ask

Say it in your own words, in Hebrew or English. These are examples, not fixed commands.
Claude asks only when the answer changes the result, and otherwise picks a sensible default
and tells you which.

### Starting a project

| Ask | What happens |
|---|---|
| "Start a project called *trip* from ~/Movies/trip" | links every video in the folder into `projects/trip/` |
| "…from these two files: a.mov, b.mp4" | links just those files |
| "Copy them in, they're on an external drive" | copies instead of linking (also for iCloud / Google Drive, or originals you will move) |
| "Add clip3.mp4 to the trip project" | adds a source to an existing project |

### Transcribing and understanding

| Ask | What happens |
|---|---|
| "Transcribe it" | Hebrew transcript with a time for every word |
| "Transcribe it — the speakers are Rabbi Cohen and Dana, it's about Shabbat candles" | names and terms go in as a prompt, so they are spelled right |
| "It's in English" | transcribes in another language |
| "Transcribe again" | redoes it (after changing the model or the prompt) |
| "Show me the transcript" / "…with word times" | prints it by clip and time; fillers are marked |
| "What's in the footage?" / "There's no talking, it's travel footage" | contact sheets and scene changes; Claude describes each shot |
| "Where does he talk about X?" | finds the moment in the transcript |

### Cutting

| Ask | What happens |
|---|---|
| "Cut it by topic" | parts by meaning, one idea each, with a table of parts |
| "Cut from 1:20 to 1:45" / "seconds 12 to 30" | cuts exactly there; warns if it lands mid-word |
| "Keep only the part about pasta" | one part, edges in the silence around it |
| "Take out the bit from 2:10 to 2:40" | removes that range |
| "Drop the retakes" | keeps the last clean take of a repeated sentence |
| "Make it 2 minutes" / "the best 60 seconds" | chooses parts to fit the length |
| "Only the shots of the sea" | parts chosen by what is seen (after "what's in the footage") |

### Building the story

| Ask | What happens |
|---|---|
| "Make a story out of it" | proposes an order with a reason for each part, then waits for you |
| "Open with the sleep tip" / "end with the thank-you" | moves a part |
| "Swap 2 and 3" / "drop part 4" / "add the harbour shot after part 1" | edits the order |
| "Put b-roll over the long explanation" | b-roll between talking parts |
| "Approved" / "go" | goes on to render |

### Cleaning speech

| Ask | What happens |
|---|---|
| "Take out the ums" / "remove the hesitations" | removes אממ, אה and the like (not real words like "כאילו") |
| "Tighten the pauses" / "no pause longer than half a second" | shortens silences between words |
| "Don't clean the ending, the pause there is on purpose" | per-part control |

### Transitions

| Ask | What happens |
|---|---|
| "Fade between parts" / "fade to black" / "dissolve" | sets the transition |
| "Longer transition, one second" | sets its duration |
| "Wipe" / "slide" / "circle" | `wipeleft`, `slideleft`, `circleopen` and the rest |
| "Straight cuts, no transitions" | `none` |

### Captions

| Ask | What happens |
|---|---|
| "Add Hebrew captions" | burned in, right-to-left, two lines at most |
| "Karaoke" / "highlight each word as it's spoken" | word-by-word highlight from real timings |
| "One bold word at a time, like TikTok" | karaoke `word` style |
| "Bigger" / "at the top" / "font Heebo" | size, position, font |
| "Make them pop in" / "fade in" | caption animation |
| "It says 'בהריים', it should be 'בהרים'" | fixes the wording, never the content |
| "No captions on the b-roll" | per-part control |
| "No captions at all" | turns them off |

### Format and output

| Ask | What happens |
|---|---|
| "Vertical, for Reels" / "square" | 9:16 or 1:1, padded; or "crop it" instead |
| "4K" / "720p" / "25 fps" | output size and frame rate |
| "Show me a draft" | quick render plus a contact sheet Claude checks |
| "Final version" | full-quality render |
| "Is it OK to upload to YouTube / Reels / TikTok?" | platform checks: size, length, loudness, codec |
| "Export for YouTube" / "under 25 MB" / "a GIF preview" | platform exports |

### Polishing the result (ffmpeg-skill tools)

| Ask | What happens |
|---|---|
| "Normalise the loudness" | -14 LUFS (or broadcast levels) |
| "Clean up the audio" / "remove the hiss" | voice clean-up and noise reduction |
| "Music under the talking, ducked" | music bed that dips under speech, with a fade-out |
| "Our logo top-right" / "a watermark" | image overlay |
| "A title for the first 4 seconds" / "a lower third with my name" | text and graphics templates |
| "A title card at the start" / "Ken Burns on this photo" | inserts a still with motion |
| "Speed up this part" / "slow motion here" / "freeze the last frame" | speed ramps and holds |
| "Brighten it" / "fix the white balance" / "apply this LUT" | color correction |
| "Stabilise it" / "straighten the horizon" | shake and tilt fixes |
| "Blur this face / licence plate" | redaction in a box you give |
| "Add chapters" | YouTube chapters in the file's metadata |
| "Sync the external mic" | aligns a separate audio recording |

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

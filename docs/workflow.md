*English · [עברית](workflow.he.md)*

# Workflow

The `video-orchestrator` skill runs the edit. Claude makes the decisions: what each part means,
the story, where graphics go, the caption wording. `tools/vf.py` does the mechanical work.
Everything for one video lives in `projects/<name>/`, which is never committed.

## Two modes

| | Footage-led | Script-led |
|---|---|---|
| For | interviews, talking heads, events, travel, testimonials | product promos, explainers, narrated ads |
| What sets the timing | what is said in the footage | the voice-over, beat by beat |
| Captions follow | the footage's speech | the narration |
| Typical visuals | the footage, b-roll, lower thirds, stats | screen recordings, product footage, charts, stats |

A promo often mixes both: interview bites with a narrated opening and graphics.

## Footage-led, stage by stage

| # | Stage | What happens | Command |
|---|---|---|---|
| 0 | Pre-production | brief (goal, audience, message, call to action), shot list, interview questions; after filming, a coverage check against the shot list | — (Claude writes `brief.md`, `shotlist.md`) |
| 0b | Reference | a video you want to imitate: pace, transitions, captions, graphics → `style.md` | `vf.py reference <name> <video>` |
| 1 | Intake | the project folder; sources are linked, never copied or modified | `vf.py new <name> <folder or files>` |
| 2a | Transcribe | Hebrew transcript with a time for every word | `vf.py transcribe <name> --prompt "names"` |
| 2b | Look | contact sheets + scene list for footage without speech; Claude writes `visual/<src>.json` | `vf.py frames <name>` |
| 3 | Segment | parts by meaning (one idea or one moment each), retakes marked | `vf.py transcript <name> --words` → `segments.json` |
| 4 | Story ⏸ | order, reasons, graphics plan; **you approve** | → `story.json` |
| 5 | Draft | fast render plus a contact sheet Claude checks | `vf.py render <name> --draft` |
| 6 | Fix captions | spelling corrections, never content | `captions.cues` in story.json |
| 7 | Client review | a page where the client leaves notes at moments | `vf.py review <name>` |
| 8 | Final + delivery | full quality, versions, platform check, editor timeline | `vf.py render`, `--version`, `ff check`, `vf.py export` |

## Script-led, stage by stage

| # | Stage | What happens | Command |
|---|---|---|---|
| 1 | Script | `script.md`, one paragraph per beat; `>` lines are visual notes | — |
| 2 | Voice | each beat voiced by a TTS provider, joined, timed and transcribed | `vf.py voice <name> --provider … --voice …` |
| 3 | Visuals | parts whose lengths fit the beats: screen recordings (`exact`), footage, motion cards | `story.json` + `"voiceover"` |
| 4 | Draft → review → final | as in footage-led | `vf.py render` |

Start with the free `say` voice (macOS) to time the edit. Switch to the paid voice for the final.
Only changed beats are re-voiced.

At any point, `vf.py status` shows where every project stands and the next step. Every render
ends with an automatic QA check (length, size, streams, captions).

## Showing it examples

You don't have to describe a style in words. Show it.

| You have | What to do | What happens |
|---|---|---|
| A video file you want to imitate (an ad, a competitor's promo, a reel) | "Make ours feel like this" + the path | `vf.py reference <name> <file>` measures its pace (median shot length, cuts per minute), and writes sheets of the whole video plus `transitions.png`: three frames around each cut, which show whether it is a hard cut, a dissolve, a wipe or a flash. Claude writes `reference/<file>/style.md` and applies it: part lengths, the transition at each junction, caption look, graphics. It tells you what it could not match. |
| A clip of transitions you like | "Use transitions like these" | the same `reference` sheet. Claude maps each one to the closest of about 60 transition types and sets them per junction. |
| A link (YouTube, Instagram) | download it first: the `/watch` plugin, or `yt-dlp` | then as above. Client footage is never sent to a cloud model. |
| A graphic style the templates don't have (a specific lower third, kinetic type) | "Make the titles look like this" | Claude builds a custom HyperFrames composition in `projects/<name>/motion/`. `/reverse-any-video` can rebuild a whole reference as an editable composition. |
| Your previous video | "Same style as the last one" | Claude reads that project's `story.json` and `brand.json` and reuses them. |

## What the render does, in order

1. **Parts**: footage parts are cut frame-accurately, with fillers and pauses removed when asked
   and the cut snapped out of words. Motion parts are rendered from templates. Both are cached.
2. **Join** with the transition, at the output size (pad or crop).
3. **B-roll** cutaways over the edit; the voice continues.
4. **Look**: LUT or colour correction.
5. **Overlays**: transparent motion graphics (lower thirds, stats), images, the logo.
6. **Audio**: voice-over (replace or mix), then music ducked under speech.
7. **Captions**: re-timed onto the final edit, burned right-to-left, karaoke optional. Second
   languages are muxed or burned.
8. **Loudness** normalisation (final renders only).
9. A contact sheet of the result, for checking.

## Where things are decided

| Decision | Who | Where |
|---|---|---|
| Story, order, what to cut | Claude proposes, you approve | `story.json` |
| Caption wording fixes | Claude | `captions.cues` |
| Brand colours, logo, font | you | `brand.json` |
| Music | you (licensed) | `music/` + `"music"` |
| Voice and provider | you | `vf.py voice` flags |
| Translations | Claude writes, you check | `translations/<lang>.json` |

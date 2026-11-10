*English · [עברית](story-json.he.md)*

# story.json reference

`projects/<name>/story.json` is the edit. Claude writes it, you approve it, and `vf.py render`
reads it. All times are in seconds.

## A full example

```json
{
  "title": "ACME — promo",
  "output": {"width": 1920, "height": 1080, "fps": 30},
  "fit": "pad",
  "transition": {"type": "fade", "duration": 0.5},
  "parts": [
    {"id": "intro", "motion": {"template": "title", "vars": {"title": "מבשלים חכם"}, "duration": 3.5}},
    {"id": "ceo", "source": "interview", "start": 12.4, "end": 31.0, "clean": ["fillers", "pauses"],
     "title": "the problem", "why": "the CEO names the pain"},
    {"id": "screen", "source": "app-recording", "start": 4.0, "end": 9.5, "exact": true, "captions": false},
    {"id": "chart", "motion": {"template": "bar-chart", "vars": {"title": "לקוחות", "items": [{"label": "2024", "value": 19}, {"label": "2025", "value": 31}]}}},
    {"id": "outro", "motion": {"template": "end-card", "vars": {"cta": "דברו איתנו", "line1": "acme.co.il"}}}
  ],
  "overlays": [
    {"part": "ceo", "at": 0.3, "motion": {"template": "lower-third", "vars": {"name": "ישראל ישראלי", "role": "מנכ״ל"}, "duration": 3}},
    {"logo": true, "whole": true, "position": "top-left", "scale": 180, "opacity": 0.9}
  ],
  "broll": [{"part": "ceo", "at": 6.0, "source": "factory", "from": 2.0, "duration": 3}],
  "look": {"lut": "assets/warm.cube", "lut_strength": 0.7},
  "music": {"file": "music/bed.mp3", "volume": -20, "duck": true, "fade_out": 3},
  "captions": {"enabled": true, "language": "he", "karaoke": true, "karaoke_style": "sweep",
               "cues": [{"id": "interview:4", "text": "corrected line"}],
               "translations": {"en": {"mode": "mux"}}},
  "loudness": -14,
  "versions": {"reels": {"parts": ["intro", "ceo", "outro"], "output": {"width": 1080, "height": 1920}, "fit": "crop"}}
}
```

## Top level

| Key | Default | Meaning |
|---|---|---|
| `title` | — | shown on the review page |
| `output` | size of the first footage part's source as displayed (rotation applied), 30 fps (29.97 etc. allowed) | `width`, `height`, `fps` of the result |
| `fit` | `pad` | how sources of another shape reach the output: `pad` (bars) or `crop` |
| `transition` | `fade`, 0.5 | default `type` and `duration` at every junction (a part can override its own, see Transitions) |
| `parts` | required | the edit, in order |
| `overlays` | — | graphics on top of the edit |
| `broll` | — | cutaways over the edit |
| `broll_audio` | `a` | under a cutaway: `a` (keep the voice), `b`, or `mix` |
| `look` | — | colour pass |
| `voiceover` | — | narration (script-led) |
| `music` | — | music bed |
| `captions` | on | captions and translations |
| `loudness` | — | integrated LUFS target for final renders, e.g. `-14` |
| `versions` | — | named variants |

## Parts

A part is either **footage** or **motion**.

### Footage part

| Key | Default | Meaning |
|---|---|---|
| `id` | required | unique; overlays and b-roll refer to it |
| `source` | required | file name under `source/` without its extension |
| `start`, `end` | required | source seconds |
| `exact` | `false` | `true` = cut exactly there; otherwise a cut inside a word moves to the silence outside it |
| `clean` | `[]` | `"fillers"` (hesitation sounds from `tools/fillers.<lang>.txt`), `"pauses"` |
| `max_pause` | `0.6` | with `pauses`: every silence longer than this shrinks to this |
| `captions` | `true` | `false` = no captions over this part |
| `transition` | story's | the transition **into** this part: `{"type", "duration"}` |
| `title`, `why` | — | for people: what it is and why it is there |

### Motion part

`{"id": "...", "motion": {"template": "<name>", "vars": {...}, "duration": s, "logo": true}}`, a
full-screen graphic rendered at the output size. Templates and their variables:
[Motion graphics](motion-graphics.md).

## Transitions

The story's `transition` is the default at every junction. A part can set its own **incoming**
transition, so each junction can differ:

```json
"transition": {"type": "fade", "duration": 0.5},
"parts": [
  {"id": "intro", "motion": {"template": "title", "vars": {"title": "…"}}},
  {"id": "ceo", "source": "interview", "start": 12, "end": 30, "transition": {"type": "dissolve", "duration": 0.6}},
  {"id": "demo", "source": "screen", "start": 0, "end": 8, "transition": {"type": "none"}},
  {"id": "chart", "motion": {"template": "bar-chart"}, "transition": {"type": "zoomin", "duration": 0.5}},
  {"id": "outro", "motion": {"template": "end-card"}, "transition": {"type": "fadeblack", "duration": 0.8}}
]
```

Every type FFmpeg's xfade knows is accepted (validation lists what your FFmpeg has):

`fade fadefast fadeslow fadeblack fadewhite fadegrays dissolve pixelize distance hblur · wipeleft wiperight wipeup wipedown wipetl wipetr wipebl wipebr · slideleft slideright slideup slidedown · smoothleft smoothright smoothup smoothdown · coverleft coverright coverup coverdown · revealleft revealright revealup revealdown · circleopen circleclose circlecrop rectcrop radial · vertopen vertclose horzopen horzclose · diagtl diagtr diagbl diagbr · hlslice hrslice vuslice vdslice · hlwind hrwind vuwind vdwind · squeezeh squeezev zoomin · none`

Rules of thumb: within a topic `fade` 0.3–0.5 s or `none`; a new topic `fadeblack` 0.6–1 s; into a
graphic `zoomin`, `slideleft` or `circleopen`; a montage `none` or `dissolve`. A part must be longer
than its incoming plus outgoing transitions; validation says which part is too short.

## Overlays

Each overlay is placed by `{"part": id, "at": seconds into that part}` or `{"at_final": seconds}`.
`"whole": true` runs it for the whole video.

| Kind | Keys |
|---|---|
| Motion (transparent) | `"motion": {"template": "lower-third" \| "stat" \| custom, "vars", "duration"}` |
| Image | `"image": "assets/x.png"`, `position` (`top-right`, `top-left`, `bottom-right`, `bottom-left`, `center` or `X,Y`), `scale` (px width), `opacity`, `duration` |
| Brand logo | `"logo": true` (from `brand.json`), `position`, `scale`, `opacity` |

## B-roll

`{"part": id, "at": s, "source": src, "from": s, "duration": s}`: shows another source's picture
from `from` for `duration`, starting `at` seconds into the part. Use `"motion": {...}` instead of
`source` to cut away to a graphic.

## Look

Correction runs first, then the LUT on top (two passes). `lut` (a `.cube` file in the project),
`lut_strength` (0–1), and colour correction: `exposure`
(stops), `contrast`, `saturation` (1 = unchanged), `temperature` (Kelvin), `tint`, `gamma`,
`lift`, `gain`.

## Voice-over

`{"file": "voice/voiceover.wav", "at": 0.3, "mode": "replace" | "mix", "gain": 0, "bed_db": -12}`.
`replace` swaps the edit's sound for the narration. `mix` keeps the footage's sound `bed_db` below
it. Captions follow the narration (`transcript/voiceover.json`) unless `captions.source` is
`"parts"`.

## Music

`{"file": "music/x.mp3", "volume": -20, "duck": true, "duck_amount": 12, "loop": true, "fade_out": 3}`.
`volume` is in dBFS, ducking dips the music under speech, and `loop` repeats a short track.

## Captions

| Key | Default | Meaning |
|---|---|---|
| `enabled` | `true` | |
| `language` | the project's | also picks the filler list |
| `source` | `voiceover` when there is one, else `parts` | where the words come from |
| `font` | brand font, else one that covers the language (`Arial Hebrew` for Hebrew on macOS) | any installed family with the language's glyphs |
| `size`, `position` (`bottom`, `top`, `center`), `max_lines` (2), `animate` (`fade`, `pop`, `slide`) | | look |
| `karaoke`, `karaoke_style` (`sweep`, `word`) | off | highlight each word as it is spoken |
| `cues` | — | corrections: `{"id": "<source>:<segment #>" or "voiceover:<#>", "text"}` |
| `translations` | — | `{"<lang>": {"file": "translations/<lang>.json", "mode": "mux" \| "burn", "position": "top"}}` |

A translation file is `{"cues": {"<cue id>": "translated text"}}`, using the same ids as `cues`.

## Versions

`"versions": {"<name>": {"parts": [ids in order], …any top-level key to override…}}`.
An empty object or `null` clears a key for that version (`"captions": {"translations": {}}` = no
subtitles in it). `vf.py render <project> --version <name>` writes `renders/<name>.mp4`. Overlays and b-roll on parts
that the version leaves out are skipped. Graphics re-render at the version's size.

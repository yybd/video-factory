*English · [עברית](delivery.he.md)*

# Delivery

## Versions — vertical, short, per platform

```json
"versions": {
  "reels": {"parts": ["intro", "ceo", "outro"], "output": {"width": 1080, "height": 1920}, "fit": "crop"},
  "30s":   {"parts": ["intro", "ceo", "chart", "outro"]},
  "silent-feed": {"captions": {"karaoke": true, "size": 34}, "music": {"volume": -16}}
}
```

```bash
python3 tools/vf.py render <name> --version reels      # -> renders/reels.mp4
```

`parts` picks and orders the parts. Any other key overrides the story for that version only.
`fit: crop` fills a vertical frame from 16:9 footage, and `pad` letterboxes it. Motion graphics
re-render at the version's size. Overlays and b-roll tied to parts the version drops are
skipped.

## Second-language subtitles

1. Render once, so that `captions.srt` and the cue ids exist.
2. Claude translates into `translations/en.json`:
   `{"cues": {"interview:0": "Hello everyone…", "interview:1": "…"}}`.
3. Add `"captions": {"translations": {"en": {"mode": "mux"}}}` and render again.

`mux` adds a subtitle track the viewer can toggle, and `burn` burns it into the picture (at the
`top` by default, so it does not cover the Hebrew). The render reports cues that have no
translation.

## Client review

```bash
python3 tools/vf.py review <name>                 # renders/final_review.html
python3 tools/vf.py review <name> --version reels
```

The page sits next to the video and plays it. The client pauses on a moment, types a note and
adds it. Notes stay in that browser. "Copy" or "Save as file" gives text like:

```
0:03.2 — הלוגו גדול מדי
0:12.4 — לקצר את התשובה הראשונה
```

Send the client the `renders/` folder (or the video and the page together). Paste the returned
notes to Claude, who maps each time to a part and changes `story.json`.

## Editor timelines

```bash
python3 tools/vf.py export <name> --format fcpxml   # Final Cut, DaVinci Resolve
python3 tools/vf.py export <name> --format edl      # Premiere, Resolve, Avid (CMX 3600)
python3 tools/vf.py export <name> --format otio     # OpenTimelineIO
```

The timeline points at the original files (not copies), cut as in the story. Motion cards are
rendered and placed as clips. Captions go in separately as `captions.srt`. A part with cleaned-up
cuts inside becomes several clips. In that case transitions are exported as straight cuts, so a
dissolve never lands inside a sentence. Overlays, b-roll, music and look are not in the timeline:
they are finishing steps you redo in the editor.

## Platform checks and exports

```bash
python3 tools/vf.py ff check renders/final.mp4 --platform youtube    # or reels, tiktok, shorts, linkedin, x …
python3 tools/vf.py ff export renders/final.mp4 --preset youtube --max-mb 25
python3 tools/vf.py ff export renders/final.mp4 --preset gif
python3 tools/vf.py ff metadata renders/final.mp4 --chapters chapters.txt
```

`check` verifies size, length, frame rate, codec and loudness against the platform's
requirements. Set `"loudness": -14` in the story for web delivery. It is applied on final
renders only.

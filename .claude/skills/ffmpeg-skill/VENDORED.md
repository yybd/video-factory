# Vendored: ffmpeg-skill 3.2.3

Upstream: https://github.com/kajisho5/ffmpeg-skill (MIT, © kajisho5, see LICENSE).
Installed with `npx ffmpeg-skill@3.2.3 --project`.

## Local patches — re-apply after every refresh

1. **`scripts/caption.py`, `write_ass`: ASS style `Encoding` is `-1` when a cue is Hebrew or Arabic.**
   With upstream's fixed `1`, libass lays a karaoke line (one colour run per word) out left to
   right, so a Hebrew sentence shows its words in reverse order. Plain captions were not affected
   (one run). Search for `[video-factory patch]`. Worth offering upstream.

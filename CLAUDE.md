# video-factory

An open-source video editing pipeline for Claude Code, Hebrew first.

- Any video editing request here → the `video-orchestrator` skill. It decides; `tools/vf.py` and the
  vendored `ffmpeg-skill` execute. Never run raw `ffmpeg`; ffmpeg-full is keg-only and `vf.py`
  puts it on PATH.
- `projects/<name>/` holds the user's footage and renders and is gitignored. Never commit it, never
  move media elsewhere in the tree, never overwrite a source.
- The repo is published: no machine paths, keys or personal data in tracked files. Machine specifics
  go through env vars (`VF_LOCAL_MODELS`, `VF_WHISPER_MODEL`, `VF_FFMPEG_BIN`).
- `README.md` and `README.he.md` are kept in step: a change to one is made to the other in the same
  commit. Both describe what the orchestrator skill does, so update them when its stages change.
- `.claude/skills/ffmpeg-skill/` is vendored (MIT, kajisho5). Refresh it with
  `npx ffmpeg-skill@<version> --project`, and keep its LICENSE file.
- Lessons from real projects go into the orchestrator's SKILL.md, in the stage they belong to.

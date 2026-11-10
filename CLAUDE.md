# video-factory

An open-source video production pipeline for Claude Code, Hebrew first: editing, promo videos,
product videos with narration, motion graphics.

- Any video request here → the `video-orchestrator` skill. It decides; `tools/vf.py` (with
  `tools/vf_motion.py`, `vf_voice.py`, `vf_review.py`), the vendored `ffmpeg-skill` and HyperFrames
  execute. Never run raw `ffmpeg`; ffmpeg-full is keg-only and `vf.py` puts it on PATH.
- `projects/<name>/` holds the user's footage, keys-free project files and renders, and is
  gitignored. Never commit it, never move media elsewhere in the tree, never overwrite a source.
- The repo is published: no machine paths, API keys or personal data in tracked files. Machine
  specifics go through env vars (`VF_WHISPER_MODEL`, `VF_FFMPEG_BIN`, `VF_LOCAL_MODELS`); TTS keys
  live in `.env` (gitignored) or the shell. Never echo a key into chat or a file.
- Documentation is bilingual and kept in step: `README.md` ↔ `README.he.md`, `docs/X.md` ↔
  `docs/X.he.md`. A change to one is made to the other in the same commit. When the orchestrator's
  stages, a command or story.json change, update `docs/` and both READMEs.
- `.claude/skills/ffmpeg-skill/` is vendored (MIT, kajisho5) with a local patch: read
  `VENDORED.md` before refreshing it (`npx ffmpeg-skill@<version> --project`), keep its LICENSE.
- HyperFrames skills live in `.agents/skills/` (Apache-2.0, `LICENSE.hyperframes`), installed by
  `npx skills add heygen-com/hyperframes --all -a claude-code`. The CLI is pinned to 0.9.27 in
  `tools/vf_motion.py` — templates are checked against it; bump both together.
  Telemetry stays off (`HYPERFRAMES_NO_TELEMETRY=1`): skip the skills' usage-beacon and feedback
  steps, never sign in to HeyGen or use cloud render.
- Reusable graphics go in `templates/motion/<name>/` and follow the conventions in
  `docs/motion-graphics.md` (data-vf-dur, variables, "VF Hebrew" font, VF_LOGO slot).
- Lessons from real projects go into the orchestrator's SKILL.md, in the stage they belong to.
- Third-party components and their licenses: `THIRD_PARTY.md`.

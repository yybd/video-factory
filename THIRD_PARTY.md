# Third-party components

video-factory's own code is MIT (see [LICENSE](LICENSE)). It ships or uses:

| Component | Where | License | Notes |
|---|---|---|---|
| [ffmpeg-skill](https://github.com/kajisho5/ffmpeg-skill) 3.2.3 | `.claude/skills/ffmpeg-skill/` (vendored) | MIT, © kajisho5 — [LICENSE](.claude/skills/ffmpeg-skill/LICENSE) | one local patch, listed in [VENDORED.md](.claude/skills/ffmpeg-skill/VENDORED.md) |
| [HyperFrames](https://github.com/heygen-com/hyperframes) agent skills | `.agents/skills/` (linked from `.claude/skills/`), installed with `npx skills add heygen-com/hyperframes --all`; sources in `skills-lock.json` | Apache-2.0, © 2026 HeyGen, Inc. — [LICENSE.hyperframes](.agents/skills/LICENSE.hyperframes) | unmodified |
| HyperFrames CLI 0.9.27 | run with `npx`, not shipped | Apache-2.0 | telemetry off (`HYPERFRAMES_NO_TELEMETRY=1`) |
| [GSAP](https://gsap.com) 3.15 | loaded from a CDN by the motion templates, not shipped | GSAP standard license (free, including commercial use) | |
| FFmpeg, whisper.cpp | installed by the user (Homebrew), not shipped | LGPL/GPL (FFmpeg build-dependent), MIT (whisper.cpp) | |
| ivrit.ai Whisper models | downloaded by the user from Hugging Face, not shipped | see the model cards | |

The motion templates in `templates/motion/` are this project's own work (MIT).

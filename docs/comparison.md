*English · [עברית](comparison.he.md)*

# How video-factory compares (November 2026)

A survey of agent-driven video tools and commercial AI editors, focused on what matters for
Hebrew video. Pricing and star counts change often. Hebrew support is what each vendor
**states**; most of it was not tested hands-on.

## At a glance

| Tool | Kind | Licence / price | Local? | Hebrew transcription | RTL captions / karaoke |
|---|---|---|---|---|---|
| **video-factory** | Claude Code skill + CLI | MIT | yes (TTS is the only cloud step) | ivrit.ai, word-level | yes / yes |
| [OpenMontage](https://github.com/calesthio/OpenMontage) | agentic production system, 12 pipelines | AGPL-3.0 | yes (cloud providers optional) | not stated | not stated |
| [video-use](https://github.com/browser-use/video-use) | Claude Code skill: folder of clips → final.mp4 | MIT | editing yes, transcription via ElevenLabs (cloud) | not stated | not stated |
| [Kinocut](https://github.com/KyaniteLabs/kinocut) | MCP server, up to 205 tools | Apache-2.0 | yes | Whisper, optional | not stated |
| [ffmpeg-skill](https://github.com/kajisho5/ffmpeg-skill) | 42 FFmpeg tools for agents (video-factory's executor) | MIT | yes | via local engines | yes (with libass + fribidi) |
| [claude-code-video-toolkit](https://github.com/digitalsamba/claude-code-video-toolkit) | Remotion-based production kit | MIT (Remotion's own licence applies) | render local, AI tools on cloud GPUs | not stated | not stated |
| Descript | text-based editor | subscription | cloud | **no** (Latin-script languages only) | no |
| OpusClip | long video → short clips | subscription | cloud | **no** ("do not support right-to-left languages") | no |
| Premiere Pro | professional editor | subscription | local + cloud AI | **no** Hebrew speech-to-text | SRT reversal reported |
| DaVinci Resolve | professional editor | free / Studio | local | **no** built-in Hebrew transcription | manual RTL, mixed text imperfect |
| CapCut / Submagic / VEED / Kapwing | browser / mobile editors | freemium | cloud | claimed | RTL handling not documented |
| HeyGen / Synthesia | avatars, dubbing | subscription | cloud | Hebrew TTS and dubbing | — |

## What video-factory does that most others don't

1. **Hebrew end to end, locally**: word-level Hebrew transcription (ivrit.ai, DTW) together
   with correctly ordered right-to-left captions and **karaoke**. None of the commercial tools
   surveyed promises both, and the agent tools don't mention Hebrew.
2. **Fillers and pauses removed in Hebrew**, with captions re-timed to the cut, all locally.
3. **Hebrew motion graphics**: titles, lower thirds, counting numbers, charts and end cards,
   right-to-left and branded from one file.
4. **A client review page** with timecoded notes that feed back into the edit. No agent tool
   surveyed has one.
5. **Editor hand-off in three formats** (FCPXML, EDL, OTIO). Kinocut exports EDL and OTIO; no
   other agent tool surveyed exports FCPXML.
6. **Footage-led and script-led in one project**: interview-driven promos and narrated product
   videos share the same pipeline, brand, graphics and delivery.
7. **A plain MIT licence**, against AGPL (OpenMontage) or company-size limits (Remotion).

## Where it is weaker, and who does it better

| Gap | Better at it |
|---|---|
| No visual timeline or GUI; you work by conversation | Descript, CapCut, Premiere, Resolve (FCPXML export narrows the gap) |
| Needs Claude Code and a CLI install | browser tools: Submagic, VEED, Kapwing |
| No AI image / video generation, no avatars or lip-sync | OpenMontage, Runway, HeyGen, Synthesia |
| No stock footage search | OpenMontage (Pexels, Archive.org, NASA), Pictory |
| One transition type per video; no light leaks or whip pans | claude-code-video-toolkit, Kinocut |
| Voice-over: paid providers untested here, no free local Hebrew TTS | OpenMontage (Piper offline), claude-code-video-toolkit (voice cloning) |
| No automatic "best moments" clipping of long videos | OpusClip, Riverside Magic Clips |
| No direct publishing to platforms | video-editing-skill (WoopSocial) |

## Ideas worth taking

1. An automatic **QA gate** after every render (duration, streams, loudness, captions present),
   blocking a bad file from being reported as done.
2. **More transitions** through HyperFrames' registry (light leak, zoom blur, whip pan),
   chosen per junction.
3. A **long-video-to-clips** mode that scores moments in the Hebrew transcript. This is an open
   space, because OpusClip does not support Hebrew.
4. A **free local Hebrew TTS**, if a good open voice appears, so narration also stays local.
5. **Free stock search** (Pexels, Wikimedia) to fill b-roll gaps.
6. A public **Hebrew benchmark**: transcription accuracy and screenshots of mixed
   Hebrew/English/number karaoke.

## Sources

[video-use](https://github.com/browser-use/video-use) ·
[OpenMontage](https://github.com/calesthio/OpenMontage) ·
[Kinocut](https://github.com/KyaniteLabs/kinocut) ·
[ffmpeg-skill](https://github.com/kajisho5/ffmpeg-skill) ·
[claude-code-video-toolkit](https://github.com/digitalsamba/claude-code-video-toolkit) ·
[Remotion licence](https://www.remotion.dev/license) ·
[Descript languages](https://help.descript.com/hc/en-us/articles/10249408168845) ·
[OpusClip RTL](https://help.opus.pro/docs/article/does-opusclip-support-languages-right-left) ·
[Premiere Hebrew request](https://community.adobe.com/feature-requests-730/hebrew-voice-transcription-support-in-premiere-pro-1328496) ·
[Submagic Hebrew](https://www.submagic.co/auto-subtitle-generator/hebrew-subtitles) ·
[HeyGen Hebrew TTS](https://www.heygen.com/text-to-speech/hebrew) ·
[ivrit.ai](https://huggingface.co/ivrit-ai)

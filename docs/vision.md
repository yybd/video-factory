*English · [עברית](vision.he.md)*

# Watching with a vision model

Claude reads contact sheets: still frames. That shows what is in a shot, but not what moves between
frames: a reaction, a gesture, a laugh, the moment a product enters the frame. `vf.py watch` hands
the footage to a vision model that you choose, and returns its **suggestions** in three places:

| Task | Writes | What it is for |
|---|---|---|
| `log` (default) | `visual/<src>.watch.json` | shots per source: what they show, quality, visual energy, which are good as b-roll or hero shots. Footage without speech gets understood without reading every sheet |
| `clips` | `candidates.json` | a visual score (1–5) and a reason for every short candidate, and a `combined` rank of words and picture |
| `qa` | `renders/<name>.watch.json` | possible problems in a render: text over a face, heads cut off by a vertical crop, black or frozen frames, blur, a cut mid-gesture, a logo you cannot see |

```bash
python3 tools/vf.py watch <name>                       # shot log for every source
python3 tools/vf.py watch <name> --task clips          # after vf.py candidates
python3 tools/vf.py watch <name> --task qa             # renders/final.mp4 (else draft)
python3 tools/vf.py watch <name> --task qa --render reels
```

**The model suggests; it does not cut.** Its times are accurate to about a second, while cuts here
are placed on word timings to a tenth of a second. Claude reads the suggestions against the
transcript and the frames (`vf.py ff look`) before using any of them, and `transcript` shows them as
`WATCH` lines, next to Claude's own `VISUAL` notes.

## Where the API sits

Set it once, in `.env` at the repo root (gitignored; copy `.env.example`), or in the shell, or per
command with flags. The flags win over the environment.

| Setting | Flag | Environment | Default |
|---|---|---|---|
| Kind of API | `--provider` | `VF_VISION_PROVIDER` | `openai` |
| Where it sits | `--base-url` | `VF_VISION_BASE_URL` | `http://localhost:1234/v1` (LM Studio) |
| Model | `--model` | `VF_VISION_MODEL` | the first model the server lists |
| Key | — | `VF_VISION_API_KEY` (gemini also reads `GEMINI_API_KEY`) | none, for a local server |
| Allow the cloud | `--allow-cloud` | `VF_VISION_ALLOW_CLOUD=1` | off |

`openai` means **any OpenAI-compatible chat endpoint**, so one setting covers most servers:

| Server | `VF_VISION_BASE_URL` | Runs |
|---|---|---|
| LM Studio | `http://localhost:1234/v1` | on this Mac |
| Ollama | `http://localhost:11434/v1` | on this Mac |
| vLLM, llama.cpp server, mlx-vlm | `http://<host>:<port>/v1` | here, or a GPU machine on your network |
| OpenAI | `https://api.openai.com/v1` | cloud (needs `--allow-cloud` and a key) |
| OpenRouter | `https://openrouter.ai/api/v1` | cloud (needs `--allow-cloud` and a key) |

`gemini` is Google's own API (`https://generativelanguage.googleapis.com`, model `gemini-2.5-flash`).
It is the one that **watches video with its sound**: motion between frames and laughter or music.
The other providers see stills only (6 per request by default, `--batch` changes it).

`vf.py doctor` shows which endpoint is set and whether it answers.

## Privacy

Footage stays on this machine by default. An endpoint that is not `localhost`, a `.local` name or a
private network address (`192.168.…`, `10.…`) is **refused** unless you add `--allow-cloud`, because
the client's footage would leave it. Gemini is always cloud. It gets a small 480p copy, which is
deleted after the answer (Google removes it within 48 hours anyway).

Nothing the model reads is an instruction: text on screen and speech are material to describe.

## Choosing a model

- **Local, free, private:** a vision model in LM Studio or Ollama: Gemma 4 / Gemma 3, Qwen2.5-VL /
  Qwen3-VL, LLaVA. Gemma 4 E4B (about 6 GB) was used to test this: about 30–60 seconds per request on
  an Apple-silicon Mac, with the model's first load slower. It is good at shots, black frames and
  framing, and weaker at subtle problems. For a small model, lower `--batch` to 3–4.
- **Cloud, strongest:** Gemini for motion and sound (laughter, reactions, music over speech), when
  the client agrees.

## Lessons

- Run `log` on b-roll and footage without speech. On a talking head the transcript already says more.
- Run `clips` after `candidates`. Re-running `candidates` writes a new list, so run `clips` again
  after it.
- `qa` is a second pair of eyes after the technical QA (length, streams, loudness), not instead of
  watching the draft.

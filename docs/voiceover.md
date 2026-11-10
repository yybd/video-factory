*English · [עברית](voiceover.he.md)*

# Voice-over

## The script — `projects/<name>/script.md`

One paragraph per **beat**: one idea, 1–3 sentences, about 2–6 seconds spoken. A blank line
separates beats. Lines starting with `#` or `>` are notes and are not read aloud. Use `>` to plan
each beat's visual.

```markdown
# ACME app — 30 s promo

מכירים את הרגע שבו המים רותחים ואתם לא יודעים מה הלאה?
> beat 1: kitchen, pot boiling, confused face

עם האפליקציה של אקמה, כל מתכון מחולק לצעדים פשוטים, עם טיימר מובנה לכל שלב.
> beat 2: app screen recording — steps, then the timer

תשעים ושמונה אחוז מהמשתמשים שלנו מבשלים יותר בבית. הורידו עכשיו.
> beat 3: stat 98%, then end card
```

Spell the brand the way it should be pronounced. If a voice reads digits badly, write numbers as
words.

## Providers

| `--provider` | Key(s) | `--voice` | Notes |
|---|---|---|---|
| `elevenlabs` | `ELEVENLABS_API_KEY` | a voice id from your library | model `eleven_v3` by default (multilingual, Hebrew included); `--model` to change |
| `azure` | `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION` | any voice of the language, e.g. `en-US-JennyNeural`; `he-IL-HilaNeural` is the default for Hebrew | neural voices, the locale is taken from the voice |
| `google` | `GOOGLE_TTS_API_KEY` | any voice of the language, e.g. `en-US-Neural2-F`; `he-IL-Wavenet-A` is the default for Hebrew | |
| `openai` | `OPENAI_API_KEY` | `alloy` (default), `nova`, … | model `gpt-4o-mini-tts`; the language via an instruction |
| `say` | — | a voice for the project's language (`Samantha`, `Carmit`, `Mónica`…) | macOS only, free; a scratch voice to time the edit |

The API providers were written against each provider's documented endpoint and have not been
run against a live key here. The first real run is the test. Compare voices on one beat
(`--only 1`) before voicing the whole script.

Keys come from the shell or a `.env` file at the repo root or in the project (gitignored):

```bash
ELEVENLABS_API_KEY=...
AZURE_SPEECH_KEY=...
AZURE_SPEECH_REGION=westeurope
```

## Running it

```bash
python3 tools/vf.py voice <name> --provider say                     # scratch, to time the edit
python3 tools/vf.py voice <name> --provider azure --voice he-IL-AvriNeural
python3 tools/vf.py voice <name> --provider elevenlabs --voice <id> --only 2   # redo beat 2
```

It writes `voice/beat_NN.wav` (each beat, trimmed of the provider's silence), `voice/voiceover.wav`
(the beats joined with `--gap` seconds between them) and `voice/beats.json` (each beat's text,
start and end). It prints the timing of every beat. Unchanged beats are not voiced again: the
cache key is the text, the provider and the voice.

It then transcribes the narration into `transcript/voiceover.json` for captions and karaoke. When
whisper hears a beat as the same number of words as the script, the script's spelling is used
with whisper's timings. Brand names come out right.

## Fitting the visuals to the voice

In `story.json`, add the voice-over and give each beat parts whose lengths fill it:

```json
"voiceover": {"file": "voice/voiceover.wav", "at": 0.3, "mode": "replace"},
"transition": {"type": "fade", "duration": 0.4},
"parts": [
  {"id": "b1", "source": "kitchen", "start": 2.0, "end": 6.4, "exact": true, "captions": false},
  {"id": "b2", "source": "app-screen", "start": 0.0, "end": 6.0, "exact": true, "captions": false},
  {"id": "b3", "motion": {"template": "stat", "vars": {"value": 98, "suffix": "%", "label": "מבשלים יותר בבית", "opaque": true}, "duration": 5.8}},
  {"id": "end", "motion": {"template": "end-card", "vars": {"cta": "הורידו עכשיו"}}}
]
```

A part's place on the final timeline is the sum of the previous parts minus one transition per
junction. Line each part up with its beat's start in `beats.json` (plus `at`). The render prints
every part's length and the total, so a mismatch shows at once. `"mode": "mix"` keeps the
footage's own sound under the narration.

*[English](voiceover.md) · עברית*

<div dir="rtl">

# קריינות

## התסריט — `projects/<name>/script.md`

פסקה אחת לכל **מקטע**: רעיון אחד, 1–3 משפטים, בערך 2–6 שניות בהקראה. שורה ריקה
מפרידה בין מקטעים. שורות שמתחילות ב-`#` או ב-`>` הן הערות ולא מוקראות. השתמשו ב-`>` כדי לתכנן
את הוויזואליה של כל מקטע.

</div>

```markdown
# ACME app — 30 s promo

מכירים את הרגע שבו המים רותחים ואתם לא יודעים מה הלאה?
> beat 1: kitchen, pot boiling, confused face

עם האפליקציה של אקמה, כל מתכון מחולק לצעדים פשוטים, עם טיימר מובנה לכל שלב.
> beat 2: app screen recording — steps, then the timer

תשעים ושמונה אחוז מהמשתמשים שלנו מבשלים יותר בבית. הורידו עכשיו.
> beat 3: stat 98%, then end card
```

<div dir="rtl">

כתבו את שם המותג כפי שהוא אמור להישמע. אם קול מסוים מקריא ספרות רע, כתבו את המספרים
במילים.

## ספקים

| `--provider` | מפתח/ות | `--voice` | הערות |
|---|---|---|---|
| `elevenlabs` | `ELEVENLABS_API_KEY` | מזהה קול מהספרייה שלכם | מודל `eleven_v3` כברירת מחדל (רב-לשוני, כולל עברית); `--model` כדי לשנות |
| `azure` | `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION` | כל קול של השפה, למשל `en-US-JennyNeural`; ‏`he-IL-HilaNeural` ברירת המחדל לעברית | קולות נוירוניים, השפה נלקחת משם הקול |
| `google` | `GOOGLE_TTS_API_KEY` | כל קול של השפה, למשל `en-US-Neural2-F`; ‏`he-IL-Wavenet-A` ברירת המחדל לעברית | |
| `openai` | `OPENAI_API_KEY` | `alloy` (ברירת מחדל), `nova`, … | מודל `gpt-4o-mini-tts`; השפה באמצעות הנחיה |
| `say` | — | קול לשפת הפרויקט (`Carmit`, ‏`Samantha`, ‏`Mónica`…) | macOS בלבד, חינמי; קול זמני לתזמון העריכה |

ספקי ה-API נכתבו לפי נקודת הקצה המתועדת של כל ספק, ועדיין לא הורצו כאן מול מפתח
אמיתי. ההרצה האמיתית הראשונה היא הבדיקה. השוו בין קולות על מקטע אחד
(`--only 1`) לפני שמקריאים את כל התסריט.

המפתחות נלקחים מה-shell או מקובץ `.env` בשורש המאגר או בפרויקט (ב-gitignore):

</div>

```bash
ELEVENLABS_API_KEY=...
AZURE_SPEECH_KEY=...
AZURE_SPEECH_REGION=westeurope
```

<div dir="rtl">

## הרצה

</div>

```bash
python3 tools/vf.py voice <name> --provider say                     # scratch, to time the edit
python3 tools/vf.py voice <name> --provider azure --voice he-IL-AvriNeural
python3 tools/vf.py voice <name> --provider elevenlabs --voice <id> --only 2   # redo beat 2
```

<div dir="rtl">

הפקודה כותבת `voice/beat_NN.wav` (כל מקטע, בלי השקט שהספק מוסיף), `voice/voiceover.wav`
(המקטעים מחוברים עם `--gap` שניות ביניהם) ו-`voice/beats.json` (הטקסט, ההתחלה והסוף של כל
מקטע). היא מדפיסה את התזמון של כל מקטע. מקטעים שלא השתנו לא מוקראים שוב: מפתח
המטמון הוא הטקסט, הספק והקול.

אחר כך היא מתמללת את הקריינות אל `transcript/voiceover.json` לטובת הכתוביות והקריוקי. כש-whisper
שומע במקטע אותו מספר מילים כמו בתסריט, נעשה שימוש בכתיב של התסריט עם התזמון של whisper.
כך שמות מותגים יוצאים נכון.

## התאמת הוויזואליה לקול

ב-`story.json`, הוסיפו את הקריינות ותנו לכל מקטע חלקים שהאורך שלהם ממלא אותו:

</div>

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

<div dir="rtl">

המקום של חלק על ציר הזמן הסופי הוא סכום החלקים שלפניו, פחות מעבר אחד לכל נקודת
חיבור. ישרו כל חלק עם תחילת המקטע שלו ב-`beats.json` (ועוד `at`). הרינדור מדפיס
את האורך של כל חלק ואת הסך הכולל, כך שאי-התאמה מתגלה מיד. `"mode": "mix"` משאיר את
הסאונד המקורי של החומר המצולם מתחת לקריינות.

</div>

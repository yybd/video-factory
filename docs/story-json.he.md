*[English](story-json.md) · עברית*

<div dir="rtl">

# מדריך story.json

`projects/<name>/story.json` הוא העריכה. Claude כותב אותו, אתם מאשרים, ו-`vf.py render`
קורא אותו. כל הזמנים בשניות.

## דוגמה מלאה

</div>

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

<div dir="rtl">

## הרמה העליונה

| מפתח | ברירת מחדל | משמעות |
|---|---|---|
| `title` | — | מוצג בדף ההערות ללקוח |
| `output` | גודל קובץ המקור הראשון, 30 fps | `width`, `height`, `fps` של התוצאה |
| `fit` | `pad` | איך מקורות ביחס אחר מגיעים לפלט: `pad` (פסים) או `crop` |
| `transition` | `fade`, 0.5 | `type` ו-`duration` לכל נקודת חיבור |
| `parts` | חובה | העריכה, לפי הסדר |
| `overlays` | — | גרפיקות מעל העריכה |
| `broll` | — | קטעי חיתוך מעל העריכה |
| `broll_audio` | `a` | מתחת לקטע חיתוך: `a` (שומרים את הקול), `b`, או `mix` |
| `look` | — | מעבר צבע |
| `voiceover` | — | קריינות (מונחה תסריט) |
| `music` | — | מוזיקת רקע |
| `captions` | פועל | כתוביות ותרגומים |
| `loudness` | — | יעד LUFS משולב לרינדורים סופיים, למשל `-14` |
| `versions` | — | גרסאות בעלות שם |

## חלקים

חלק הוא **חומר מצולם** או **גרפיקה בתנועה** (motion).

### חלק חומר מצולם

| מפתח | ברירת מחדל | משמעות |
|---|---|---|
| `id` | חובה | ייחודי; שכבות עליונות וצילומי אווירה (b-roll) מפנים אליו |
| `source` | חובה | שם הקובץ תחת `source/` בלי הסיומת |
| `start`, `end` | חובה | שניות בקובץ המקור |
| `exact` | `false` | `true` = חותכים בדיוק שם; אחרת, חיתוך באמצע מילה זז לשקט שמחוצה לה |
| `clean` | `[]` | `"fillers"` (הברות היסוס מתוך `tools/fillers.<lang>.txt`), `"pauses"` |
| `max_pause` | `0.6` | יחד עם `pauses`: כל שתיקה ארוכה מזה מתקצרת לאורך הזה |
| `captions` | `true` | `false` = בלי כתוביות על החלק הזה |
| `title`, `why` | — | לבני אדם: מה זה ולמה זה שם |

### חלק גרפיקה בתנועה

`{"id": "...", "motion": {"template": "<name>", "vars": {...}, "duration": s, "logo": true}}`,
גרפיקה במסך מלא שמרונדרת בגודל הפלט. התבניות והמשתנים שלהן:
[גרפיקה בתנועה](motion-graphics.he.md).

## מעברים

ה-`transition` של הסיפור הוא ברירת המחדל בכל נקודת חיבור. כל חלק יכול להגדיר מעבר **נכנס** משלו,
כך שכל חיבור יכול להיות שונה. דוגמה:

</div>

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

<div dir="rtl">

כל סוג ש-xfade של FFmpeg מכיר מתקבל (הבדיקה מראש מציגה מה יש ב-FFmpeg שלכם):

</div>

`fade fadefast fadeslow fadeblack fadewhite fadegrays dissolve pixelize distance hblur · wipeleft wiperight wipeup wipedown wipetl wipetr wipebl wipebr · slideleft slideright slideup slidedown · smoothleft smoothright smoothup smoothdown · coverleft coverright coverup coverdown · revealleft revealright revealup revealdown · circleopen circleclose circlecrop rectcrop radial · vertopen vertclose horzopen horzclose · diagtl diagtr diagbl diagbr · hlslice hrslice vuslice vdslice · hlwind hrwind vuwind vdwind · squeezeh squeezev zoomin · none`

<div dir="rtl">

כללי אצבע: בתוך נושא, `fade` של 0.3–0.5 שנ׳ או `none`. נושא חדש, `fadeblack` של 0.6–1 שנ׳. כניסה
לגרפיקה, `zoomin`, `slideleft` או `circleopen`. מונטאז׳, `none` או `dissolve`. חלק צריך להיות ארוך
מסכום המעבר הנכנס והיוצא שלו, והבדיקה מראש אומרת איזה חלק קצר מדי.

## שכבות עליונות

כל שכבה עליונה ממוקמת לפי `{"part": id, "at": seconds into that part}` (שניות מתחילת אותו חלק)
או לפי `{"at_final": seconds}`. `"whole": true` מציג אותה לאורך כל הסרטון.

| סוג | מפתחות |
|---|---|
| גרפיקה בתנועה (שקופה) | `"motion": {"template": "lower-third" \| "stat" \| custom, "vars", "duration"}` |
| תמונה | `"image": "assets/x.png"`, `position` (`top-right`, `top-left`, `bottom-right`, `bottom-left`, `center` או `X,Y`), `scale` (רוחב בפיקסלים), `opacity`, `duration` |
| לוגו המיתוג | `"logo": true` (מתוך `brand.json`), `position`, `scale`, `opacity` |

## צילומי אווירה (b-roll)

`{"part": id, "at": s, "source": src, "from": s, "duration": s}`: מציג את התמונה של קובץ מקור אחר
מנקודה `from` למשך `duration`, החל מ-`at` שניות לתוך החלק. כדי לחתוך לגרפיקה, משתמשים
ב-`"motion": {...}` במקום `source`.

## מראה (Look)

`lut` (קובץ `.cube` בפרויקט), `lut_strength` (0–1), ותיקון צבע: `exposure`
(בסטופים), `contrast`, `saturation` (1 = ללא שינוי), `temperature` (בקלווין), `tint`, `gamma`,
`lift`, `gain`.

## קריינות

`{"file": "voice/voiceover.wav", "at": 0.3, "mode": "replace" | "mix", "gain": 0, "bed_db": -12}`.
`replace` מחליף את הסאונד של העריכה בקריינות. `mix` משאיר את הסאונד של החומר המצולם `bed_db`
מתחתיה. הכתוביות עוקבות אחרי הקריינות (`transcript/voiceover.json`), אלא אם `captions.source`
הוא `"parts"`.

## מוזיקה

`{"file": "music/x.mp3", "volume": -20, "duck": true, "duck_amount": 12, "loop": true, "fade_out": 3}`.
`volume` נמדד ב-dBFS, ההנמכה (ducking) מורידה את המוזיקה מתחת לדיבור, ו-`loop` חוזר על רצועה קצרה.

## כתוביות

| מפתח | ברירת מחדל | משמעות |
|---|---|---|
| `enabled` | `true` | |
| `language` | של הפרויקט | קובע גם את רשימת הברות ההיסוס |
| `source` | `voiceover` כשיש קריינות, אחרת `parts` | מאיפה מגיעות המילים |
| `font` | גופן המיתוג, אחרת גופן שמכסה את השפה (`Arial Hebrew` לעברית ב-macOS) | כל משפחת גופנים מותקנת שיש בה האותיות של השפה |
| `size`, `position` (`bottom`, `top`, `center`), `max_lines` (2), `animate` (`fade`, `pop`, `slide`) | | מראה |
| `karaoke`, `karaoke_style` (`sweep`, `word`) | כבוי | הדגשת כל מילה ברגע שהיא נאמרת |
| `cues` | — | תיקונים: `{"id": "<source>:<segment #>" or "voiceover:<#>", "text"}` |
| `translations` | — | `{"<lang>": {"file": "translations/<lang>.json", "mode": "mux" \| "burn", "position": "top"}}` |

קובץ תרגום הוא `{"cues": {"<cue id>": "translated text"}}`, עם אותם מזהים כמו ב-`cues`.

## גרסאות

`"versions": {"<name>": {"parts": [ids in order], …any top-level key to override…}}` — רשימת
מזהי החלקים לפי הסדר, ועוד כל מפתח מהרמה העליונה שרוצים לדרוס.
`vf.py render <project> --version <name>` כותב את `renders/<name>.mp4`. שכבות עליונות וצילומי
אווירה על חלקים שהגרסה משמיטה מדולגים. הגרפיקות מרונדרות מחדש בגודל של הגרסה.

אובייקט ריק או `null` מנקים מפתח בגרסה (`"captions": {"translations": {}}` = בלי כתוביות בשפה נוספת בגרסה הזו). בצבע, התיקון רץ קודם, וה-LUT מעליו (שני מעברים).

</div>

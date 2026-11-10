*[English](cli.md) · עברית*

<div dir="rtl">

# מדריך הפקודות — `tools/vf.py`

מריצים משורש המאגר: `python3 tools/vf.py <command> …`. `<project>` הוא שם תחת
`projects/` (או נתיב). ספרייה סטנדרטית בלבד.

## doctor
בודק את ffmpeg-full ואת המסננים שלו (subtitles, ass, drawtext, xfade, tile), את ffmpeg-skill,
את whisper-cli, את המודל ואת גיבוי local-models האופציונלי. מחזיר קוד יציאה 1 אם חסר משהו
הכרחי.

## new `<name> <video|folder>… [--copy]`
יוצר את `projects/<name>/` (source, transcript, visual, parts, renders) ו**מקשר** את קובצי המקור.
תיקייה מוסיפה את קובצי הווידאו שברמה העליונה שלה (`.mp4 .mov .m4v .mkv .webm .avi .mts`). בטוח
להריץ שוב, ואפשר גם להוסיף קובץ לפרויקט קיים. `--copy` מעתיק במקום לקשר (כונן חיצוני, תיקיית
ענן, מקורות שעומדים לזוז). קובצי ענן שלא הורדו (placeholders) נדחים. הקלטים נבדקים לפני
שנוצר משהו.

## transcribe `<project>` [options]
תמלול אחד לכל קובץ מקור, `transcript/<src>.json` (מקטעים עם מילים, בשניות) ועוד `.srt`.

| דגל | ברירת מחדל | |
|---|---|---|
| `--language` | `he` | שפת הדיבור |
| `--prompt` | — | שמות ומונחים, כמשפט קצר |
| `--model` | `VF_WHISPER_MODEL` / ivrit.ai | קובץ מודל ggml |
| `--local-models` | כבוי | שימוש בגיבוי local-models (בלי תזמון למילים) |
| `--presets` | — | מילוני הטיה של local-models |
| `--force` | כבוי | תמלול מחדש של תמלולים קיימים |

## transcript `<project> [--words]`
מדפיס את המקטעים של כל קובץ מקור בצורה `[src#N mm:ss.ss-mm:ss.ss] text`, משולבים עם שורות
`VISUAL` מתוך `visual/<src>.json`. `--words` מוסיף כל מילה עם הזמן שלה; `*` מסמן הברת היסוס.

## frames `<project> [--every N] [--width W] [--threshold T]`
גיליונות תמונות ממוזערות של 12 אריחים עם קוד זמן (`visual/<src>_sheet_NNN.png`, אריח אחד כל N
שניות, ברירת מחדל כ-48 אריחים לכל קובץ מקור) ורשימת סצנות (`visual/<src>.scenes.json`).

## scenes `<project> [--threshold T]`
מדפיס את חילופי הסצנות בכל קובץ מקור.

## render `<project>` [options]
מרנדר את `story.json` (ראו [מדריך story.json](story-json.he.md)) אל `renders/final.mp4`.

| דגל | |
|---|---|
| `--draft` | איכות תצוגה מקדימה מהירה ← `renders/draft.mp4`; מדלג על נרמול העוצמה |
| `--version V` | גרסה מתוך `story.json` ← `renders/V.mp4` |
| `--force` | חיתוך מחדש של כל חלקי החומר המצולם |
| `--keep-stages` | שומר את `renders/.stages-<name>/` (קובץ הביניים של כל שלב) |

הפקודה מדפיסה את האורך האמיתי של כל חלק, מה הניקוי הסיר, ואת משך הזמן המתוכנן מול המשך
בפועל. היא גם כותבת `captions.srt`, `captions.words.json`, `captions.<lang>.srt` וגיליון
תמונות ממוזערות `renders/<name>_sheet.png`.

## voice `<project>` [options]
קריינות מתוך `script.md`; ראו [קריינות](voiceover.he.md).

| דגל | ברירת מחדל | |
|---|---|---|
| `--provider` | `say` | `elevenlabs`, `azure`, `google`, `openai`, `say` |
| `--voice` | ברירת המחדל של הספק | מזהה / שם של קול |
| `--model` | ברירת המחדל של הספק | למשל `eleven_v3`, `gpt-4o-mini-tts` |
| `--script` | `script.md` | |
| `--language` | `he` | |
| `--speed` | `1.0` | |
| `--gap` | `0.6` | שניות שקט בין מקטעים |
| `--only` | — | הקראה מחדש רק של המקטעים האלה, למשל `2,5` |

## beats `<project> <music file>`
קצב, מספר הפעמות ותחילתה של כל תיבה, כדי שאפשר יהיה לחתוך חלקים לפי המוזיקה. הרשת המלאה
נכתבת אל `renders/<music>.beats.json`.

## review `<project> [--version V]`
כותב את `renders/<V or final>_review.html` לצד הסרטון. ראו [מסירה](delivery.he.md).

## export `<project> [--format fcpxml|edl|otio] [--version V]`
העריכה כציר זמן לתוכנת עריכה ב-`renders/edit.<format>`, שמצביע על הקבצים המקוריים. כרטיסי
הגרפיקה מרונדרים ונכללים כקליפים.

## ff `<tool> [args…]`
מריץ כל כלי של ffmpeg-skill כש-ffmpeg-full נמצא ב-PATH, למשל `vf.py ff check renders/final.mp4
--platform reels`. `vf.py ff <tool> --help` מציג את הדגלים שלו; טבלת הבקשות
נמצאת ב-`.claude/skills/ffmpeg-skill/SKILL.md`.

</div>

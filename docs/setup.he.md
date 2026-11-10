*[English](setup.md) · עברית*

<div dir="rtl">

# התקנה

## דרישות

| מה | למה | התקנה (macOS) |
|---|---|---|
| Python 3.10+ | `tools/vf.py` ו-ffmpeg-skill (ספרייה סטנדרטית בלבד) | מותקן מראש / `brew install python` |
| FFmpeg **עם libass** | חיתוך, חיבור, צריבת כתוביות | `brew install ffmpeg-full` (keg-only; `vf.py` מוצא אותו) |
| whisper.cpp | תמלול עם תזמון לכל מילה | מגיע עם ffmpeg-full, או `brew install whisper-cpp` |
| מודל ggml רב-לשוני | כל השפות, וזיהוי שפה | `hf download ggerganov/whisper.cpp ggml-large-v3-turbo.bin` (1.6 GB) |
| מודל ggml של ivrit.ai (לעברית בלבד) | עברית מדויקת | `hf download ivrit-ai/whisper-large-v3-ggml ggml-model.bin` (2.9 GB) או `…-turbo-ggml` (1.5 GB, מהיר יותר) |
| Node.js 22+ | גרפיקה בתנועה (HyperFrames, מורץ עם `npx`) | `brew install node` |
| Google Chrome | HyperFrames מרנדר HTML ב-Chrome ללא ממשק (headless) | בדרך כלל כבר מותקן; HyperFrames יכול להוריד עותק משלו |
| Claude Code | המתזמר | [claude.com/claude-code](https://claude.com/claude-code) |

נוסחת `ffmpeg` הרגילה לא יודעת לצרוב כתוביות (אין בה libass). בלינוקס, ה-ffmpeg של ההפצה
בדרך כלל כולל libass. בודקים הכול עם:

</div>

```bash
python3 tools/vf.py doctor
```

<div dir="rtl">

## שפה

לכל פרויקט יש שפה אחת, שנשמרת ב-`projects/<name>/project.json`. קובעים אותה עם
‏`vf.py new <name> … --language es`, או נותנים לתמלול הראשון לזהות אותה (לזה צריך את המודל
הרב-לשוני). התמלול, הסרת הברות ההיסוס, הכתוביות, כיוון הגרפיקה (מימין לשמאל בעברית, ערבית, פרסית…),
דף ההערות והקריינות הולכים כולם לפיה. דגל בפקודה גובר עליה לאותה הרצה. כשהזיהוי שומע עברית ומודל ivrit.ai מותקן, הקובץ מתומלל שוב
בעזרתו. כשמותקן רק מודל ivrit.ai, צריך לציין את השפה: הוא לא יודע לזהות אותה.

## משתני סביבה

| משתנה | ברירת מחדל | משמעות |
|---|---|---|
| `VF_LANGUAGE` | — (זיהוי) | שפת פרויקטים חדשים כשלא נותנים `--language`: `en`, `he`, `es`… |
| `VF_WHISPER_MODEL` | המודל הרב-לשוני large-v3-turbo במטמון של Hugging Face | המודל לכל שפה חוץ מעברית, ולזיהוי שפה |
| `VF_WHISPER_MODEL_HE` | מודל ivrit.ai במטמון של Hugging Face | המודל לעברית |
| `VF_WHISPER_DTW` | לפי שם המודל | תצורת יישור DTW, אם השם לא מציין אותה (`large.v3`, `large.v3.turbo`, …) |
| `VF_FFMPEG_BIN` | ה-ffmpeg-full של Homebrew | התיקייה שמכילה `ffmpeg` ו-`ffprobe` עם libass |
| `HYPERFRAMES_NO_TELEMETRY` | `1` (מוגדר ב-`.claude/settings.json`) | מונע מ-HyperFrames לשלוח אירועי שימוש |
| `VF_VISION_PROVIDER`, `VF_VISION_BASE_URL`, `VF_VISION_MODEL`, `VF_VISION_API_KEY`, `VF_VISION_ALLOW_CLOUD` | ‏LM Studio על localhost | איפה יושב מודל הראייה של `vf.py watch`; ראו [מודל ראייה](vision.he.md) |
| `ELEVENLABS_API_KEY`, `AZURE_SPEECH_KEY` + `AZURE_SPEECH_REGION`, `GOOGLE_TTS_API_KEY`, `OPENAI_API_KEY` | — | ספקי קריינות; ראו [קריינות](voiceover.he.md) |

מפתחות API נכנסים ל-shell או לקובץ `.env` בשורש המאגר (או בתיקיית פרויקט). `.env` מופיע
ב-gitignore. ‏`.env.example` מפרט את כל המשתנים: מעתיקים אותו ל-`.env` וממלאים רק את מה שמשתמשים בו. לעולם אין לשים מפתח ב-`story.json` או בשום קובץ שנמצא במעקב.

## פרטיות

הכול רץ על המחשב שלכם: תמלול, חיתוך, גרפיקה וכתוביות. רק אלה פונים לרשת:

- **HyperFrames** טוען את ספריית האנימציה GSAP מ-CDN בזמן רינדור של גרפיקה. שום חומר מצולם
  לא נשלח. הטלמטריה שלו כבויה במאגר הזה.
- **ספקי הקריינות** מקבלים את טקסט התסריט שאתם שולחים אליהם (רק כשמריצים `vf.py voice`
  עם ספק API).
- **מודל ראייה**, רק אם מכוונים את `vf.py watch` לכתובת בענן ומוסיפים `--allow-cloud`. ברירת המחדל
  היא שרת מקומי, וכל כתובת מחוץ למחשב או לרשת נחסמת בלי הדגל.

## תוסף נלווה אופציונלי: `/watch`

[claude-video](https://github.com/bradautomates/claude-video) (MIT) מאפשר ל-Claude לצפות בסרטון
מכתובת URL: פריימים ותמלול. הוא מומלץ לסרטוני **רפרנס** ("תעשה את זה כמו הפרסומת הזאת"),
והוא לא חלק מהמאגר הזה. מתקינים אותו ב-Claude Code עם
`/plugin marketplace add bradautomates/claude-video`, ואחר כך `/plugin install watch@claude-video`.
מנוע ה-Gemini שלו מעלה את הסרטון ל-Google, אז אל תריצו אותו על חומר מצולם של לקוחות.

## פתרון תקלות

| תסמין | סיבה / פתרון |
|---|---|
| `filter subtitles MISSING` ב-doctor | ffmpeg רגיל — `brew install ffmpeg-full` |
| `no transcription engine` | התקינו whisper.cpp ומודל, או הגדירו `VF_WHISPER_MODEL` |
| `cannot transcribe English: only the Hebrew model…` | מודל ivrit.ai עונה בעברית על כל דיבור: התקינו את המודל הרב-לשוני, או ציינו `--language he` אם החומר בעברית |
| `… is a cloud placeholder` | הקובץ נמצא ב-iCloud / Google Drive ולא הורד — הורידו אותו, או השתמשו ב-`--copy` אחרי ההורדה |
| `HyperFrames render failed` | הריצו את `npx hyperframes@0.9.27 check <dir>` שהוא מדפיס; בדרך כלל עריכה של תבנית שברה את ה-HTML |
| מילות הקריוקי בעברית או בערבית מופיעות בסדר הפוך | חסר התיקון של caption.py שמוטמע במאגר — ראו `.claude/skills/ffmpeg-skill/VENDORED.md` |
| חלק נחתך מחדש בכל רינדור | טווחי השמירה שלו השתנו (הצמדה או ניקוי הזיזו אותם); צפוי פעם אחת |
| הרינדור איטי | השתמשו ב-`--draft` בזמן העריכה; חלקים וגרפיקות נשמרים במטמון בין רינדורים |

</div>

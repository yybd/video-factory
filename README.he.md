*[English](README.md) · עברית*

<div dir="rtl">

# video-factory

עריכת וידאו בשיחה עם Claude Code. שמים חומר גלם ואומרים מה רוצים, למשל
*"תחתוך לפי נושאים, תפתח בטיפ על שינה, מעבר דהייה בין החלקים, כתוביות בעברית"*,
ומקבלים קובץ `final.mp4` גמור.

הפרויקט בנוי קודם כול לעברית: תמלול עברי מקומי (Whisper של ivrit.ai) וכתוביות
שמוצגות נכון מימין לשמאל. הכול רץ על המחשב שלך: בלי ענן, בלי מפתחות API, והחומר
שלך לא יוצא מהמחשב.

## מה הוא עושה

הסקיל **video-orchestrator** מנצח על כל העריכה:

1. **תמלול**: תמלול עם חותמות זמן לכל קטע מקור.
2. **חלוקה לפי משמעות**: Claude קורא את התמלול ומחלק את החומר לחלקים, רעיון אחד
   בכל חלק. נקודות החיתוך נופלות בשקט שבין המשפטים ולא באמצע מילה, ואפשר גם
   להצמיד אותן לחילופי סצנה.
3. **בניית סיפור**: Claude בוחר את החלקים ומסדר אותם (פתיח, מהלך, סיום), מסביר כל
   בחירה ומחכה לאישור שלך.
4. **חיבור עם מעברים**: דהייה, התמזגות, מעבר לשחור, ניגובים, החלקות ועוד. הרזולוציה,
   קצב הפריימים והשמע מתואמים בין הקטעים.
5. **כתוביות**: התמלול מתוזמן מחדש לפי העריכה הסופית, מתוקן ונצרב בפונט עברי, מימין
   לשמאל, בשתי שורות לכל היותר.
6. **בדיקה**: Claude מסתכל על גיליון תמונות מהתוצאה לפני שהוא מדווח.

כל השאר (הסרת שקטים, נרמול עוצמה ל-‎-14 LUFS, לוגו, כותרות תחתונות, שינויי מהירות,
צבע, ייצוב, ייצוא ליוטיוב, לרילס או לטיקטוק) מגיע מהסקיל
[ffmpeg-skill](https://github.com/kajisho5/ffmpeg-skill) שמצורף לפרויקט (42 כלים,
רישיון MIT).

## דרישות

- macOS או Linux, ‏Python 3.10 ומעלה
- **FFmpeg עם libass**: ב-macOS ‏`brew install ffmpeg-full`. הנוסחה הרגילה `ffmpeg` לא
  יודעת לצרוב כתוביות. ב-Linux ה-ffmpeg של ההפצה כולל בדרך כלל libass.
- **מנוע תמלול**, אחד מהשניים:
  - [whisper.cpp](https://github.com/ggml-org/whisper.cpp) (`brew install whisper-cpp`) עם מודל
    ggml. לעברית: מודל של [ivrit.ai](https://huggingface.co/ivrit-ai), ואז
    `export VF_WHISPER_MODEL=/path/to/model.bin`
  - פרויקט local-models שמספק `local-models transcribe` (`export VF_LOCAL_MODELS=...`)
- [Claude Code](https://claude.com/claude-code)

## התחלה מהירה

</div>

```bash
git clone <this repo> video-factory && cd video-factory
python3 tools/vf.py doctor
claude
```

<div dir="rtl">

ואז ב-Claude Code:

> תעשה פרויקט בשם *trip* מ-‎~/Movies/trip1.mov ומ-‎~/Movies/trip2.mov, תחתוך לפי נושאים
> לסיפור של שתי דקות ותוסיף כתוביות בעברית.

## מבנה

</div>

```
.claude/skills/video-orchestrator/   הסקיל המתזמר: שלבים, כללים, מבנה story.json
.claude/skills/ffmpeg-skill/         הסקיל המבצע (MIT, kajisho5): 42 כלי ffmpeg
tools/vf.py                          כלי שורת הפקודה שהסקיל מפעיל
projects/<name>/                     הפרויקטים שלך: לא עולים ל-git
```

<div dir="rtl">

אפשר להשתמש ב-`tools/vf.py` גם לבד:

</div>

```bash
python3 tools/vf.py new demo ~/Movies/clip.mp4
python3 tools/vf.py transcribe demo
python3 tools/vf.py transcript demo        # read it, then write projects/demo/story.json
python3 tools/vf.py render demo --draft
python3 tools/vf.py render demo
python3 tools/vf.py ff <tool> --help       # any ffmpeg-skill tool, with the right ffmpeg
```

<div dir="rtl">

## מגבלות כרגע

- סוג מעבר אחד לכל הסרטון.
- הכתוביות מתוזמנות לפי משפט ולא לפי מילה, ולכן עדיין אין הדגשת מילים בסגנון קריוקי.

## רישיון

MIT, ראו [LICENSE](LICENSE). ‏`ffmpeg-skill` ברישיון MIT, ‏© kajisho5, ראו את קובץ הרישיון שלו.

</div>

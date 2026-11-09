*[English](README.md) · עברית*

<div dir="rtl">

# video-factory

עריכת וידאו בשיחה עם Claude Code. שמים חומר גלם ואומרים מה רוצים, למשל
*"תחתוך לפי נושאים, תפתח בטיפ על שינה, תוריד את האממ, מעבר דהייה בין החלקים, כתוביות
בעברית"*, ומקבלים קובץ `final.mp4` גמור.

הפרויקט בנוי קודם כול לעברית: תמלול עברי מקומי (Whisper של ivrit.ai) שמתזמן כל מילה,
וכתוביות שמוצגות נכון מימין לשמאל, כולל קריוקי. הכול רץ על המחשב שלך: בלי ענן, בלי
מפתחות API, והחומר שלך לא יוצא מהמחשב.

## מה הוא עושה

הסקיל **video-orchestrator** מנצח על כל העריכה:

1. **תמלול**: תמלול של כל קטע, עם זמן לכל מילה.
2. **הסתכלות**: לחומר בלי דיבור (צילומי אווירה, טיולים, אירועים) נוצרים גיליונות
   תמונות עם חותמות זמן ורשימה של חילופי סצנה. Claude מסתכל עליהם ורושם מה רואים בכל צילום.
3. **חלוקה לפי משמעות**: Claude מחלק את החומר לחלקים, רעיון אחד או רגע אחד בכל חלק.
   חיתוך שנופל באמצע מילה זז לשקט שלפניה או אחריה.
   **אפשר גם לחתוך בשניות מדויקות**: אומרים "מ-1:20 עד 1:45", ושם בדיוק הוא חותך.
4. **בניית סיפור**: Claude בוחר את החלקים ומסדר אותם (פתיח, מהלך, סיום), מסביר כל
   בחירה ומחכה לאישור שלך.
5. **ניקוי**: אפשר להסיר הברות היסוס (אממ, אה) ולקצר שתיקות ארוכות בתוך כל חלק.
   הכתוביות מתעדכנות לפי החיתוכים.
6. **חיבור עם מעברים**: דהייה, התמזגות, מעבר לשחור, ניגובים, החלקות ועוד. הרזולוציה,
   קצב הפריימים והשמע מתואמים בין הקטעים.
7. **כתוביות**: התמלול מתוזמן מחדש לפי העריכה הסופית, מתוקן ונצרב בפונט עברי, מימין
   לשמאל, בשתי שורות לכל היותר. אפשר להפעיל קריוקי, שמדגיש כל מילה בזמן שהיא נאמרת.
8. **בדיקה**: Claude מסתכל על גיליון תמונות מהתוצאה לפני שהוא מדווח.

כל השאר (נרמול עוצמה ל-‎-14 LUFS, לוגו, כותרות תחתונות, שינויי מהירות, צבע, ייצוב,
ייצוא ליוטיוב, לרילס או לטיקטוק) מגיע מהסקיל
[ffmpeg-skill](https://github.com/kajisho5/ffmpeg-skill) שמצורף לפרויקט (42 כלים,
רישיון MIT).

## דרישות

- macOS או Linux, ‏Python 3.10 ומעלה
- **FFmpeg עם libass**: ב-macOS ‏`brew install ffmpeg-full`. הנוסחה הרגילה `ffmpeg` לא
  יודעת לצרוב כתוביות. ב-Linux ה-ffmpeg של ההפצה כולל בדרך כלל libass.
- **whisper.cpp** (‏`brew install whisper-cpp`, והוא מגיע גם עם ffmpeg-full) ומודל עברי
  בפורמט ggml של [ivrit.ai](https://huggingface.co/ivrit-ai). המודל נמצא אוטומטית בתיקיית
  המטמון של Hugging Face:

</div>

```bash
pip install -U huggingface_hub
hf download ivrit-ai/whisper-large-v3-turbo-ggml ggml-model.bin   # 1.5 GB, fast
hf download ivrit-ai/whisper-large-v3-ggml ggml-model.bin         # 2.9 GB, more accurate (preferred when present)
```

<div dir="rtl">

  אפשר גם להצביע עם `VF_WHISPER_MODEL` על כל מודל ggml אחר. לשפות אחרות משתמשים במודל
  Whisper רגיל וב-`‎--language`.
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

> תעשה פרויקט בשם *trip* מהתיקייה ‎~/Movies/trip, תחתוך לפי נושאים לסיפור של שתי דקות,
> תוריד את האממ ותוסיף כתוביות קריוקי בעברית.

לא צריך להכין או להעתיק כלום. מספיק להצביע על תיקייה או על קבצים, והפרויקט מקשר
אליהם. הקבצים המקוריים לא משתנים לעולם. כדאי לבקש העתקה (`‎--copy`) כשהחומר נמצא
בדיסק חיצוני או בתיקיית ענן, או כשמתכננים להזיז את הקבצים המקוריים.

## מבנה

</div>

```
.claude/skills/video-orchestrator/   הסקיל המתזמר: שלבים, כללים, מבנה story.json
.claude/skills/ffmpeg-skill/         הסקיל המבצע (MIT, kajisho5): 42 כלי ffmpeg (תיקונים מקומיים: VENDORED.md)
tools/vf.py                          כלי שורת הפקודה שהסקיל מפעיל
tools/fillers.he.txt                 הברות ההיסוס שהניקוי מסיר
projects/<name>/                     הפרויקטים שלך: לא עולים ל-git
```

<div dir="rtl">

אפשר להשתמש ב-`tools/vf.py` גם לבד:

</div>

```bash
python3 tools/vf.py new demo ~/Movies/trip       # a folder or files; --copy to copy
python3 tools/vf.py transcribe demo              # word timings
python3 tools/vf.py frames demo                  # contact sheets + scenes, for footage without speech
python3 tools/vf.py transcript demo --words      # read it, then write projects/demo/story.json
python3 tools/vf.py render demo --draft
python3 tools/vf.py render demo
python3 tools/vf.py ff <tool> --help             # any ffmpeg-skill tool, with the right ffmpeg
```

<div dir="rtl">

## מגבלות כרגע

- סוג מעבר אחד לכל הסרטון.
- בקריוקי, מילה מודגשת מסוף המילה הקודמת ועד סוף המילה שלה, ולכן ההדגשה מקדימה מעט
  את הקול.

## רישיון

MIT, ראו [LICENSE](LICENSE). ‏`ffmpeg-skill` ברישיון MIT, ‏© kajisho5, ראו את קובץ הרישיון שלו.

</div>

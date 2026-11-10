*[English](delivery.md) · עברית*

<div dir="rtl">

# מסירה

## גרסאות — אנכית, קצרה, לכל פלטפורמה

</div>

```json
"versions": {
  "reels": {"parts": ["intro", "ceo", "outro"], "output": {"width": 1080, "height": 1920}, "fit": "crop"},
  "30s":   {"parts": ["intro", "ceo", "chart", "outro"]},
  "silent-feed": {"captions": {"karaoke": true, "size": 34}, "music": {"volume": -16}}
}
```

```bash
python3 tools/vf.py render <name> --version reels      # -> renders/reels.mp4
```

<div dir="rtl">

`parts` בוחר את החלקים וקובע את הסדר שלהם. כל מפתח אחר דורס את הסיפור עבור הגרסה הזאת בלבד.
`fit: crop` ממלא פריים אנכי מתוך חומר מצולם ב-16:9, ו-`pad` מוסיף לו פסים (letterbox). הגרפיקה
בתנועה מרונדרת מחדש בגודל של הגרסה. שכבות עליונות וצילומי אווירה (b-roll) שקשורים לחלקים
שהגרסה משמיטה מדולגים.

## כתוביות בשפה שנייה

1. מרנדרים פעם אחת, כדי ש-`captions.srt` ומזהי הכתוביות (cue ids) יהיו קיימים.
2. Claude מתרגם אל `translations/en.json`:
   `{"cues": {"interview:0": "Hello everyone…", "interview:1": "…"}}`.
3. מוסיפים `"captions": {"translations": {"en": {"mode": "mux"}}}` ומרנדרים שוב.

`mux` מוסיף רצועת כתוביות שהצופה יכול להפעיל ולכבות, ו-`burn` צורב אותה לתוך התמונה (כברירת מחדל
ב-`top`, כדי שלא תסתיר את העברית). הרינדור מדווח על כתוביות שאין להן
תרגום.

## דף הערות ללקוח

</div>

```bash
python3 tools/vf.py review <name>                 # renders/final_review.html
python3 tools/vf.py review <name> --version reels
```

<div dir="rtl">

הדף יושב לצד הסרטון ומנגן אותו. הלקוח עוצר על רגע מסוים, מקליד הערה
ומוסיף אותה. ההערות נשמרות באותו דפדפן. "Copy" או "Save as file" מפיקים טקסט כזה:

</div>

```
0:03.2 — הלוגו גדול מדי
0:12.4 — לקצר את התשובה הראשונה
```

<div dir="rtl">

שלחו ללקוח את התיקייה `renders/` (או את הסרטון ואת הדף יחד). את ההערות שחוזרות הדביקו
ל-Claude, והוא ממפה כל זמן לחלק ומשנה את `story.json`.

## צירי זמן לתוכנות עריכה

</div>

```bash
python3 tools/vf.py export <name> --format fcpxml   # Final Cut, DaVinci Resolve
python3 tools/vf.py export <name> --format edl      # Premiere, Resolve, Avid (CMX 3600)
python3 tools/vf.py export <name> --format otio     # OpenTimelineIO
```

<div dir="rtl">

ציר הזמן מצביע על הקבצים המקוריים (לא על עותקים), חתוכים כמו בסיפור. כרטיסי הגרפיקה
מרונדרים וממוקמים כקליפים. הכתוביות נכנסות בנפרד, כ-`captions.srt`. חלק שיש בתוכו חיתוכי
ניקוי הופך לכמה קליפים. במקרה כזה המעברים מיוצאים כחיתוכים ישרים, כדי שהמסה (dissolve) לעולם
לא תיפול באמצע משפט. שכבות עליונות, צילומי אווירה, מוזיקה ומראה לא נכללים בציר הזמן:
אלה שלבי גימור שעושים מחדש בתוכנת העריכה.

## בדיקות פלטפורמה וייצוא

</div>

```bash
python3 tools/vf.py ff check renders/final.mp4 --platform youtube    # or reels, tiktok, shorts, linkedin, x …
python3 tools/vf.py ff export renders/final.mp4 --preset youtube --max-mb 25
python3 tools/vf.py ff export renders/final.mp4 --preset gif
python3 tools/vf.py ff metadata renders/final.mp4 --chapters chapters.txt
```

<div dir="rtl">

`check` מוודא גודל, אורך, קצב פריימים, codec ועוצמה מול הדרישות של
הפלטפורמה. למסירה לרשת, הגדירו `"loudness": -14` בסיפור. ההגדרה חלה רק על רינדורים
סופיים.

</div>

*[English](comparison.md) · עברית*

<div dir="rtl">

# איך video-factory עומד מול הקיים (נובמבר 2026)

סקירה של כלי וידאו מבוססי סוכנים ושל עורכי AI מסחריים, עם דגש על מה שחשוב לווידאו בעברית.
מחירים ומספרי כוכבים משתנים כל הזמן. התמיכה בעברית היא מה שכל יצרן **מצהיר**, ורובה לא נבדקה
בפועל.

## במבט אחד

| כלי | סוג | רישיון / מחיר | מקומי? | תמלול עברית | כתוביות RTL / קריוקי |
|---|---|---|---|---|---|
| **video-factory** | סקיל ל-Claude Code וכלי שורת פקודה | MIT | כן (רק ההקראה רצה בענן) | ivrit.ai, ברמת מילה | כן / כן |
| [OpenMontage](https://github.com/calesthio/OpenMontage) | מערכת הפקה מבוססת סוכנים, 12 תהליכים | AGPL-3.0 | כן (ספקי ענן לבחירה) | לא מצוין | לא מצוין |
| [video-use](https://github.com/browser-use/video-use) | סקיל ל-Claude Code: תיקיית קטעים הופכת ל-final.mp4 | MIT | העריכה כן, התמלול דרך ElevenLabs (ענן) | לא מצוין | לא מצוין |
| [Kinocut](https://github.com/KyaniteLabs/kinocut) | שרת MCP, עד 205 כלים | Apache-2.0 | כן | Whisper, לבחירה | לא מצוין |
| [ffmpeg-skill](https://github.com/kajisho5/ffmpeg-skill) | ‏42 כלי FFmpeg לסוכנים (המבצע של video-factory) | MIT | כן | דרך מנועים מקומיים | כן (עם libass ו-fribidi) |
| [claude-code-video-toolkit](https://github.com/digitalsamba/claude-code-video-toolkit) | ערכת הפקה מבוססת Remotion | MIT (חל גם הרישיון של Remotion) | רינדור מקומי, כלי AI על מעבדים גרפיים בענן | לא מצוין | לא מצוין |
| Descript | עריכה מבוססת טקסט | מנוי | ענן | **לא** (רק שפות בכתב לטיני) | לא |
| OpusClip | סרטון ארוך לקליפים קצרים | מנוי | ענן | **לא** (לא תומך בשפות מימין לשמאל) | לא |
| Premiere Pro | עורך מקצועי | מנוי | מקומי ו-AI בענן | **אין** תמלול עברית | דווח על כתוביות SRT מתהפכות |
| DaVinci Resolve | עורך מקצועי | חינם / Studio | מקומי | **אין** תמלול עברית מובנה | RTL ידני, טקסט מעורב לא מטופל עד הסוף |
| CapCut / ‏Submagic / ‏VEED / ‏Kapwing | עורכים בדפדפן ובנייד | חינם עם תשלום | ענן | מוצהר | טיפול ב-RTL לא מתועד |
| HeyGen / ‏Synthesia | אווטארים ודיבוב | מנוי | ענן | הקראה ודיבוב בעברית | — |

## מה video-factory עושה שרוב האחרים לא עושים

1. **עברית מקצה לקצה, מקומית**: תמלול עברי ברמת מילה (ivrit.ai עם DTW), יחד עם כתוביות
   מימין לשמאל בסדר הנכון ו**קריוקי**. אף כלי מסחרי שנסקר לא מבטיח את שניהם יחד, וכלי הסוכנים
   לא מזכירים עברית בכלל.
2. **הסרת הברות היסוס ושתיקות בעברית**, עם כתוביות שמתוזמנות מחדש לפי החיתוך, הכול מקומית.
3. **גרפיקה מונפשת בעברית**: כותרות, כותרות תחתונות, מספרים שעולים, גרפים ושקופיות סיום,
   מימין לשמאל וממותגים מקובץ אחד.
4. **דף הערות ללקוח** עם הערות לפי זמן, שחוזרות לתוך העריכה. לאף כלי סוכן שנסקר אין דבר כזה.
5. **מסירה לעורך בשלושה פורמטים** (FCPXML, ‏EDL, ‏OTIO). ‏Kinocut מייצא EDL ו-OTIO, ואף כלי
   סוכן אחר שנסקר לא מייצא FCPXML.
6. **מונחה חומר ומונחה תסריט באותו פרויקט**: תדמית שבנויה על ראיונות וסרטון מוצר עם קריינות
   חולקים אותו תהליך, אותו מיתוג, אותה גרפיקה ואותה מסירה.
7. **סרטונים קצרים בעברית מסרטון ארוך**: רגעים מועמדים מתוך התמלול העברי, ש-Claude שופט, ומרונדרים
   אנכיים עם כתוביות מילה-אחר-מילה וכותרת וו. ‏OpusClip, המוביל בתחום, לא תומך בעברית.
8. **ציר זמן ויזואלי בלי תוכנת עריכה**: דף סטטי אחד עם הסרטון, כל המסלולים, גרירה לשינוי סדר,
   מעבר לכל חיבור, והערות.
9. **רישיון MIT פשוט**, לעומת AGPL (‏OpenMontage) או מגבלות לפי גודל חברה (‏Remotion).

## איפה הוא חלש יותר, ומי עושה את זה טוב יותר

| חסר | מי עושה את זה טוב יותר |
|---|---|
| אין ציר זמן גרפי או ממשק. העבודה היא בשיחה | ‏Descript, ‏CapCut, ‏Premiere, ‏Resolve (ייצוא FCPXML מצמצם את הפער) |
| דורש Claude Code והתקנה בשורת פקודה | כלים בדפדפן: Submagic, ‏VEED, ‏Kapwing |
| אין יצירת תמונות או וידאו ב-AI, ואין אווטארים או סנכרון שפתיים | ‏OpenMontage, ‏Runway, ‏HeyGen, ‏Synthesia |
| אין חיפוש בספריות סטוק | ‏OpenMontage (‏Pexels, ‏Archive.org, ‏NASA), ‏Pictory |
| אין אפקטי אור או מעברי תנופה בין כ-60 סוגי המעברים (לכל חיבור בנפרד מאז 2026-11) | ‏claude-code-video-toolkit |
| קריינות: הספקים בתשלום עוד לא נבדקו כאן, ואין הקראה עברית חינמית מקומית | ‏OpenMontage (‏Piper מקומי), ‏claude-code-video-toolkit (שיבוט קול) |
| בחירת "הרגעים הטובים" נעשית בשיקול של Claude, לא במודל ויראליות מאומן | ‏OpusClip, ‏Riverside Magic Clips (בלי עברית) |
| אין פרסום ישיר לרשתות | ‏video-editing-skill (‏WoopSocial) |

## רעיונות שכדאי לאמץ

1. **בדיקת איכות אוטומטית** אחרי כל רינדור (אורך, ערוצים, עוצמה, קיום כתוביות), כך שקובץ פגום
   לא ידווח כמוכן.
2. **מעברי shader** דרך הקטלוג של HyperFrames (אור, טשטוש זום, תנופה), בנוסף לכ-60 הסוגים לכל חיבור.
3. **אנרגיית שמע וצחוק** בדירוג הקליפים, לצד הסימנים מהתמלול.
4. **הקראה עברית חינמית ומקומית**, אם יופיע קול פתוח טוב, כך שגם הקריינות תישאר מקומית.
5. **חיפוש סטוק חינמי** (‏Pexels, ‏Wikimedia) להשלמת צילומי אווירה חסרים.
6. **מדד ביצועים ציבורי לעברית**: דיוק תמלול, ותמונות של קריוקי מעורב (עברית, אנגלית ומספרים).

## מקורות

</div>

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

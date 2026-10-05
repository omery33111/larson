import json

from analytics.formatting import trades as trade_count
from analytics.statistics import clean_label
from chat.context import CACHE, EFFORT, IRON, MAX_TOKENS, MODEL, build_messages, build_system

from .rules import declared_rules



# ------------------------- THE MENTOR'S CONTEXT START ------------------------- #
#
# Everything below the persona is identical to the general chat: the same resume, the same
# statistics document, the same message history. What changes is the job.
#
# The general chat answers questions. The mentor runs a debrief - the trader closes a session,
# hands over what just happened, and gets told how it differed from who he has been. That is
# why the deviation report is computed in Python and handed over finished: the whole value is
# in the comparison being true, and a comparison a model invented is worth nothing.

PERSONA = """אתה לארסון — המנטור האישי של הסוחר הזה. אתם מכירים: הרזומה שלו נמצאת מולך, ואתה
מלווה אותו לאורך זמן. **זו לא שיחת שאלות ותשובות — זה תחקיר.** הוא בדיוק סגר סשן או יום
מסחר, הביא לך את מה שקרה, ורוצה לדעת מה השתנה בו.

**מה אתה עושה עם עדכון — קיבלת שני דוחות, והם עונים על שאלות שונות:**

1. **`השוואה_לבייסליין` — דוח הסטיות.** מה השתנה בו מאז. זו סטטיסטיקה, ולכן היא דורשת מדגם
   ולפעמים תגיע ריקה. זה בסדר גמור.
2. **`בדיקת_הכללים` — האם הוא עמד בתוכנית.** לכל כלל שם יש **הוכחה מההיסטוריה שלו** שהוא
   עולה לו כסף, ולידה הפסיקה: אילו עסקאות מהעדכון הפרו אותו ואילו לא. **הבדיקה תקפה גם על
   עסקה אחת**, כי "האם העסקה הזו הוחזקה פחות משתי דקות" היא עובדה ולא סטטיסטיקה.

**כל מספר בשני הדוחות כבר חושב** — אתה מנסח, לא מחשב, ולא מוסיף נתון משלך.

**עדכון קטן — אפילו עסקה אחת — הוא עדיין עדכון.** סוחר יומי סוגר לפעמים סשן בעסקה אחת, וזה
לא פחות לגיטימי מיום של עשרים. **אסור לך לענות "אין לי מספיק כדי להגיד משהו" ולסיים שם.**
כשדוח הסטיות ריק, **בדיקת הכללים היא התשובה** — ויש בה מה לומר.

**איך אתה מדבר על בדיקת הכללים:**
- **כלל שנשמר — תפרגן, וקצר.** "לא נגעת בכניסות המהירות" זו לא מחמאה גנרית; זה בדיוק הדבר
  שאתה מודד אצלו. אבל אל תעשה מזה חגיגה על עסקה אחת — "עמדת בזה" מספיק.
- **כלל שנשבר — תגיד את זה ישר, ותצמיד לו את המחיר שההיסטוריה מראה.** אתה לא מנחש שזה יעלה
  לו; המספר בידיים שלך. אם זה הדפוס שכבר דיברתם עליו — תגיד שזה חוזר.
- **תמיד תגיד על כמה עסקאות בדקת.** "בדקתי את העסקה האחת ששלחת" זה ישר, וזה עדיף על להתחמק.
- **כלל שלא היה ניתן לבדיקה** (אין משך, אין תגית) פשוט לא מופיע בדוח — אל תמציא עליו מסקנה.

- **שתיים-שלוש נקודות, לא יותר, ו**דבר חיובי אחד** — בין אם הוא מגיע מהסטיות ובין אם הוא
  כלל שהסוחר שמר עליו. תחקיר שהוא רק רשימת כישלונות מפסיקים לקרוא אחרי פעמיים.
- **תגיד מה השתנה, ומיד תגיד למה זה משנה לו בכסף או בהתנהגות.** לא "הקצב עלה" אלא מה זה
  אומר עליו.
- **חבר את הסטייה לדפוס שאתה כבר מכיר אצלו** כשיש חיבור כזה בנתונים ("אצלך זה מופיע אחרי
  יום אדום"). זה ההבדל בין מנטור לבין דוח.
- **תמציתי. שלוש-ארבע פסקאות קצרות לכל היותר.** זו לא הרצאה.
- **סיים במשפט אחד** על הדבר שכדאי לו להסתכל עליו עד הפעם הבאה. משפט אחד, לא רשימה.

**כשאין דוח סטיות** — כי הוא רק כתב לך משהו, או כי אין מספיק נתונים להשוואה — תענה כמנטור
רגיל, קצר, מהרזומה שלו. אם חסרים נתונים כדי להשוות, תגיד את זה ישר ותגיד מה יפתח את זה.

**איך אתה כותב:**
- **המשפט הראשון עומד בפני עצמו** ואומר את הדבר עצמו. לא כותרת ולא הקדמה.
- עברית, גוף שני, שפה של סוחר. בלי "חשוב לציין", בלי לפתוח בסיכום השאלה.
- בלי כותרות ובלי תבליטים.
- אתה לא מציג את עצמך ולא חותם בשמך.

**הכלל שלא נשבר — אתה לא מחשב.** כל מספר מגיע מהנתונים כמו שהוא, עם היחידה שלו. מה שלא
נמצא שם — לא קיים, ואתה אומר את זה במקום לנחש.

**אסור לחלוטין:** להמליץ לקנות או למכור נכס ספציפי, לתת תחזית שוק, או לתת ייעוץ השקעות.""" + IRON


# The opening line of the relationship. It is the product's whole ask in one sentence, and it
# is written here rather than generated: it must be identical every time, and paying a model
# call to produce a fixed sentence would be paying for nothing.
GREETING = ("היי. איך עברה עליך התקופה האחרונה?\n\n"
            "שלח לי את העסקאות האחרונות שלך, ואני אגיד לך מה השתנה בך מאז — "
            "מה נשבר, ומה דווקא התהדק — בהשוואה למה שאני כבר מכיר עליך.")


# ------------- THE LINE THAT OPENS THE COMPARISON:
# Said the moment there is something to compare against, and written here rather than
# generated. It is a fixed sentence - paying a model call to produce it would be paying for
# nothing - and it is also the honest thing to say: the founding file is not a session to be
# debriefed, it is the baseline itself. What is owed next is the recent trades.
def baseline_set(total_trades):
    return (f"✔ נקלטו {trade_count(total_trades)}. זה הבסיס שלך — מעכשיו יש לי מול מה "
            "להשוות.\n\n" 
            "עכשיו שלח לי את העסקאות מהימים האחרונים, ואגיד לך מה השתנה בך מאז: "
            "מה נשבר, ומה דווקא התהדק.")


def mentor_system(user):
    """
    The mentor's system block - **and the rules he set for himself, always.**

    They used to travel only inside a debrief briefing, so on any other turn the model had
    never been told which rules exist. Asked "which of my rules would you drop", it invented
    one: a 16:00-18:00 window the trader had never set. **A model asked about a list it has
    not been shown will produce a plausible list**, and the trader has no way to tell that
    from a real answer.

    It belongs in the system block rather than the turn, and that is not an accident of
    convenience: his rules change about as often as his resume does, so they cache together
    with it. Attaching them per question would rewrite the cached prefix on every message.
    """
    blocks = build_system(user, persona = PERSONA)

    declared = declared_rules(user)

    if declared:
        listed = "\n".join("- " + rule["rule"] for rule in declared)

        block = ("**הכללים שהסוחר קבע לעצמו, כפי שהם רשומים אצלו:**\n"
                 f"{listed}\n\n"
                 "**אלה כל הכללים שלו. אם אין כאן כלל כלשהו — הוא לא קיים, "
                 "ואסור להתייחס אליו כאילו כן.**")
    else:
        block = ("**הסוחר לא קבע לעצמו אף כלל.** אם הוא שואל על הכללים שלו, זו התשובה — "
                 "**אל תמציא כללים שהוא לא קבע.**")

    # The marker moves to the last block, which is this one: anything cached has to be the
    # whole prefix, and leaving it on the resume would exclude the rules from the cache.
    for existing in blocks:
        existing.pop("cache_control", None)

    blocks.append({"type": "text", "text": block, "cache_control": CACHE})

    return blocks


def mentor_messages(conversation):
    return build_messages(conversation)


def receipt(trade_file):
    """
    The documentation line, written by the server and never by the model.

    It is the first thing the trader reads after handing over a file, and it is the promise
    that his data landed. A number the model produced here would be a number nobody checked.
    """
    line = f"✔ תועד ונשמר לרזומה: {trade_count(trade_file.imported_count)} חדשות"

    if trade_file.duplicate_count:
        line += f" ({trade_count(trade_file.duplicate_count)} כפולות דולגו)"

    return line + "\n\n"


FIRST_FILE_BRIEF = """**זה הקובץ הראשון שלו. אין מה להשוות ואין עדיין כללים — וזו לא סיבה
להתנצל, זו עבודה אחרת:**

- **תן לו קריאה ראשונה על מי הוא כסוחר** לפי מה שהרגע נכנס. הרזומה המלאה נמצאת מולך למעלה —
  תשתמש בה. זה הרגע הראשון שבו הוא קורא משהו נכון על עצמו, ואסור לבזבז אותו על "קיבלתי".
- **דבר אחד שעובד ודבר אחד שדולף**, שניהם עם המספר שמאחוריהם. לא יותר.
- **סיים בכך שמהעדכון הבא זה הופך להשוואה:** מכאן והלאה כל קובץ שישלח יימדד מול מה שהרגע
  נקבע כבסיס שלו. זו הסיבה שהוא יחזור.
- **אל תדבר על מה שחסר לך.** אין בייסליין כי עוד לא היה אחד — זה מובן מאליו ולא מעניין אותו."""


# What to do when the trader typed something alongside the file. It is deliberately narrow:
# the debrief still happens, and the persona above is not up for negotiation. What a trader
# may reasonably ask for here is a different manner - and refusing that silently is worse
# than honouring it, because he will simply ask again and get a different answer.
NOTE_BRIEF = """**הסוחר כתב לך משהו יחד עם הקובץ**, והוא בשדה `מה_שהסוחר_כתב_לך`. תתייחס
אליו בתוך התשובה. אם זו בקשה על **איך** לדבר איתו — כבד אותה. **התחקיר עצמו קורה בכל מקרה**,
וכללי הברזל שלמעלה לא זזים."""


# ------------- WHEN HE HAS RULES OF HIS OWN:
#
# The distinction is worth a paragraph of prompt because it changes what a breach means. An
# inferred rule is news - he may genuinely not have known the 14:00 hour was costing him. A
# declared one is not news: **he said it, and then he did the other thing**, and the only
# useful response to that is to say so plainly and ask what got in the way.
DECLARED_BRIEF = """**בתוך `בדיקת_הכללים`, כל שורה שנושאת `declared: true` היא כלל שהסוחר קבע
לעצמו** — לא דפוס שההיסטוריה שלו מרמזת עליו. ההבדל הזה חייב להישמע בתשובה:

- **כלל שהוא קבע ושבר** — זו לא הפתעה בשבילו, והוא לא צריך שתסביר לו למה הכלל קיים. תגיד
  בפשטות שהוא קבע את זה ולא עמד בו, עם העסקה בשמה, **ושאל מה קרה שם.** בלי הרצאה.
- **כלל שהוא קבע ושמר עליו** — זה הדבר הכי שווה ציון בכל התחקיר, גם ביום מפסיד. **הוא עשה
  בדיוק מה שהתחייב.** אמור זאת לפני כל השאר.
- **כלל שנגזר מההיסטוריה** — שם כן מקומו של ההסבר, כי ייתכן שהוא לא ידע.

**וכלל שהסוחר ניסח בעצמו — צטט אותו במילים שלו, בדיוק כפי שהוא מופיע.** אל תנסח אותו מחדש
ואל תסביר אותו לו: זה המשפט שהוא כתב, והוא יזהה אותו. ניסוח מחדש נקרא כאילו לא הבנת אותו.

**`checked` אומר על כמה עסקאות הכלל בכלל נבדק, והמספר הזה שווה אמירה כשהוא קטן.** כלל שנבדק
על שתיים מתוך עשרים עסקאות אינו "נשמר" — הוא לא נבדק. אם זה המצב, אמור את זה במשפט אחד:
שהעסקאות האחרות לא נשאו תגית או הערה, ולכן הן לא נספרו לכאן ולא לכאן."""


def _has_declared(plan):
    if not isinstance(plan, dict):
        return False
    return any(entry.get("declared")
               for side in ("broken", "kept")
               for entry in plan.get(side, []) or [])


# ------------------------- WHEN HE ASKS FOR A RULE ------------------------- #
#
# **The words and the button have to say the same thing.** He asked for a rule, Larson
# proposed one in prose about long-versus-short sizing, and no button appeared - because
# that is not a shape the checker can judge. From the outside that reads as broken, and it
# teaches him the suggestion is decorative.
#
# So when he asks, the server tells the model exactly what it is about to offer him, or
# that there is nothing to offer. The card is still composed in python and the model still
# writes nothing; this only stops the two from contradicting each other.

def suggestion_brief(card, standings = ()):
    """
    What to tell the model about the card it is about to be shown underneath.

    `standings` is how each of his rules is doing, and it is there for the case the first
    version got wrong: he asks which condition he would give up, Larson picks one, and no
    button appears because the engine's bar is higher than the model's opinion. **Both can
    be right and the user still reads it as broken** - so the model is handed the same
    figures and can say which one it would pick *and* why there is nothing to press.
    """
    if standings and not card:
        lines = "\n".join(
            f"- \"{row['הכלל']}\": נבדק על {row['נבדק_על']}, נשמר ב-{row['נשמר']}, נשבר ב-{row['נשבר']}"
            for row in standings)

        return f"""**הסוחר שאל על הכללים שלו, ואין כרגע כלל שעומד בסף להצעת הורדה.**

כך כל אחד מהם עומד בפועל:
{lines}

**מותר ומומלץ לענות על השאלה** — אם הוא שאל על איזה היה מוותר, תגיד איזה ולמה, עם המספרים.
**אבל אמור לו גם שאין כפתור, ולמה:** המערכת מציעה להוריד כלל רק כשהוא נשבר כמעט תמיד
(90% ומעלה) או כשהוא נשמר לגמרי לאורך זמן. **כלל שהוא שומר עליו בחלק מהמקרים הוא כלל שהוא
עובד עליו, ולהציע למחוק אותו זה להגיד לו להפסיק לנסות.**"""

    if card:
        return (f"**הסוחר ביקש כלל, ומתחת לתשובה שלך יופיע כפתור שמציע לו בדיוק את זה:**"
                + chr(10) + card["title"] + chr(10) + card["detail"] + chr(10) * 2
                + "**הצג את ההצעה הזו ולא אחרת, ואל תמציא כלל משלך במקומה.** "
                + "הסבר בקצרה למה היא שווה, ואמור לו שהכפתור מתחת מוסיף אותה.")

    return """**הסוחר ביקש כלל, ואין כרגע דפוס מפסיד שאפשר להפוך לכלל שנבדק אוטומטית.**

תגיד לו את זה ישירות, ותגיד למה — אם השעות שלו רווחיות, אם הסטאפים שלו רווחיים, אם אין
דליפה מובהקת. **זו בשורה טובה ולא חוסר.**

**ואל תמציא כלל במילים כאילו המערכת יכולה לאכוף אותו.** מה שהיא יודעת לבדוק הוא: שעת כניסה,
מספר חוזים, כניסה חוזרת אחרי הפסד, מספר עסקאות ביום, הפסד יומי, ותנאי חופשי שנבדק מול
**התגיות ושמות הסטאפים** שהוא רושם. אם יש לך רעיון שנשען על תגית שהוא כבר משתמש בה — הצע
לו לכתוב אותו בעצמו ב"הכללים שלי", וזה אפשרי. **אם הרעיון נשען על משהו שלא נרשם על העסקה,
אמור שזה לא ניתן לבדיקה אוטומטית עדיין.**"""


def update_prompt(deviation, plan, total_trades, new_trades, file_name, is_first = False,
                  note = ""):
    """
    The briefing for an update. Words and finished figures - nothing to compute.

    Two reports, and they answer different questions. The deviation is a statistic and needs
    a sample; the plan check is a fact about each trade and holds at any size. A session of
    one arrives with an empty deviation and a full plan check, and that is by design.

    `note` is whatever the trader typed in the same request as the file. It used to be
    discarded, because the briefing replaces the last user turn wholesale - so an instruction
    sent with a file vanished without a trace, and the same instruction sent on its own line
    worked. That inconsistency reads as the mentor ignoring him at random. Nothing is added
    to the prompt when he typed nothing, which is every debrief the current screen sends.
    """
    payload = {
        "מה_קרה": f"הסוחר העלה קובץ ({clean_label(file_name)}) ואישר את קליטתו לרזומה.",
        "עסקאות_בעדכון_הזה": new_trades,
        "עסקאות_ברזומה_אחרי_העדכון": total_trades,
        "השוואה_לבייסליין": deviation,
        "בדיקת_הכללים": plan,
    }

    # A first file founds the resume rather than reporting on a session, and the persona is
    # written around comparing and rule-checking - both of which are necessarily empty here.
    # Without being told, he answers by apologising for what he does not have instead of
    # saying the thing he does have: who this trader is.
    job = FIRST_FILE_BRIEF if is_first else (
        "**אל תחזור על שורת התיעוד** — היא כבר מוצגת מעל התשובה שלך. התחל ישר מהתחקיר.")

    # **A rule he wrote down and a rule his losses imply are not the same conversation**, and
    # the flag on the entry is the only thing that says which is which. Without this the model
    # reports both in the same voice - "you traded in the 14:00 hour again" alongside "you
    # entered before ten" - and the second one is the one he has standing to be held to.
    if _has_declared(plan):
        job += "\n\n" + DECLARED_BRIEF

    if note:
        payload["מה_שהסוחר_כתב_לך"] = note
        job += "\n\n" + NOTE_BRIEF

    return ("הסוחר בדיוק עדכן אותך. להלן שני דוחות מחושבים על מה שנכנס.\n\n"
            + job + "\n\n"
            + json.dumps(payload, ensure_ascii = False, indent = 1, default = str))

# ------------------------- THE MENTOR'S CONTEXT END ------------------------- #

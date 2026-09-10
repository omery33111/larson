import json

from django.conf import settings
from django.utils import timezone as django_timezone

from .formatting import money, percent, ratio
from .models import TraderProfile



# ------------------------- TRADER PROFILE START ------------------------- #
#
# The 300-500 token document that describes the trader's "self". It is the only part of
# milestone 3 that calls the model - every number it talks about was computed already and
# is handed over as JSON. The model writes; it never calculates.

MODEL = "claude-opus-5"

SYSTEM_PROMPT = """אתה לארסון — מנטור מסחר ותיק שישב מהצד וצפה בסוחר הזה עובד. עכשיו אתה אומר לו
את מה שראית. אתה לא מציג את עצמך ולא חותם בשמך; הוא כבר יודע מי אתה, והשם שלך מופיע מעל
הטקסט במסך.

**שתי מגבלות שקודמות לכל השאר:**
1. **בין 150 ל-200 מילים. לא יותר.** טקסט ארוך מזה לא נקרא, וכל מילה מעבר מחלישה את מה שלפניה.
2. **לכל היותר שני מספרים בכל הטקסט.** קיבלת רשימה קצרה של מספרים מותרים — בחר מתוכה שניים,
   ורק אם המספר עצמו הוא הפואנטה של המשפט. **אל תספור, אל תפרט ואל תדקלם נתונים.**
   כל הנתונים כבר פרושים לפניו בעמוד; אם תחזור עליהם, אין סיבה שיקרא הלאה.

איך אתה כותב:
- עברית, גוף שני, שפה של סוחר. בלי ז'רגון אקדמי ובלי מילים מנופחות.
- אל תמציא נתון. מה שלא קיבלת — לא קיים.
- בלי כותרות, בלי רשימות, בלי תבליטים. פסקאות רצופות בלבד.
- ארבע פסקאות, כל אחת מופרדת בשורה ריקה. הראשונות שלוש קצרות; האחרונה משפט אחד.

מה אתה אומר, בסדר הזה:

1. **הקריאה.** מי הסוחר הזה באמת — לא מה הוא עשה, אלא מה שאתה רואה מאחורי זה: דפוס, אופי,
   נטייה שחוזרת. משהו שהוא לא היה אומר על עצמו, ושכשיקרא אותו יעצור רגע ויבין שקלעת.

2. **הרגע שבו הוא היה גיבור.** דבר אחד ספציפי שהוא עשה טוב באמת. תן לו את מלוא הקרדיט,
   בלי הסתייגות ובלי "אבל" בסוף. אתה מפרגן כמו מי שלא מחלק מחמאות בחינם — ולכן זה נחשב.

3. **הדליפה שחוזרת.** הדבר שקורה לו שוב ושוב בלי שהוא שם לב. תגיד את זה ישר, בלי לרכך
   ובלי להתנצל. עוקצני זה טוב; משפיל זה לא. אתה בצד שלו — בדיוק בגלל זה אתה לא מייפה.

4. **ה"אני האמיתי".** משפט אחד שסוגר. לא סיכום של מה שכתבת, אלא אמירה שהוא ייקח איתו
   למסך מחר.

**אסור לחלוטין** להמליץ על קנייה או מכירה של נכס ספציפי, או לתת ייעוץ השקעות."""


def _top_group(groups, best = True):
    """The single strongest or weakest bucket, by name only."""
    significant = [g for g in groups if g.get("is_significant")]

    if not significant:
        return None

    pick = (max if best else min)(significant, key = lambda g: g["expectancy"])
    return g_label(pick)


def g_label(group):
    return group.get("label") or str(group["key"])


def build_profile_prompt(statistics, strengths, leaks):
    """
    A deliberately narrow briefing, not the full statistics document.

    The page already shows every number. Handing the model the whole table produced exactly
    what it looks like - a recital of figures the reader can see for themselves two inches
    lower. It cannot quote a number it was never given, so the shape of the trader is sent
    as words, and only a handful of figures come along, pre-formatted with their units.
    """
    core = statistics["core"]
    behaviour = statistics["behaviour"]
    breakdowns = statistics["breakdowns"]
    currency = statistics.get("currency", "USD")

    hold = behaviour.get("hold_time", {})
    awareness = behaviour.get("self_awareness", {})
    size = behaviour.get("size_discipline", {})

    payload = {
        "מי_הסוחר_הזה": {
            "מספר_עסקאות": statistics["total_trades"],
            "תקופה": f"{statistics['date_from']:%m/%Y} עד {statistics['date_to']:%m/%Y}",
            "נכסים": [g_label(g) for g in breakdowns["by_symbol"]][:4],
            "השעה_החזקה": _top_group(breakdowns["by_hour"], best = True),
            "השעה_החלשה": _top_group(breakdowns["by_hour"], best = False),
            "הסטאפ_שעובד": _top_group(breakdowns["by_setup"], best = True),
            "הסטאפ_שלא_עובד": _top_group(breakdowns["by_setup"], best = False),
            "משך_החזקה_שעובד": _top_group(breakdowns["by_duration"], best = True),
            "הכיוון_החזק": _top_group(breakdowns["by_direction"], best = True),
            "עסקאות_ליום_בממוצע": statistics["daily"]["avg_trades_per_day"],
        },

        # Titles only. The detail lines carry the arithmetic, and that is the page's job.
        "מה_עובד_אצלו": [f["title"] for f in strengths],
        "מה_דולף_אצלו": [f["title"] for f in leaks],

        "דפוסים_התנהגותיים": {
            "מחזיק_מפסידות_יותר_מרווחיות": hold.get("holds_losers_longer"),
            "הדירוג_העצמי_שלו_מנבא_תוצאה": awareness.get("is_calibrated"),
            "גודל_פוזיציה_יציב": size.get("is_consistent"),
            "רצף_ההפסדים_הארוך_ביותר": statistics["streaks"]["longest_loss_streak"],
        },

        # The only figures in the whole briefing, already carrying their units.
        "מספרים_שמותר_לצטט_לכל_היותר_שניים": {
            "אחוזי_הצלחה": percent(core["win_rate"]),
            "יחס_רווח_להפסד": ratio(core["win_loss_ratio"]),
            "רווח_נקי": money(core["net_pnl"], currency),
            "ציון": f"{statistics['score']['total']} מתוך 100 ({statistics['score']['grade']})",
            "העמוד_החלש_בציון": min(statistics["score"]["pillars"], key = lambda p: p["value"])["label"],
        },
    }

    return ("להלן תדריך על הסוחר. הוא מכיל מילים ולא טבלאות, בכוונה — "
            "כל המספרים כבר מוצגים לו בעמוד.\n\n"
            + json.dumps(payload, ensure_ascii = False, indent = 2, default = str))



def generate_profile(user, statistics, strengths, leaks, accounts = None):
    """
    Calls the model and stores the result.
    Raises RuntimeError with a message meant for the user when it cannot run.
    """
    api_key = settings.ANTHROPIC_API_KEY

    if not api_key:
        raise RuntimeError(
            "לא הוגדר מפתח API של Claude. אם כבר הוספת ANTHROPIC_API_KEY לקובץ back-end/.env, "
            "השרת עדיין רץ עם הערך הישן — עצור אותו לגמרי והפעל מחדש. "
            "ודא גם שאין עוד מופע של runserver שתפס את פורט 8000.")

    try:
        import anthropic
    except ImportError:
        raise RuntimeError("חבילת anthropic אינה מותקנת. הרץ: pip install anthropic")

    client = anthropic.Anthropic(api_key = api_key)

    # The same meter the chat and the mentor answer to. Generating a profile is the single
    # most expensive call in the product - it reads the whole history - so it is the last
    # place that should be exempt from it.
    from usage import budget

    if not budget.has_room(user):
        raise RuntimeError(budget.exhausted_message(user))

    try:
        # Streaming keeps a long generation from hitting the HTTP timeout.
        with client.messages.stream(
            model = MODEL,
            max_tokens = 4000,
            system = SYSTEM_PROMPT,
            messages = [{"role": "user", "content": build_profile_prompt(statistics, strengths, leaks)}],
        ) as stream:
            message = stream.get_final_message()
    except Exception as e:
        raise RuntimeError(f"הקריאה ל-Claude נכשלה: {e}")

    if getattr(message, "usage", None):
        budget.record(user, "profile", message.usage)

    # A safety classifier can decline with HTTP 200 and no usable content.
    if message.stop_reason == "refusal":
        raise RuntimeError("המודל סירב לייצר את הפרופיל. נסה שוב מאוחר יותר.")

    text = "".join(block.text for block in message.content if block.type == "text").strip()

    if not text:
        raise RuntimeError("המודל החזיר תשובה ריקה.")

    profile, _ = TraderProfile.objects.update_or_create(
        user = user,
        defaults = {
            "profile_text": text,
            "accounts": ",".join(accounts or []),
            "trades_at_generation": statistics["total_trades"],
            "score_at_generation": statistics["score"]["total"],
            "generated_at": django_timezone.now(),
        },
    )

    return profile

# ------------------------- TRADER PROFILE END ------------------------- #

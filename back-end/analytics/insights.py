from .evidence import attach_examples
from .formatting import days, minutes, money, percent, points, ratio, trades as trade_count
from .statistics import MIN_TRADES_FOR_BREAKDOWN



# ------------------------- ANGEL AND DEVIL START ------------------------- #
#
# The two shoulders. One side is what must not be touched, the other is what is bleeding.
#
# Every finding here is derived arithmetically from the statistics document - never written
# by the model. A mentor that invents a number it cannot show is worse than no mentor, and
# these lines are the ones the trader will act on.
#
# Each finding carries: title, detail, impact (money), and evidence (how many trades), so
# nothing appears on screen without the sample size behind it.


MAX_FINDINGS_PER_SIDE = 4



def build_insights(statistics, trades = None):
    """
    Returns (strengths, leaks), each ranked by how much money is attached.

    **`trades` is optional and what it buys is the pointing.** Given the rows, every finding
    that survives the ranking also carries three of its own instances by name - which is the
    difference between "revenge trading cost you $1,840" and "here, this one". Callers that
    only need the sentences may leave it out and nothing else changes.

    It is attached **after** the ranking on purpose: only the findings that reach the screen
    are worth selecting examples for, and the selectors walk the whole history.
    """
    if not statistics.get("total_trades"):
        return [], []

    currency = statistics.get("currency", "USD")
    zone = statistics.get("timezone", "Asia/Jerusalem")

    strengths = _collect_strengths(statistics, currency)
    leaks = _collect_leaks(statistics, currency)

    strengths.sort(key = lambda f: -abs(f["impact"]))
    leaks.sort(key = lambda f: -abs(f["impact"]))

    strengths = strengths[:MAX_FINDINGS_PER_SIDE]
    leaks = leaks[:MAX_FINDINGS_PER_SIDE]

    if trades:
        attach_examples(strengths, trades, currency, zone, worst_first = False)
        attach_examples(leaks, trades, currency, zone, worst_first = True)

    return strengths, leaks



# ------------- THE ANGEL: what is working, and must not be changed
def _collect_strengths(statistics, currency):
    core = statistics["core"]
    daily = statistics["daily"]
    behaviour = statistics["behaviour"]
    breakdowns = statistics["breakdowns"]

    findings = []

    best_setup = _best_group(breakdowns["by_setup"])
    if best_setup:
        findings.append({
            "key": "best_setup",
            "subject": best_setup["key"],
            "title": f"הסטאפ החזק שלך: {best_setup['key']}",
            "detail": f"תוחלת {money(best_setup['expectancy'], currency)} לעסקה, "
                      f"עם {percent(best_setup['win_rate'])} הצלחה. זה הבסיס שלך — אל תתעסק בו.",
            "impact": best_setup["net_pnl"],
            "evidence": trade_count(best_setup["trades"]),
        })

    best_hour = _best_group(breakdowns["by_hour"])
    if best_hour:
        findings.append({
            "key": "best_hour",
            "subject": best_hour["key"],
            "title": f"השעה החזקה שלך: {int(best_hour['key']):02d}:00",
            "detail": f"תוחלת {money(best_hour['expectancy'], currency)} לעסקה בשעה הזו. "
                      f"אם יש לך זמן מוגבל למסך — זה החלון.",
            "impact": best_hour["net_pnl"],
            "evidence": trade_count(best_hour["trades"]),
        })

    best_symbol = _best_group(breakdowns["by_symbol"])
    if best_symbol and len(breakdowns["by_symbol"]) > 1:
        findings.append({
            "key": "best_symbol",
            "subject": best_symbol["key"],
            "title": f"הנכס החזק שלך: {best_symbol.get('label') or best_symbol['key']}",
            "detail": f"תוחלת {money(best_symbol['expectancy'], currency)} לעסקה, "
                      f"מול הנכסים האחרים שלך.",
            "impact": best_symbol["net_pnl"],
            "evidence": trade_count(best_symbol["trades"]),
        })

    best_direction = _best_group(breakdowns["by_direction"])
    if best_direction and len(breakdowns["by_direction"]) > 1 and best_direction["key"] != "unknown":
        label = "לונג" if best_direction["key"] == "long" else "שורט"
        findings.append({
            "key": "best_direction",
            "subject": best_direction["key"],
            "title": f"אתה חד יותר ב{label}",
            "detail": f"תוחלת {money(best_direction['expectancy'], currency)} לעסקה ב{label}, "
                      f"עם {percent(best_direction['win_rate'])} הצלחה.",
            "impact": best_direction["net_pnl"],
            "evidence": trade_count(best_direction["trades"]),
        })

    payoff_ratio = core["win_loss_ratio"]
    if payoff_ratio and payoff_ratio >= 1.8:
        findings.append({
            "key": "payoff",
            "title": "הרווח הממוצע שלך גדול משמעותית מההפסד",
            "detail": f"רווח ממוצע {money(core['avg_win'], currency)} מול הפסד ממוצע "
                      f"{money(core['avg_loss'], currency)} — יחס {ratio(payoff_ratio)} לטובתך. "
                      f"זה מה שמאפשר לך להיות רווחי גם בלי אחוזי הצלחה גבוהים.",
            "impact": core["gross_profit"],
            "evidence": f"{core['wins']} רווחים מול {core['losses']} הפסדים",
        })

    size = behaviour["size_discipline"]
    if size.get("available") and size["is_consistent"]:
        findings.append({
            "key": "size_discipline",
            "title": "גודל הפוזיציה שלך יציב",
            "detail": f"סטייה של {ratio(size['size_variation'])} סביב ממוצע של "
                      f"{ratio(size['avg_size'])} חוזים. "
                      f"סיכון קבוע הוא מה שמונע מיום אחד למחוק חודש.",
            "impact": abs(core["expectancy"]) * statistics["total_trades"] * 0.1,
            "evidence": trade_count(statistics["total_trades"]),
        })

    awareness = behaviour["self_awareness"]
    if awareness.get("available") and awareness["is_calibrated"]:
        findings.append({
            "key": "self_awareness",
            "title": "אתה יודע לזהות עסקה טובה בזמן אמת",
            "detail": f"העסקאות שדירגת גבוה הניבו {money(awareness['high_rated_expectancy'], currency)} "
                      f"לעסקה, מול {money(awareness['low_rated_expectancy'], currency)} בנמוכות. "
                      f"הקריאה שלך על עצמך מכוילת.",
            "impact": abs(awareness["gap"]) * awareness["rated_trades"] / 2,
            "evidence": f"{trade_count(awareness['rated_trades'])} מדורגות",
        })

    hold = behaviour["hold_time"]
    if hold.get("available") and not hold["holds_losers_longer"]:
        findings.append({
            "key": "hold_time",
            "title": "אתה חותך הפסדים מהר יותר מרווחים",
            "detail": f"החזקה ממוצעת של {minutes(hold['avg_win_minutes'])} ברווח "
                      f"מול {minutes(hold['avg_loss_minutes'])} בהפסד. זה הכיוון הנכון.",
            "impact": core["gross_profit"] * 0.15,
            "evidence": trade_count(core["wins"] + core["losses"]),
        })

    if daily["green_day_rate"] >= 55:
        findings.append({
            "key": "green_days",
            "title": "רוב ימי המסחר שלך ירוקים",
            "detail": f"{percent(daily['green_day_rate'])} מהימים שהוכרעו נסגרו ברווח "
                      f"({daily['green_days']} ירוקים מול {daily['red_days']} אדומים).",
            "impact": daily["avg_green_day"] * daily["green_days"],
            "evidence": f"{days(daily['trading_days'])} מסחר",
        })

    return findings



# ------------- THE DEVIL: what is bleeding, ranked by cost
def _collect_leaks(statistics, currency):
    core = statistics["core"]
    daily = statistics["daily"]
    streaks = statistics["streaks"]
    behaviour = statistics["behaviour"]
    breakdowns = statistics["breakdowns"]

    findings = []

    revenge = behaviour["revenge"]
    if _is_leak(revenge):
        findings.append({
            "key": "revenge",
            "title": "עסקאות נקמה",
            "detail": f"עסקה שנפתחה מיד אחרי הפסד מניבה אצלך {money(revenge['expectancy'], currency)} "
                      f"לעסקה, מול {money(revenge['rest_expectancy'], currency)} בשאר. "
                      f"סה\"כ {money(revenge['total_pnl'], currency)}.",
            "impact": revenge["total_pnl"],
            "evidence": trade_count(revenge["count"]),
        })

    mistakes = behaviour["mistake_tax"]
    if _is_leak(mistakes):
        findings.append({
            "key": "mistake_tax",
            "title": "מס הטעויות",
            "detail": f"העסקאות שסימנת בעצמך כטעות עלו לך {money(mistakes['total_cost'], currency)}. "
                      f"אתה מזהה אותן — הפער הוא בין הזיהוי להימנעות.",
            "impact": mistakes["total_cost"],
            "evidence": f"{trade_count(mistakes['coverage'])} מסומנות",
        })

    worst_mistake = _worst_group(breakdowns["by_mistake"])
    if worst_mistake:
        findings.append({
            "key": "worst_mistake",
            "subject": worst_mistake["key"],
            "title": f"הטעות היקרה ביותר: {worst_mistake['key']}",
            "detail": f"תוחלת {money(worst_mistake['expectancy'], currency)} לעסקה כשהיא מופיעה, "
                      f"סה\"כ {money(worst_mistake['net_pnl'], currency)}.",
            "impact": worst_mistake["net_pnl"],
            "evidence": trade_count(worst_mistake["trades"]),
        })

    overtrading = behaviour["overtrading"]
    if _is_leak(overtrading):
        findings.append({
            "key": "overtrading",
            "title": "יתר מסחר",
            "detail": f"בימים עם יותר מ-{overtrading['threshold']} עסקאות התוחלת שלך "
                      f"{money(overtrading['expectancy'], currency)} לעסקה, מול "
                      f"{money(overtrading['rest_expectancy'], currency)} בימים רגילים.",
            "impact": overtrading["total_pnl"],
            "evidence": trade_count(overtrading["count"]),
        })

    after_red = behaviour["after_red_day"]
    if _is_leak(after_red):
        detail = (f"ביום שאחרי יום הפסד התוחלת שלך {money(after_red['expectancy'], currency)} לעסקה, "
                  f"מול {money(after_red['rest_expectancy'], currency)} אחרי יום ירוק.")
        if after_red.get("avg_size_after_red") and after_red.get("avg_size_after_green"):
            if after_red["avg_size_after_red"] > after_red["avg_size_after_green"]:
                detail += (f" ואתה גם מגדיל: {ratio(after_red['avg_size_after_red'])} חוזים בממוצע "
                           f"מול {ratio(after_red['avg_size_after_green'])}.")
        findings.append({
            "key": "after_red_day",
            "title": "היום שאחרי יום אדום",
            "detail": detail,
            "impact": after_red["total_pnl"],
            "evidence": trade_count(after_red["count"]),
        })

    hold = behaviour["hold_time"]
    if hold.get("available") and hold["holds_losers_longer"]:
        findings.append({
            "key": "hold_time",
            "title": "אתה מחזיק מפסידות יותר מרווחיות",
            "detail": f"החזקה ממוצעת של {minutes(hold['avg_loss_minutes'])} בהפסד "
                      f"מול {minutes(hold['avg_win_minutes'])} ברווח. "
                      f"זו הדליפה היקרה ביותר במסחר.",
            "impact": -abs(core["gross_loss"] * 0.2),
            "evidence": trade_count(core["wins"] + core["losses"]),
        })

    worst_hour = _worst_group(breakdowns["by_hour"])
    if worst_hour:
        findings.append({
            "key": "worst_hour",
            "subject": worst_hour["key"],
            "title": f"השעה שעולה לך הכי הרבה: {int(worst_hour['key']):02d}:00",
            "detail": f"תוחלת {money(worst_hour['expectancy'], currency)} לעסקה בשעה הזו, "
                      f"סה\"כ {money(worst_hour['net_pnl'], currency)}.",
            "impact": worst_hour["net_pnl"],
            "evidence": trade_count(worst_hour["trades"]),
        })

    worst_setup = _worst_group(breakdowns["by_setup"])
    if worst_setup:
        findings.append({
            "key": "worst_setup",
            "subject": worst_setup["key"],
            "title": f"הסטאפ המפסיד שלך: {worst_setup['key']}",
            "detail": f"תוחלת {money(worst_setup['expectancy'], currency)} לעסקה, "
                      f"סה\"כ {money(worst_setup['net_pnl'], currency)}. "
                      f"שווה לבדוק אם הוא שייך לתוכנית בכלל.",
            "impact": worst_setup["net_pnl"],
            "evidence": trade_count(worst_setup["trades"]),
        })

    size = behaviour["size_discipline"]
    # Variable size is only a leak when the oversized trades actually lose. A trader who
    # sizes up on their best reads is not undisciplined - they are selective, and calling
    # that a leak would push them away from the thing that works.
    if (size.get("available") and not size["is_consistent"]
            and size["biggest_size_expectancy"] < 0):
        findings.append({
            "key": "size_discipline",
            "title": "אתה מגדיל פוזיציה בדיוק במקום הלא נכון",
            "detail": f"סטייה של {ratio(size['size_variation'])} סביב ממוצע "
                      f"{ratio(size['avg_size'])} חוזים, עד {ratio(size['max_size'])}. "
                      f"בעסקאות הגדולות ביותר התוחלת שלך "
                      f"{money(size['biggest_size_expectancy'], currency)} — ההגדלה עולה לך כסף.",
            "impact": size["biggest_size_expectancy"] * 10,
            "evidence": trade_count(statistics["total_trades"]),
        })

    awareness = behaviour["self_awareness"]
    if awareness.get("available") and not awareness["is_calibrated"]:
        findings.append({
            "key": "self_awareness",
            "title": "הדירוג שלך לא מנבא את התוצאה",
            "detail": f"העסקאות שדירגת גבוה הניבו {money(awareness['high_rated_expectancy'], currency)} "
                      f"לעסקה, מול {money(awareness['low_rated_expectancy'], currency)} בנמוכות. "
                      f"מה שמרגיש לך כמו עסקה טובה אינו מה שעובד בפועל.",
            "impact": -abs(awareness["gap"]) * awareness["rated_trades"] / 2,
            "evidence": f"{trade_count(awareness['rated_trades'])} מדורגות",
        })

    if streaks["longest_loss_streak"] >= 5:
        findings.append({
            "key": "loss_streak",
            "title": f"רצף של {streaks['longest_loss_streak']} הפסדים ברצף",
            "detail": "רצף באורך כזה בלי עצירה מצביע על היעדר מפסק — כלל שמוציא אותך מהמסך "
                      "אחרי מספר הפסדים קבוע.",
            "impact": -abs(core["avg_loss"] * streaks["longest_loss_streak"]),
            "evidence": f"מתוך {trade_count(statistics['total_trades'])}",
        })

    reference = max(core["gross_profit"], abs(core["net_pnl"]), 1)
    if abs(daily["worst_day"]) / reference > 0.35:
        findings.append({
            "key": "worst_day",
            "title": "יום בודד מוחק חלק גדול מהרווח",
            "detail": f"היום הגרוע שלך היה {money(daily['worst_day'], currency)} — "
                      f"נתח משמעותי מכל מה שהרווחת. מגבלת הפסד יומית הייתה חוסמת את זה.",
            "impact": daily["worst_day"],
            "evidence": f"{days(daily['trading_days'])} מסחר",
        })

    return findings



# ------------- SELECTION HELPERS:
def _best_group(groups):
    """Best expectancy among groups that clear the sample-size floor and are profitable."""
    candidates = [g for g in groups if g["is_significant"] and g["expectancy"] > 0]
    return max(candidates, key = lambda g: g["expectancy"]) if candidates else None


def _worst_group(groups):
    candidates = [g for g in groups if g["is_significant"] and g["expectancy"] < 0]
    return min(candidates, key = lambda g: g["expectancy"]) if candidates else None


def _is_leak(comparison):
    return (comparison.get("available")
            and comparison.get("is_significant")
            and comparison.get("is_worse"))

# ------------------------- ANGEL AND DEVIL END ------------------------- #

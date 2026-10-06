from analytics.formatting import minutes, money, ratio, trades as trade_count
from analytics.statistics import _split_tags, clean_label

from .interpret import interpret, vocabulary
from .models import TraderRule



# ------------------------- DECLARED RULES, AS THE CHECKER SEES THEM ------------------------- #
#
# **A declared rule is translated into exactly the shape an inferred one has**, so it flows
# through `check_plan` unchanged: same keys, same judging loop, same named offender.
#
# The one key that is added is `declared`, and it carries the whole difference in tone.
# Breaking a rule the record argues for is news - he may not have known. **Breaking one he
# wrote down himself is not news, it is the conversation**, and the mentor has to be able to
# tell the two apart without being told which is which.
#
# `why` is written here rather than at the point of judging because an inferred rule answers
# "says who" with a number out of the history, and a declared one answers it with **"you
# did"** - which is the stronger answer of the two and should read that way.


def clock(minutes):
    """**Minutes from midnight to a wall clock.** They were whole hours until a trader
    pointed out that "I do not enter before 09:30" is a rule people actually have."""
    total = int(minutes)
    return f"{total // 60:02d}:{total % 60:02d}"


def declared_rules(user, currency = "USD"):
    """Every active commitment, in the checker's shape. Empty when he has set none."""
    rows = TraderRule.objects.filter(user = user, is_active = True)

    return [translated for translated in (_translate(row, currency) for row in rows) if translated]


def _translate(row, currency):
    kind = row.kind
    number = row.number

    mine = "כלל שקבעת לעצמך"

    # ------------- HIS OWN WORDS:
    #
    # **The rule the checker judges is the terms; the rule the trader reads is his sentence.**
    # Both travel, and they are not the same string on purpose - quoting the interpretation
    # back at him would show him our paraphrase of his plan instead of his plan.
    if kind == TraderRule.CUSTOM:
        terms = row.terms

        # A row that was saved before its sentence could be interpreted is not a rule. It
        # must not become one that every trade keeps.
        if not isinstance(terms, dict) or not (terms.get("require") or terms.get("forbid")):
            return None

        sentence = clean_label(row.text, 200)

        if not sentence:
            return None

        return _rule(kind, sentence, mine, terms)

    # A rule without its threshold cannot be judged, and a half-saved row must not become a
    # rule that silently never fires.
    if number is None:
        return None

    if kind in (TraderRule.NO_BEFORE, TraderRule.NO_AFTER):
        word = "לפני" if kind == TraderRule.NO_BEFORE else "אחרי"
        return _rule(kind, f"לא להיכנס {word} {clock(number)}", mine, number)

    if kind == TraderRule.MAX_SIZE:
        return _rule(kind, f"לא לעלות מעל {ratio(number)} חוזים", mine, number)

    if kind == TraderRule.NO_REVENGE_WITHIN:
        return _rule(kind, f"לא להיכנס תוך {minutes(number)} מסגירת הפסד", mine, number)

    if kind == TraderRule.MAX_TRADES_PER_DAY:
        return _rule(kind, f"לא יותר מ-{trade_count(int(number))} ביום", mine, number)

    if kind == TraderRule.MAX_DAILY_LOSS:
        return _rule(kind, f"לא לעבור הפסד יומי של {money(abs(number), currency)}",
                     mine, abs(number))

    return None


def _rule(kind, text, why, value):
    return {
        # Namespaced so a declared rule can never collide with an inferred one of the same
        # family - both can be live at once, and they say different things.
        "key": f"declared:{kind}",
        "rule": text,
        "why": why,
        # Declared rules sort above inferred ones by construction: what he committed to is
        # the first thing a debrief should answer, before anything his history merely implies.
        "weight": float("inf"),
        "kind": kind,
        "value": value,
        "declared": True,
    }



# ------------- THE TWO THAT ARE ABOUT A DAY AND NOT A TRADE:
#
# A trade cannot answer "did you take more than four today" on its own, so these are judged
# over the day's rows instead of inside the per-trade loop. **They are also the two rules a
# trader most often means by "I have rules"** - a trade cap and a daily stop - which is why
# they are here rather than left out for being awkward to fit.
DAY_KINDS = {TraderRule.MAX_TRADES_PER_DAY, TraderRule.MAX_DAILY_LOSS}


def day_verdict(rule, day_rows):
    """Whether one day broke one day-level rule, and which trade crossed the line."""
    rows = sorted(day_rows, key = lambda t: t.executed_at)

    if rule["kind"] == TraderRule.MAX_TRADES_PER_DAY:
        limit = int(rule["value"])
        if len(rows) <= limit:
            return False, None
        # The one that crossed it, not the worst one: this rule is about the count, and the
        # trade worth naming is the one that should not have been taken.
        return True, rows[limit]

    if rule["kind"] == TraderRule.MAX_DAILY_LOSS:
        limit = abs(rule["value"])
        running = 0.0
        for trade in rows:
            if trade.pnl is None:
                continue
            running += trade.pnl
            if running <= -limit:
                return True, trade
        return False, None

    return None, None



# ------------------------- TWO RULES THAT CANNOT BOTH HOLD ------------------------- #

def conflicts_with(user, kind, terms = None, number = None, ignore_id = None):
    """
    The rule he already has that this one would contradict, as a sentence, or `None`.

    **Caught when he writes it rather than reported afterwards.** A pair that cannot both
    be satisfied makes one of them break on every single trade, and the debrief would
    dutifully report that forever without ever saying the two are arguing.

    **Exact terms only, never substrings**, and that restraint is the whole correctness of
    it: requiring `ifvg` while forbidding `1m ifvg` is perfectly coherent - take any IFVG
    except the one-minute one - and a substring match would call it impossible. The cost of
    a false alarm here is that he stops believing the next one.
    """
    rows = TraderRule.objects.filter(user = user, is_active = True)

    if ignore_id:
        rows = rows.exclude(id = ignore_id)

    if kind == TraderRule.CUSTOM:
        terms = terms or {}
        mine_required = {t for group in terms.get("require", []) for t in group}
        mine_forbidden = set(terms.get("forbid", []))

        # **Against itself first**, which the first version never did: it compared the new
        # rule to the others and walked straight past a rule that bans what it demands.
        against_itself = mine_required & mine_forbidden

        if against_itself:
            return None, sorted(against_itself)[0]

        for row in rows.filter(kind = TraderRule.CUSTOM):
            theirs = row.terms if isinstance(row.terms, dict) else {}
            required = {t for group in theirs.get("require", []) for t in group}
            forbidden = set(theirs.get("forbid", []))

            clash = (mine_required & forbidden) | (mine_forbidden & required)

            if clash:
                return row, sorted(clash)[0]

        return None

    # ------------- AND THE ONE PAIR OF STRUCTURED RULES THAT CAN FIGHT:
    #
    # "Not before 14:00" with "not after 10:00" leaves no hour he may trade at all. Nothing
    # else here can contradict anything: there is one rule of each kind, and a size cap and
    # a daily stop are about different things.
    if kind in (TraderRule.NO_BEFORE, TraderRule.NO_AFTER) and number is not None:
        other = (TraderRule.NO_AFTER if kind == TraderRule.NO_BEFORE
                 else TraderRule.NO_BEFORE)
        row = rows.filter(kind = other).first()

        if row and row.number is not None:
            opens = number if kind == TraderRule.NO_BEFORE else row.number
            closes = row.number if kind == TraderRule.NO_BEFORE else number

            if opens >= closes:
                return row, clock(closes)

    return None


# ------------------------- RELEARNING, WHEN HIS WORDS CHANGE ------------------------- #

def refresh(user):
    """
    Re-read every free-text rule whose vocabulary has grown since it was interpreted.

    **This closes the one gap that fails silently.** A rule interpreted in June against the
    labels he used in June does not know about the word he started tagging with in August -
    so it keeps reporting, keeps sounding certain, and quietly stops seeing the thing it was
    written about. Nothing on any screen would say so.

    **Run on confirm and not inside the debrief**, deliberately. New labels only ever arrive
    with new trades, so this is the moment they appear; and the debrief is a streaming
    response the trader is watching, which is the wrong place to put a model call that is
    not about his question.

    Cheap by construction: it fires only when there are labels the rule has never seen, so a
    trader whose tagging is stable never pays for it at all.
    """
    rows = list(TraderRule.objects.filter(user = user, kind = TraderRule.CUSTOM,
                                          is_active = True))
    if not rows:
        return 0

    current = vocabulary(user)
    if not current:
        return 0

    relearned = 0

    for row in rows:
        seen = set(row.known_labels or [])

        if not set(current) - seen:
            continue

        terms = interpret(row.text, billed_to = user, known_labels = current)

        # **A failed re-read leaves the rule exactly as it was.** A rule that works against
        # last month's words is worth more than no rule, and a transient API error must
        # never be able to erase a commitment he made.
        if terms:
            row.terms = terms

        row.known_labels = current
        row.save(update_fields = ["terms", "known_labels"])
        relearned += 1

    return relearned

# ------------------------- END ------------------------- #

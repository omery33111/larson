from django.db import migrations


def untangle(apps, schema_editor):
    """
    Rules already saved that demand a term and ban the same term.

    **Written by a reading of his sentence, not by him.** Asked for "only IFVG and nothing
    else", the model returned `ifvg` as required and the IFVG spellings as forbidden - the
    second list swallowing the first. The conflict check compared a new rule against the
    *other* rules and never against itself, so it went straight through.

    **A rule no trade can satisfy breaks on every trade, forever**, and the debrief reports
    it every single time without once saying the rule is arguing with itself. Rows written
    before the fix cannot repair themselves, so they are repaired here.

    The required side wins, exactly as it now does at the boundary: he asked for something,
    and the ban on it is the misreading. A narrower term - `1m ifvg` beside a required
    `ifvg` - is a coherent plan and is left alone.
    """
    TraderRule = apps.get_model("mentor", "TraderRule")

    for row in TraderRule.objects.filter(kind = "custom"):
        terms = row.terms if isinstance(row.terms, dict) else {}

        required = {term for group in terms.get("require", []) or [] for term in group}
        forbidden = terms.get("forbid", []) or []

        kept = [term for term in forbidden if term not in required]

        if len(kept) != len(forbidden):
            terms["forbid"] = kept
            row.terms = terms
            row.save(update_fields = ["terms"])


class Migration(migrations.Migration):

    dependencies = [("mentor", "0005_larson_suggestions")]

    # Nothing to undo: the removed terms made the rule impossible to satisfy, and putting
    # them back would restore a rule that breaks on every trade.
    operations = [migrations.RunPython(untangle, migrations.RunPython.noop)]

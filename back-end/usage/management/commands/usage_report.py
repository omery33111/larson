"""
What the beta actually cost, per trader and in total.

    python manage.py usage_report                 # the last 30 days
    python manage.py usage_report --days 7
    python manage.py usage_report --since 2026-09-01

**This exists so the limits can be set from evidence instead of from my arithmetic.** The
defaults in settings were derived from one measured prompt on one synthetic resume; a month
of ten people using the product for real is a better number than that, and this is what turns
the rows in the ledger into it.

What it prints, and why each column is there:

  answers      how often the trader actually came back - the engagement figure
  in / out     the tokens themselves, since the two are priced very differently
  cost         the money, from the prices in settings
  peak day     the busiest single day, which is what a daily budget has to clear
  % of budget  whether the cap was anywhere near binding, which is the whole question
"""

from datetime import datetime, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Count, Sum
from django.utils import timezone

from usage.budget import units
from usage.models import TokenSpend



class Command(BaseCommand):
    help = "What the model has cost, per trader and in total."

    def add_arguments(self, parser):
        parser.add_argument("--days", type = int, default = 30)
        parser.add_argument("--since", type = str, default = None,
                            help = "YYYY-MM-DD, instead of --days")

    def handle(self, *args, **options):
        if options["since"]:
            start = timezone.make_aware(datetime.strptime(options["since"], "%Y-%m-%d"))
            label = f"since {options['since']}"
        else:
            start = timezone.now() - timedelta(days = options["days"])
            label = f"the last {options['days']} days"

        rows = TokenSpend.objects.filter(created_at__gte = start)

        if not rows.exists():
            self.stdout.write(f"Nothing recorded in {label}.")
            return

        in_price = settings.AI_INPUT_PRICE / 1_000_000
        out_price = settings.AI_OUTPUT_PRICE / 1_000_000

        from usage.budget import CACHE_READ_WEIGHT, CACHE_WRITE_WEIGHT

        def money(input_tokens, output_tokens, write = 0, read = 0):
            return (input_tokens * in_price
                    + write * in_price * CACHE_WRITE_WEIGHT
                    + read * in_price * CACHE_READ_WEIGHT
                    + output_tokens * out_price)

        # ------------- per trader
        people = (rows.values("user__username")
                      .annotate(answers = Count("id"),
                                inp = Sum("input_tokens"),
                                out = Sum("output_tokens"),
                                wrote = Sum("cache_write_tokens"),
                                read = Sum("cache_read_tokens"))
                      .order_by("-answers"))

        self.stdout.write("")
        self.stdout.write(f"USAGE — {label}")
        self.stdout.write("=" * 78)
        self.stdout.write(f"{'trader':<18}{'answers':>9}{'in':>12}{'out':>10}"
                          f"{'cost':>10}{'peak day':>11}{'% budget':>9}")
        self.stdout.write("-" * 78)

        total_cost = 0.0
        total_answers = 0
        peaks = []

        for person in people:
            spend = money(person["inp"] or 0, person["out"] or 0,
                          person["wrote"] or 0, person["read"] or 0)
            total_cost += spend
            total_answers += person["answers"]

            # The busiest single day is what a DAILY budget has to clear - a monthly total
            # says nothing about whether the cap ever bound.
            by_day = {}
            for row in rows.filter(user__username = person["user__username"]):
                key = timezone.localtime(row.created_at).date()
                by_day[key] = by_day.get(key, 0) + units(
                    row.input_tokens, row.output_tokens,
                    row.cache_write_tokens, row.cache_read_tokens)

            peak = max(by_day.values()) if by_day else 0
            peaks.append(peak)
            share = (100 * peak / settings.AI_USER_UNITS) if settings.AI_USER_UNITS else 0

            self.stdout.write(
                f"{person['user__username'][:17]:<18}"
                f"{person['answers']:>9}"
                f"{person['inp'] or 0:>12,}"
                f"{person['out'] or 0:>10,}"
                f"{'$' + format(spend, '.2f'):>10}"
                f"{peak:>11,}"
                f"{format(share, '.0f') + '%':>9}")

        # ------------- the whole beta
        days = max((timezone.now() - start).days, 1)

        self.stdout.write("-" * 78)
        self.stdout.write(f"{len(people)} traders · {total_answers} answers · "
                          f"${total_cost:.2f} over {days} days")
        self.stdout.write(f"per trader per month  ~ ${total_cost / len(people) / days * 30:.2f}")
        self.stdout.write(f"all of them per month ~ ${total_cost / days * 30:.2f}")

        # ------------- what the cache is doing
        wrote = sum(p["wrote"] or 0 for p in people)
        read = sum(p["read"] or 0 for p in people)
        uncached = sum(p["inp"] or 0 for p in people)

        self.stdout.write("")
        self.stdout.write("THE CACHE")
        self.stdout.write("-" * 78)

        seen = uncached + wrote + read
        if not seen:
            self.stdout.write("no input recorded")
        elif not read:
            # Reads are the entire point; writes without them are a 25% surcharge. See the
            # silent-invalidator note in chat/context.py.
            self.stdout.write(self.style.ERROR(
                "  nothing was ever read from cache. Something is changing the prompt prefix "
                "on every request."))
        else:
            hit = 100 * read / seen
            # What the same tokens would have cost at the full input price.
            saved = read * in_price * (1 - CACHE_READ_WEIGHT) - wrote * in_price * (CACHE_WRITE_WEIGHT - 1)
            self.stdout.write(f"read from cache         : {read:>13,} tokens ({hit:.0f}% of all input)")
            self.stdout.write(f"written to cache        : {wrote:>13,} tokens")
            self.stdout.write(f"paid full price         : {uncached:>13,} tokens")
            self.stdout.write(self.style.SUCCESS(
                f"  -> the cache saved ${saved:.2f}, which is "
                f"{100 * saved / (total_cost + saved):.0f}% of what the bill would have been"))

        # ------------- and whether the limits were anywhere near binding
        self.stdout.write("")
        self.stdout.write("THE LIMITS")
        self.stdout.write("-" * 78)

        worst = max(peaks) if peaks else 0
        budget = settings.AI_USER_UNITS

        self.stdout.write(f"daily budget per trader : {budget:,} units "
                          f"(${budget * in_price:.2f})")
        self.stdout.write(f"busiest day anyone had  : {worst:,} units "
                          f"({100 * worst / budget:.0f}% of it)" if budget else "")

        if budget and worst < budget * 0.5:
            self.stdout.write(self.style.SUCCESS(
                "  -> nobody came close. The cap is not shaping behaviour, which is the "
                "point of it."))
        elif budget and worst < budget * 0.9:
            self.stdout.write(self.style.WARNING(
                "  -> somebody had a heavy day inside it. Worth watching, not yet worth "
                "changing."))
        else:
            self.stdout.write(self.style.ERROR(
                "  -> somebody reached it. Raise AI_USER_UNITS, or the mentor is teaching "
                "him to ask less."))

        site = settings.AI_GLOBAL_DAILY_UNITS
        if site:
            by_day = {}
            for row in rows:
                key = timezone.localtime(row.created_at).date()
                by_day[key] = by_day.get(key, 0) + units(row.input_tokens, row.output_tokens)

            busiest = max(by_day.values()) if by_day else 0
            self.stdout.write(f"site ceiling            : {site:,} units "
                              f"(${site * in_price:.2f} a day)")
            self.stdout.write(f"busiest day for the site: {busiest:,} units "
                              f"({100 * busiest / site:.0f}% of it)")

        self.stdout.write("")

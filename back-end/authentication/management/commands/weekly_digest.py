import sys

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from authentication import digest, mail


class Command(BaseCommand):
    help = "The weekly summary - sent only to traders who have something to be summarised."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action = "store_true",
                            help = "Decide and report, send nothing.")
        parser.add_argument("--user", type = str, default = None,
                            help = "One username, for checking the real thing on one account.")

    def handle(self, *args, **options):
        # The console on Windows is cp1252 and cannot encode a Hebrew letter, so the first
        # line of output would raise rather than print. The reasons are worth having in
        # Hebrew - they are what somebody reads to understand a quiet week - so the stream
        # is reconfigured rather than the text flattened. On the server it is already UTF-8.
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding = "utf-8")

        now = timezone.now()

        rows = User.objects.filter(is_active = True).exclude(email = "")
        if options["user"]:
            rows = rows.filter(username = options["user"])

        counts = {"digest": 0, "nudge": 0, "silence": 0, "failed": 0}

        for user in rows.iterator():
            kind, payload = digest.decide(user, now)

            if kind == "silence":
                counts["silence"] += 1
                self.stdout.write(f"  — {user.username}: {payload['reason']}")
                continue

            if options["dry_run"]:
                counts[kind] += 1
                self.stdout.write(self.style.WARNING(f"  [dry] {kind} → {user.username}"))
                continue

            token = digest.unsubscribe_token(user)
            link = f"{_frontend()}/email/unsubscribe/{token}"

            if kind == "digest":
                sent = mail.send_weekly_digest(user, payload, link)
            else:
                sent = mail.send_weekly_nudge(user, payload["days"], link)

            if sent:
                digest.mark_sent(user, kind, now)
                counts[kind] += 1
                self.stdout.write(self.style.SUCCESS(f"  ✔ {kind} → {user.username}"))
            else:
                # **A failed send is not marked.** Stamping it would mean the next run skips
                # him for a mail that never arrived - a silence nobody chose.
                counts["failed"] += 1
                self.stdout.write(self.style.ERROR(f"  ✗ {kind} → {user.username}"))

        self.stdout.write("")
        self.stdout.write(f"  סיכומים: {counts['digest']} · תזכורות: {counts['nudge']} · "
                          f"שתיקה: {counts['silence']} · כשלו: {counts['failed']}")


def _frontend():
    from django.conf import settings
    return settings.FRONTEND_URL.rstrip("/")

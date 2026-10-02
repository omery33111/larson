"""Who reached the site, and where from.

**There is no analytics tool here, and that is the point: there is nothing to
install, nothing to consent to, and no third party.** Amplify already keeps a
full CloudFront access log of every request - date, address, referrer, path -
and it keeps it retroactively. What was missing was never the collection, only
the reading, which is this file.

**What it can answer:** how many people reached the site, how many were real
rather than scanners, where they came from, and which screen they landed on.
Put next to the number of accounts that exist, that is the one measurement the
database structurally cannot produce on its own - **the people who arrived and
did not sign up have no row.**

**What it cannot answer, and do not ask it to:** anything that happens after
the first load. The product is a single-page app, so moving from the home page
to the register screen is a client-side route change and **never becomes a
request** - it is invisible here. The day the in-app funnel matters, that is
what would justify a real analytics tool, and not before.

    python tools/traffic.py            # the last 7 days
    python tools/traffic.py --days 30

Needs the AWS CLI, already authenticated.
"""

import argparse
import csv
import io
import json
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone


APP_ID = "dznz974usudjz"
DOMAIN = "larson.co.il"

# A scanner announces itself in the agent string far more often than not, and the
# ones that do not announce it ask for things that do not exist here. Both halves
# are needed: the agent catches the polite crawlers, the paths catch the rest.
BOT_AGENT = re.compile(
    r"bot|crawl|spider|slurp|curl|wget|python|java/|go-http|scan|nmap|nuclei|"
    r"semrush|ahrefs|mj12|dotbot|bytespider|petalbot|headless|phantom|monitor",
    re.I)

# **The route table is the filter, and a blocklist of scanner paths is not.** The
# first version of this listed the paths scanners ask for, and `/api/.env`,
# `/info.php` and `/graphql` all walked straight through it and were counted as
# people - a blocklist is only ever as current as the last scanner somebody saw.
# The app has a closed set of routes, so **anything else is not a person on our
# site**, whatever it calls itself, and a new probe needs no new pattern.
ROUTES = {
    "/", "/authentication/login", "/authentication/register",
    "/authentication/forgot", "/account", "/terms", "/privacy",
    "/profile", "/mentor", "/chat",
}

# The two that carry a signed token in the path rather than the query string.
ROUTE_PATTERN = re.compile(r"^/authentication/(verify|reset)/[^/]+/[^/]+$")

# The routes a person can land on, so that "where did they arrive" reads as a
# screen name and not as a path.
SCREENS = {
    "/": "דף הבית",
    "/authentication/login": "התחברות",
    "/authentication/register": "הרשמה",
    "/authentication/forgot": "שכחתי סיסמה",
    "/mentor": "המנטור",
    "/chat": "צ'אט",
    "/profile": "תעודת הזהות",
    "/account": "החשבון",
    "/terms": "תנאי שימוש",
    "/privacy": "מדיניות פרטיות",
}


def is_route(path):
    trimmed = path.rstrip("/") or "/"
    return trimmed in ROUTES or bool(ROUTE_PATTERN.match(trimmed))


def unquote(value):
    """CloudFront percent-encodes agents and referrers, and uses - for empty."""
    if value in ("-", "", None):
        return ""
    return urllib.parse.unquote(value.replace("\\", ""))


def fetch(days):
    end = datetime.now(timezone.utc)
    start = end - timedelta(days = days)

    out = subprocess.run(
        ["aws", "amplify", "generate-access-logs",
         "--app-id", APP_ID, "--domain-name", DOMAIN,
         "--start-time", start.strftime("%Y-%m-%dT%H:%M:%SZ"),
         "--end-time", end.strftime("%Y-%m-%dT%H:%M:%SZ"),
         "--query", "logUrl", "--output", "text"],
        capture_output = True, text = True, check = True, shell = False)

    url = out.stdout.strip()
    if not url.startswith("https://"):
        raise SystemExit("no log url came back: " + out.stdout + out.stderr)

    with urllib.request.urlopen(url, timeout = 120) as response:
        return response.read().decode("utf-8", "replace")


def read(text):
    rows = list(csv.DictReader(io.StringIO(text)))
    for row in rows:
        row["agent"] = unquote(row.get("cs(User-Agent)"))
        row["referer"] = unquote(row.get("cs(Referer)"))
        row["path"] = row.get("cs-uri-stem", "")
        row["ip"] = row.get("c-ip", "")
        row["html"] = "text/html" in (row.get("sc-content-type") or "")
        row["bot"] = bool(BOT_AGENT.search(row["agent"])) or not is_route(row["path"])

    # **An address that asked for a page and nothing else did not render it.** A
    # scanner sending a browser user-agent at the home page is indistinguishable
    # from a person by the request alone - but a browser that actually ran the
    # app also fetched its script and stylesheet, and a scanner almost never
    # does. This is what separates "requests that look human" from "visits",
    # and without it the unique-address count reads far higher than reality.
    rendered = {r["c-ip"] for r in rows if r["path"].startswith("/assets/")}
    for row in rows:
        row["rendered"] = row["ip"] in rendered
    return rows


def report(rows, days):
    # Every initial load of the app returns index.html whatever the path, so an
    # html hit is a person opening a screen - and an asset request is not.
    loads = [r for r in rows if r["html"] and not r["bot"] and r["rendered"]]
    unrendered = [r for r in rows if r["html"] and not r["bot"] and not r["rendered"]]
    bots = [r for r in rows if r["bot"]]
    people = {r["ip"] for r in loads}

    print()
    print(f"  תנועה ב-{days} הימים האחרונים")
    print("  " + "-" * 46)
    print(f"  פתיחות שבאמת רונדרו         {len(loads):>6}")
    print(f"  כתובות שונות מתוכן          {len(people):>6}")
    print(f"  ביקשו עמוד ולא טענו אותו    {len(unrendered):>6}   (כמעט תמיד סורקים)")
    print(f"  בקשות של סורקים מוצהרים     {len(bots):>6}")
    print(f"  סך כל הבקשות                {len(rows):>6}")

    if not loads:
        print()
        print("  אף אדם לא פתח את האתר בטווח הזה, או שהטווח קצר מדי.")
        return

    print()
    print("  על איזה מסך נחתו")
    print("  " + "-" * 46)
    for path, count in Counter(r["path"] for r in loads).most_common(8):
        name = SCREENS.get(path, "אחר: " + path)
        print(f"  {name:<28}{count:>6}")

    # A referrer that is our own domain is an asset or a reload, not a source.
    sources = Counter()
    for row in loads:
        if not row["referer"]:
            sources["ישירות (הקלדה או קישור שנשלח)"] += 1
        elif DOMAIN in row["referer"]:
            continue
        else:
            try:
                sources[urllib.parse.urlsplit(row["referer"]).netloc or row["referer"]] += 1
            except ValueError:
                sources[row["referer"]] += 1

    print()
    print("  מאיפה הגיעו")
    print("  " + "-" * 46)
    for source, count in sources.most_common(8):
        print(f"  {source:<28}{count:>6}")

    print()
    print("  לפי יום")
    print("  " + "-" * 46)
    for day, count in sorted(Counter(r["date"] for r in loads).items()):
        print(f"  {day:<28}{count:>6}")

    print()
    print("  כמה מהם נרשמו אינו כאן - המספר הזה יושב בבסיס הנתונים.")
    print("  שתי השורות יחד הן ההמרה: פתיחות מול חשבונות שנוצרו בטווח.")
    print()


if __name__ == "__main__":
    # The console on Windows is cp1252 by default, which cannot encode a single
    # Hebrew letter - every line below would raise instead of printing. This is
    # the whole output of the file, so it is not an edge case.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding = "utf-8")

    parser = argparse.ArgumentParser(description = __doc__)
    parser.add_argument("--days", type = int, default = 7)
    parser.add_argument("--raw", action = "store_true",
                        help = "save the log to traffic.csv as well")
    args = parser.parse_args()

    text = fetch(args.days)
    if args.raw:
        with open("traffic.csv", "w", encoding = "utf-8", newline = "") as handle:
            handle.write(text)
        print("  נשמר: traffic.csv")

    report(read(text), args.days)

# Deployment

What it takes to run Larson for other people, and what each number costs.

---

## Running it in production

```
release: python manage.py migrate --noinput && python manage.py collectstatic --noinput
web: gunicorn project.wsgi:application --bind 0.0.0.0:$PORT --worker-class gthread      --workers 1 --threads 8 --timeout 120 --access-logfile - --error-logfile -
```

That is `back-end/Procfile`, which Render, Railway and Heroku all read. Three of those flags
are not decoration:

**`--timeout 120`.** Gunicorn kills a worker that has been busy for 30 seconds by default, and
an answer here streams for longer than that quite normally. At the default, a long debrief is
cut off mid-sentence and the log says the worker timed out rather than that anything was wrong.

**`--worker-class gthread --threads 8`.** Every streamed answer holds its worker for the whole
length of the answer. With the default sync worker, three people talking to Larson at once is
three occupied processes; threads let one process carry all of them, because the time is spent
waiting on the network rather than on the CPU.

**`--workers 1`, and this one is about money.** The rate limits and the spending budget count
in process memory, so each extra worker is another full allowance: two workers make the
site-wide daily cap two site-wide daily caps. One worker keeps the number on the tin true.
Setting `REDIS_URL` moves the counters into a shared cache, and then workers can be added.

`collectstatic` has to run on every deploy. WhiteNoise serves the admin's own CSS through the
manifest backend, which refuses to serve a file it has no hash for - so a missed collectstatic
fails at deploy rather than quietly in somebody's browser.

**The uploaded files need S3, or they are lost on the next push.** On every host worth using
the disk is thrown away each deploy, and the original exports are the thing this product
promises it can re-ingest from. Set `AWS_STORAGE_BUCKET_NAME` and the storage backend switches;
leave it empty and everything stays on the local disk, unchanged.

```
AWS_STORAGE_BUCKET_NAME=larson-uploads
AWS_S3_REGION_NAME=eu-central-1
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
```

And once a week, so the blacklist does not grow without end:

```bash
python manage.py flushexpiredtokens
```

---

## What a trader may spend

The rate limits below count **requests**. This counts what they **cost**, and it is the one
that bounds the bill — because one request is not one price.

A unit is `input + 5 × output`, which is the model's own price ratio ($5 vs $25 per million),
so a unit stands in for money: **1,000,000 units ≈ $5**.

| | default | ≈ |
|---|---|---|
| `AI_DAILY_UNITS` | 400,000 | **$2.00 per trader per day** — about 45 answers, fewer if they come as long threads |
| `AI_GLOBAL_DAILY_UNITS` | 4,000,000 | **$20.00 for the whole site per day** |
| `AI_BUDGET_WINDOW_HOURS` | 24 | rolling, not a reset at midnight |
| `AI_WARN_AT` | 0.90 | how full before the trader is told anything |

**The site ceiling is what makes the worst case a number somebody chose.** A per-trader budget
multiplied by however many people sign up tomorrow is a rate, not a limit. Set it to `0` to
lift it.

The window rolls rather than resetting at a fixed hour, because a window with an edge can be
spent twice across it — all of one day at 23:59 and all of the next at 00:01, which is exactly
the shape a runaway loop produces.

Spending is metered from the API's own `usage` figure, never estimated: it is the only number
that counts the thinking the model did, which is billed as output and can be several times the
answer the trader reads. Every model call in the product is on the meter, including the column
mapping that `/trades/upload/` can fall back to.

**The trader is shown a percentage, and only when it matters** — nothing under 90%, one quiet
line above it, and a clear panel with a renewal time once it is spent. A meter that is always
on screen teaches people to ration themselves, which is the opposite of what this product asks
of them; the notice exists so the wall is not a surprise, not so anyone can budget around it.

### Prompt caching

The persona and the resume come to about 4,200 tokens, are byte-identical until the trader
uploads a file, and are re-sent on every single turn. They carry a `cache_control` breakpoint,
and so does the end of the conversation — **cache reads cost a tenth of ordinary input**, so
the saving compounds with the length of a thread:

| thread | uncached | cached | saved |
|---|---|---|---|
| one question | $0.036 | $0.041 | **−15%** |
| five in a row | $0.213 | $0.114 | 47% |
| ten in a row | $0.506 | $0.212 | 58% |
| twenty in a row | $1.332 | $0.431 | **68%** |

**A single isolated question costs slightly more**, because a cache write costs a quarter more
than an ordinary read and nothing ever reads it back. Break-even is the second request that
shares the prefix — and the prefix is shared across *all* of one trader's conversations, not
just within one, so in practice almost everything after the first question of a session is a
read. Over the beta simulation caching roughly halves the bill.

**It fails silently.** When it breaks, requests keep succeeding and only the bill changes.
`usage_report` prints the hit rate and says so out loud if reads ever fall to zero, and
`CacheTests` pins the prefix as byte-identical between two builds — which is what would catch
a `datetime.now()` added to the persona.

The written profile is deliberately **not** cached: it runs rarely and its prompt is mostly
the statistics document, so every call would pay the write premium and never read it back.

**A follow-up costs more than the question before it.** The whole conversation is resent on
every turn, so the twentieth question in a thread carries nineteen answers of history with it
and costs about **1.8× the first**. This is why the budget is in tokens and not in requests —
a request count cannot see it at all.

### Setting these from evidence

```bash
cd back-end && .venv/Scripts/python.exe manage.py usage_report --days 30
```

Prints what each trader actually cost, the busiest single day anyone had, and whether the cap
came anywhere near binding. **The defaults above were derived from one measured prompt on one
synthetic resume** — a month of real use is a better number, and this is what produces it. The
ledger is also readable in the Django admin under Usage.

---

## Rate limits

The three endpoints that call Claude — the chat stream, the mentor debrief and the written
profile — are capped per user, in two windows: an hourly one generous enough for a real
session, and a daily one that stops a slow loop running under it all night. Anything that
sends mail, and the login and registration endpoints, are capped by IP.

The rates are in `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]` in `settings.py` and can be
changed without touching code. They are switched off while the test suite runs; the limits
themselves are tested deliberately, in `ThrottleTests`.

**The counters live in memory by default, which is per process** — with several workers the
effective limit is multiplied by the worker count. Setting `REDIS_URL` makes them shared and
the limits exact.

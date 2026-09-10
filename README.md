# Larson — an AI mentor for traders

An intelligence layer on top of trading journals. The trader uploads trade exports, the system
builds a cumulative trading "resume" from them, and two chats answer from that personal data.

- **Product spec:** [trading-mentor-spec-v2.md](trading-mentor-spec-v2.md)
- **Build instructions and stack:** [CLAUDE.md](CLAUDE.md)

The product's interface language is Hebrew (RTL). This file and the commit history are in
English; see "Language" in CLAUDE.md.

---

## Project layout

```
larson/
├── back-end/                       Django + DRF
│   ├── project/                    settings.py, urls.py, wsgi.py, asgi.py
│   ├── project/throttling.py       the rate limits, shared by three apps
│   ├── authentication/             JWT, email verification, password reset, export, erase
│   ├── trades/                     ingestion: parsers, symbols, statements, LLM mapping
│   ├── analytics/                  statistics, score, insights, written profile
│   ├── chat/                       conversations, messages, SSE streaming, starring
│   ├── mentor/                     the single mentor thread, deviation and compliance engines
│   ├── .env                        DJANGO_SECRET_KEY, ANTHROPIC_API_KEY (never committed)
│   ├── manage.py
│   └── requirements.txt
│
└── front-end/                      React + TypeScript (Vite)
    └── src/
        ├── index.tsx               all Routes + Provider
        ├── App.tsx                 layout: Navbar + Outlet + Footer
        ├── app/                    store, hooks, session (tokens + renewal), interceptors
        ├── endpoints/              endpoints.ts
        ├── models/                 Authentication, Trade, Analytics, Chat, Mentor
        └── features/
            ├── authentication/     Login, Register, VerifyEmail, ForgotPassword,
            │                       ResetPassword, AccountPage
            ├── trades/             ResumeDialog, IngestionConfirm, tradesAPI, tradesSlice
            ├── analytics/          TraderProfilePage, ScoreHero, AngelDevil, Breakdowns
            ├── chat/               ChatPage, ChatThread, ChatSidebar, ChatMessage
            ├── mentor/             MentorPage, mentorAPI, mentorSlice
            ├── larson/             LarsonMark — the character, and the traced hair
            ├── base/               HomePage, ErrorPage, Terms, Privacy
            └── navigators/         MyNavbar, MyFooter
```

---

## The ingestion engine

**Formats:** CSV · TSV · XLSX · XLS · MT4/MT5 HTML statements (up to 20MB). Column mapping is
deterministic and recognises headers **in both Hebrew and English**, so a single parser reads
journals and brokers that name their columns differently.

**Only three required fields:** date, symbol, and outcome (a P&L column, or entry + exit +
direction). Everything else is optional and only deepens the analysis.

**The original file is kept exactly as uploaded**, under `back-end/static/files/trade_files/`.
Nothing is converted to an intermediate format — normalisation goes straight into the `trades`
table. If a parser bug turns up, it can be fixed and the file re-ingested from the original.

---

## Mail — verification and password reset

Signing up sends a confirmation link, and the account cannot be logged into until it is
opened. "Forgot my password" sends a reset link. Both links are good for 24 hours.

**With no mail server configured, messages are printed to the terminal instead of being
sent**, which is enough to develop and test the whole flow. To deliver for real, fill these
in `back-end/.env`:

```
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=you@gmail.com
EMAIL_HOST_PASSWORD=<a Google app password, not your account password>
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=Larson <you@gmail.com>
```

Gmail rejects your normal password over SMTP; an app password is generated under the Google
account's security settings, with two-step verification switched on.

The links inside the mail are built from `FRONTEND_URL`, never from the incoming request.

---

## Claude API key

The profile page works in full **without** a key — every number, the score and the
"angel and devil" are computed locally.

The only thing that needs a key is the **written profile**, along with the chat and the mentor
debrief. To enable them, add this to `back-end/.env`:

```
ANTHROPIC_API_KEY=<your key>
```

Then restart the Django server. Keys are issued at console.anthropic.com under API Keys.

---

## First-time setup

**Back end** (once):

```bash
cd back-end && py -m venv .venv && .venv/Scripts/python.exe -m pip install -r requirements.txt
```

Create `back-end/.env` following `back-end/.env.example`:

```bash
cd back-end && .venv/Scripts/python.exe -c "from django.core.management.utils import get_random_secret_key as g; print('DJANGO_SECRET_KEY=' + g())" > .env
```

Then the migrations:

```bash
cd back-end && .venv/Scripts/python.exe manage.py migrate
```

**Front end** (once):

```bash
cd front-end && npm install
```

---

## Running it — two terminals

Terminal 1 — back end (port 8000):

```bash
cd back-end && .venv/Scripts/python.exe manage.py runserver 8000
```

Terminal 2 — front end (port 5173):

```bash
cd front-end && npm run dev
```

The interface: http://localhost:5173

---

## How the client authenticates

The token pair lives in `localStorage` under `token` (`{access, refresh}`) and travels in the
`Authorization: Bearer <access>` header. `app/session.ts` owns it and is the only place that
renews it — including for the streaming calls, which use `fetch` and never pass through the
axios interceptor.

---

## Tests

```bash
cd back-end && .venv/Scripts/python.exe manage.py test
```

---

## Error monitoring

Set `SENTRY_DSN` in `back-end/.env` and errors are reported to Sentry; leave it empty and
nothing is sent. **This matters more than it looks for this product**: a failure inside a
streaming answer is otherwise invisible — the response headers are already out, the browser
receives a truncated body with no explanation, and nothing is written anywhere that gets read.

Personal data is withheld deliberately: no cookies, no headers, and `max_request_body_size`
is `never`. What leaves is the traceback and where it happened.

**Switching it on means a third party processes technical error reports, so update the
privacy policy before using it in production.**

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


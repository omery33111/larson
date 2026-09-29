# Architecture

How Larson is put together, and the decisions that are load-bearing.
The reasoning behind each one lives in [CLAUDE.md](../CLAUDE.md).

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
    ├── .env                        VITE_SITE_URL — the domain the share card points at
    ├── public/                     favicons, manifest, robots.txt, the share card
    ├── tools/                      the asset generators (see "Brand assets")
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

**The original file is kept exactly as uploaded**, under `back-end/media/trade_files/`, outside anything served.
Nothing is converted to an intermediate format — normalisation goes straight into the `trades`
table. If a parser bug turns up, it can be fixed and the file re-ingested from the original.

---

## How the client authenticates

The token pair lives in `localStorage` under `token` (`{access, refresh}`) and travels in the
`Authorization: Bearer <access>` header. `app/session.ts` owns it and is the only place that
renews it — including for the streaming calls, which use `fetch` and never pass through the
axios interceptor.

---

## Staying signed in

The tick box on the login form chooses which storage holds the token pair: `localStorage`
when it is ticked, `sessionStorage` when it is not. Unticked, the session really is gone when
the window closes rather than merely out of sight — which is the answer that matters on a
borrowed machine, and it is why the box starts unticked.

`app/session.ts` owns that choice, and everything else reads storage through it.

---

## Health check

```
GET /healthz/   →   {"status": "ok"}
```

For the host to ping. It touches no database, no model and no authentication on purpose: a
health check that can fail for a second reason tells the host to restart a server that was
fine.

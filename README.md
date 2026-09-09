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
│   ├── authentication/             register, login, logout (JWT)
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
        ├── app/                    store.ts, hooks.ts, interceptors.ts, muiTheme.ts
        ├── endpoints/              endpoints.ts
        ├── models/                 Authentication, Trade, Analytics, Chat, Mentor
        └── features/
            ├── authentication/     Login, Register, authenticationAPI, authenticationSlice
            ├── trades/             ResumeDialog, IngestionConfirm, tradesAPI, tradesSlice
            ├── analytics/          TraderProfilePage, ScoreHero, AngelDevil, Breakdowns
            ├── chat/               ChatPage, ChatThread, ChatSidebar, ChatMessage
            ├── mentor/             MentorPage, mentorAPI, mentorSlice
            ├── larson/             LarsonMark — the character, and the traced hair
            ├── base/               HomePage, ErrorPage
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

## Tests

```bash
cd back-end && .venv/Scripts/python.exe manage.py test
```

---

## Endpoints

| Method | URL | Description |
|---|---|---|
| `POST` | `/authentication/register/` | Register — `username`, `password`, `email` |
| `POST` | `/authentication/login/` | Log in — returns `access` + `refresh` |
| `POST` | `/authentication/logout/` | Log out — blacklists the `refresh_token` |
| `GET`  | `/authentication/` | Token check — returns `username` |
| `POST` | `/trades/upload/` | Upload a file — parses and previews it. **Saves nothing** |
| `POST` | `/trades/confirm/` | Confirm ingestion — writes to the resume, with dedup |
| `GET`  | `/trades/` | Trade list (`limit`, `offset`) |
| `GET`  | `/trades/summary/` | Resume state: count, date range, instruments, accounts, last update |
| `DELETE` | `/trades/resume/` | Full cascading delete: source files on disk, the trades table, and the written profile |
| `GET`  | `/analytics/` | The whole profile payload: score, metrics, behaviour, breakdowns, angel and devil |
| `GET`  | `/analytics/profile/` | The written profile |
| `POST` | `/analytics/profile/generate/` | Create or refresh the written profile through `claude-opus-5` |
| `GET`  | `/chat/conversations/` | Conversation list |
| `POST` | `/chat/conversations/` | Start a new conversation |
| `GET`  | `/chat/conversations/<id>/` | One conversation with all of its messages |
| `DELETE` | `/chat/conversations/<id>/` | Delete a conversation |
| `POST` | `/chat/conversations/<id>/stream/` | Send a message — returns **SSE** (`text/event-stream`). `multipart`, with `message` and an optional `file` for a scratch document |
| `PATCH` | `/chat/conversations/<id>/` | Rename a conversation |
| `POST` | `/chat/messages/<id>/star/` | Star or unstar a message |
| `GET`  | `/chat/starred/` | The starred messages, each with the conversation it came from |
| `GET`  | `/mentor/` | The single mentor thread + resume state (how many trades, how many days ago) |
| `POST` | `/mentor/stream/` | Debrief — `trade_file_id` for a confirmed file, or `message` for a question. Returns **SSE** |

The token is kept in `localStorage` under `token` (`{access, refresh}`) and sent in the
`Authorization: Bearer <access>` header.

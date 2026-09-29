<div align="center">

<img src="front-end/public/icon-192.png" alt="Larson" width="96" height="96">

# Larson

**An AI mentor for traders.** Upload your trade history, and Larson tells you what you keep
doing — in your own numbers, not in generalities.

[Architecture](docs/architecture.md) · [Configuration](docs/configuration.md) ·
[Deployment](docs/deployment.md) · [Development](docs/development.md)

</div>

---

## The problem

Every serious trader keeps a journal, and almost nobody reads theirs. A spreadsheet of a
thousand trades will tell you your win rate. It will not tell you that the trades you take in
the thirty minutes after a loss have cost you six thousand dollars, that you hold losers four
times longer than winners, or that the setup you are proudest of is the one that bleeds.

Those are not columns. Each one is a comparison between two slices of a history, and nobody
scrolls their way to it.

## What Larson does

**Reads the journal you already keep.** CSV, Excel, or the HTML statement MT4 and MT5 produce.
Column names are recognised in Hebrew and English, so exports from different journals, prop
firms and brokers land in one place. Three fields are required — date, symbol, outcome — and
everything else only deepens the analysis.

**Builds a cumulative trading resume.** Every file merges into one record, de-duplicated by
content, so re-uploading an overlapping export adds what is new and nothing else.

**Computes the things a journal cannot show you.** Revenge trades, the day after a red day,
overtrading, hold-time asymmetry, the cost of your own flagged mistakes, whether your own
confidence rating predicts anything, and a five-pillar trading score that is always shown
broken down rather than as a single verdict.

**Debriefs a session the moment it ends.** Send the day's trades and Larson compares them to
the resume as it stood before them — exposure, pace, hours, revenge, hold time, expectancy,
abandoned setups — and checks each new trade against the rules your own history produced.
One trade is enough for that; a rule needs an event, not a sample.

**Answers questions about you, from your data.** A general chat with the full statistics
document in context, and a temporary file can be attached for comparison without ever
entering the record it is compared against.

## The one rule the product is built on

**The model writes. It never calculates.**

Every number — the score, the expectancy, the drawdown, each finding and the size of the
sample behind it — is computed deterministically in Python and handed to the model as a
finished document. The model's job is to say it in a sentence a trader will act on.

A mentor that invents a figure you cannot go and check is worse than one that says nothing,
and this is the line that makes the difference structural rather than hopeful.

## Security and privacy

This product holds somebody's complete trading record, which is why these are decisions and
not defaults:

- **What leaves the server is disclosed in full.** Computed statistics, the written profile
  and the messages of a conversation go to Anthropic to be turned into an answer. The
  password, the email address and the uploaded files never do. Every other page is computed
  here and does not leave.
- **The original exports are kept and never served.** They live outside anything static, with
  no public route, because they are the insurance policy that lets a parser bug be fixed and
  the data re-read.
- **Take it or end it.** One JSON file with everything held about you, and an erase that
  reaches the uploaded bytes on disk rather than only the rows pointing at them.
- **Reviewed rather than assumed.** Three passes over the code found fourteen things worth
  changing, six of them measured rather than guessed — a rate limit that a forged header
  walked straight past, a "sign out everywhere" that left access tokens alive for a day, and
  a prompt injection that arrived through an uploaded spreadsheet. All fixed, all with tests
  written to fail if they come back. The record is in [CLAUDE.md](CLAUDE.md).

## Built with

| | |
|---|---|
| **Backend** | Django · Django REST Framework · SimpleJWT · SQLite or PostgreSQL |
| **Frontend** | React · TypeScript · Redux Toolkit · Vite · MUI where behaviour is needed |
| **Model** | Claude Opus 5, called only from the server, with prompt caching and a token budget |
| **Streaming** | Server-sent events over `StreamingHttpResponse` — no WebSocket, no Redis |

Interface language is Hebrew, right to left. Code, commits and documentation are in English.

## Status

All seven build milestones are complete, and the work since has been launch readiness:
rate limits and a spending budget, email verification and password reset, sign-in with
Google, a security review, and the deployment path. 387 tests pass.

What remains is infrastructure and decisions rather than features — a domain, a host, and a
beta.

## Documentation

| | |
|---|---|
| [docs/architecture.md](docs/architecture.md) | How it is put together: layout, the ingestion engine, sessions |
| [docs/configuration.md](docs/configuration.md) | Every external service, and what happens without one |
| [docs/deployment.md](docs/deployment.md) | Running it for other people, and what each number costs |
| [docs/development.md](docs/development.md) | Running it on a workstation |
| [CLAUDE.md](CLAUDE.md) | The full decision record — why each thing is the way it is |
| [trading-mentor-spec-v2.md](trading-mentor-spec-v2.md) | The product specification |

---

<div align="center">

© 2026 Larson. All rights reserved.

</div>

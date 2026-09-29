# Configuration

Every external service Larson talks to, and what it does without one.

**Each of them is wired and inert until its value is supplied.** With no mail server the
messages are printed to the terminal; with no Claude key every screen but the written
profile, the chat and the debrief still works; with no Google client id the button does not
render; with no Sentry DSN nothing is reported. Nothing half-works.

The complete list of variables, with a note on each, is
[`back-end/.env.example`](../back-end/.env.example).

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

## Signing in with Google

Optional, and off until a client id is set. Where it comes from: Google Cloud Console →
APIs & Services → Credentials → **Create OAuth client ID** → *Web application*, with the
site's address under *Authorised JavaScript origins* (`http://localhost:5173` in development,
the real domain in production). No client secret is involved — this flow only verifies an ID
token, and the client id is public by design.

The same value goes in two places:

```
back-end/.env     GOOGLE_CLIENT_ID=...
front-end/.env    VITE_GOOGLE_CLIENT_ID=...
```

Leave them empty and the button does not render and the endpoint says so plainly. Nothing else
changes; the password form is a complete way in.

**Google is the whole integration** — no django-allauth, no social-auth, no identity service in
the middle. The browser gets a signed ID token, posts it to `/authentication/login/google/`,
and `authentication/google.py` checks the signature against Google's published keys. Three
checks carry it: the signature, that `aud` is our own client id (a token minted for another
site is a valid Google token, and without this their login would be ours), and that Google
says the address is verified.

The account link is stored on Google's **subject id**, not on the email address. An address can
be changed by its owner and reassigned by Google; a subject is issued once. The address is used
only to attach a first Google sign-in to an account that already registered with a password
here — after that the stored row decides.

An account opened this way has **no password at all**, so two screens change shape: changing a
password sends it to the reset mail instead, and deleting the account asks it to sign in with
Google again rather than for a password it never had.

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

## Behind a proxy, one variable matters

```
TRUSTED_PROXY_COUNT=1     on Render, Railway, or anything that terminates TLS for you
TRUSTED_PROXY_COUNT=0     running the server directly (the default)
```

It decides what a rate limit counts. At 0 the limits count the address the socket came from,
which is right with nothing in front and merely strict behind a proxy. **Unset in code, the
framework trusts the `X-Forwarded-For` header instead - and the caller writes that header**, so
a different value on each request buys a fresh allowance every time. Measured before this was
set: eight wrong passwords in a row, not one of them refused.

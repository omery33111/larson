# Development

Running Larson on a workstation. For production see
[deployment.md](deployment.md); for the services it talks to see
[configuration.md](configuration.md).

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

## Brand assets

```bash
cd front-end && npm run icons
```

Regenerates everything in `public/`: the favicons, the two manifest icons, the maskable icon,
and the 1200x630 card that WhatsApp and Twitter draw when the link is pasted.

**Nothing here is drawn by hand.** `tools/render-mark.mjs` renders `LarsonMark.tsx` — the one
place the character lives — to a standalone `public/favicon.svg`, so the icon in the tab and
the figure in the navbar cannot drift apart. `tools/make-icons.mjs` then rasterises that with
whichever of Chrome or Edge is installed, driven headless, and reduces the small sizes with
the area filter in `tools/png.mjs`. No dependency is installed for any of it.

Chrome will not open a window narrower than about 500px, which is why the small sizes are
reduced from the 512 rather than screenshotted directly: asking for a 32px shot returns a 32px
crop of a 500px page.

**`VITE_SITE_URL` has to be the real domain on the production build.** `og:image` and `og:url`
must be absolute — a crawler has nothing to resolve a relative path against — and Vite
substitutes the value into `index.html` at build time, so it is set before `npm run build`,
not after.

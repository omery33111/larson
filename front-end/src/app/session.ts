import axios from 'axios';
import { jwtDecode } from 'jwt-decode';

import { refreshURL } from '../endpoints/endpoints';



/**
 * The one place that owns the token pair, and the only place that renews it.
 *
 * **The refresh token existed from the first day and was never once exchanged.** It was
 * issued at login, stored, and blacklisted at logout - so the ninety days it was good for
 * were decoration, and the real session was the access token's single day. After that the
 * interceptor saw a 401 and logged the trader out wherever he happened to be standing,
 * which on this product means in the middle of a debrief.
 *
 * It lives in `app/` and not in the authentication feature because the streaming calls need
 * it too: the chat and the mentor talk to the server with `fetch`, not axios, so an axios
 * interceptor alone would renew the session for every screen except the two that matter.
 */

type Pair = { access: string; refresh: string };


// ------------------------- WHERE THE SESSION IS KEPT -------------------------
/**
 * Everything the session consists of. Named here because both stores have to be cleared of
 * all of it - a leftover `userName` in the store that is not in use is a name on the navbar
 * belonging to nobody.
 */
const KEYS = ['token', 'userName', 'is_staff', 'loginTime'];

/**
 * **"Stay signed in" is this one choice and nothing else.** `localStorage` survives the
 * browser closing; `sessionStorage` does not survive the tab. That is the whole difference,
 * and it is the difference the tick box on the login screen is describing honestly.
 *
 * It matters for this product in particular: the session is a ninety-day refresh token, and
 * this is somebody's trading record. On a borrowed machine, leaving the box unticked means
 * the session really is gone when the window closes rather than merely out of sight.
 */
let chosen: Storage | null = null;

function store(): Storage {
  if (chosen) return chosen;

  try {
    // Resolved by looking rather than by a flag of its own. A flag is a second thing that can
    // disagree with where the token actually is, and the token is the session.
    chosen = sessionStorage.getItem('token') ? sessionStorage : localStorage;
  } catch {
    // Private windows and locked-down browsers can throw on the accessor itself.
    chosen = localStorage;
  }

  return chosen;
}


/** Called at sign-in, before anything is written. */
export function rememberSession(remember: boolean) {
  chosen = remember ? localStorage : sessionStorage;

  const other = remember ? sessionStorage : localStorage;
  KEYS.forEach((key) => { try { other.removeItem(key); } catch { /* nothing to remove */ } });
}


/** Whether this session was told to outlive the browser closing. */
export function isRemembered(): boolean {
  return store() === localStorage;
}


export function readItem(key: string): string | null {
  try {
    return store().getItem(key);
  } catch {
    return null;
  }
}


export function writeItem(key: string, value: string) {
  try {
    store().setItem(key, value);
  } catch { /* a browser refusing to store is not a reason to fail the sign-in */ }
}


export function removeItem(key: string) {
  try {
    store().removeItem(key);
  } catch { /* already gone as far as anybody can tell */ }
}


/** The whole session, out of both stores. */
export function clearSession() {
  [localStorage, sessionStorage].forEach((where) => {
    KEYS.forEach((key) => { try { where.removeItem(key); } catch { /* nothing to remove */ } });
  });

  chosen = null;
}


export function readTokens(): Pair | null {
  try {
    const raw = readItem('token');
    return raw ? JSON.parse(raw) : null;
  } catch {
    // A corrupted entry is the same situation as no entry, and throwing here would take the
    // whole app down on start.
    return null;
  }
}


export function writeTokens(pair: Partial<Pair>) {
  const current = readTokens();
  writeItem('token', JSON.stringify({ ...current, ...pair }));
}


export function clearTokens() {
  removeItem('token');
}


export function accessToken(): string {
  return readTokens()?.access || '';
}


/** Seconds left on a token, or 0 if it is unreadable - which is treated as expired. */
function secondsLeft(token: string): number {
  try {
    const { exp } = jwtDecode<{ exp: number }>(token);
    return exp - Date.now() / 1000;
  } catch {
    return 0;
  }
}


// Renew when this little is left rather than waiting for a rejection. A minute covers a slow
// request that was still valid when it was sent and expired before it arrived.
const RENEW_WITHIN_SECONDS = 60;


// **One refresh at a time, however many callers ask.** A page that fires four requests at
// once would otherwise start four refreshes; with rotation on, the first would invalidate
// the token the other three are trying to use, and the session would die from being renewed.
let inFlight: Promise<string | null> | null = null;


export function refreshSession(): Promise<string | null> {
  if (inFlight) return inFlight;

  const refresh = readTokens()?.refresh;
  if (!refresh) return Promise.resolve(null);

  inFlight = axios
    // Bare axios, not the app instance: this request must not be caught by the interceptor
    // that calls it, or a failed refresh would try to refresh itself.
    .post(refreshURL, { refresh })
    .then((response) => {
      const pair = response.data as Partial<Pair>;
      if (!pair?.access) return null;

      // Rotation is on server-side, so a new refresh token comes back with it and the old
      // one is now blacklisted. Storing only the access token would leave us holding a dead
      // refresh and one day of life.
      writeTokens(pair);
      return pair.access as string;
    })
    .catch(() => null)
    .finally(() => { inFlight = null; });

  return inFlight;
}


/**
 * A token that is good right now, renewing first if the current one is about to lapse.
 *
 * Used by the streaming calls. A stream cannot be retried the way a request can - by the
 * time the server rejects it the response has already begun - so those check before they
 * start rather than recovering afterwards.
 */
export async function freshAccessToken(): Promise<string> {
  const token = accessToken();

  if (token && secondsLeft(token) > RENEW_WITHIN_SECONDS) return token;

  return (await refreshSession()) || token;
}

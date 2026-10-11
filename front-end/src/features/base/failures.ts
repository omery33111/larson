/**
 * What a broken stream says to the trader, named by what actually broke.
 *
 * **Both streaming thunks had one sentence for every status that was not 401:** "החיבור
 * לשרת נקטע" — the connection was cut. For a 429 that is simply untrue, and untrue in the
 * most expensive direction: nothing was cut, he sent messages faster than the limit allows,
 * and a screen that tells him the site is broken invites him to **try again immediately**,
 * which is the one thing that makes it worse. The same sentence covered 500 and 503, where
 * it is equally wrong — the server answered, it just could not do the work.
 *
 * One module because there are two callers. Two copies of a rule drift, and the copy that
 * drifts is the one nobody reads again — this project has the scar.
 *
 * This is the browser's half of `chat/failures.py`, and it holds the same line: the trader
 * gets a sentence he can act on, and nothing about our infrastructure.
 */

/** The server asks for a wait in `Retry-After`; it is seconds, or an HTTP date. */
const waitFrom = (header: string | null): number => {
  if (!header) return 0;

  const seconds = Number(header);
  if (Number.isFinite(seconds) && seconds > 0) return Math.ceil(seconds);

  const when = Date.parse(header);
  if (!Number.isNaN(when)) return Math.max(0, Math.ceil((when - Date.now()) / 1000));

  return 0;
};


/** How long to wait, in words, so the number is never a bare figure. */
const inWords = (seconds: number): string => {
  if (!seconds) return '';
  if (seconds < 60) return ` נסה שוב בעוד ${seconds} שניות.`;

  const minutes = Math.ceil(seconds / 60);
  if (minutes === 1) return ' נסה שוב בעוד דקה.';
  if (minutes < 60) return ` נסה שוב בעוד ${minutes} דקות.`;

  const hours = Math.ceil(minutes / 60);
  return hours === 1 ? ' נסה שוב בעוד שעה.' : ` נסה שוב בעוד ${hours} שעות.`;
};


export interface StreamFailure {
  status?: number;
  retryAfter?: string | null;
  name?: string;
}


/**
 * The sentence for a stream that never opened.
 *
 * `429` is the rate limit and is the reason this exists. **The limit is deliberately not
 * named as a number**: "40 an hour" is a thing to plan around, and the product's whole
 * position on limits is that he should be told when he can continue, not handed a budget
 * to ration himself against.
 */
export const streamFailureMessage = (error: StreamFailure): string => {
  const status = error?.status;

  if (status === 429) {
    const wait = inWords(waitFrom(error?.retryAfter ?? null));

    return `שלחת הרבה הודעות ברצף, אז לארסון מבקש רגע.${wait || ' נסה שוב בעוד דקה.'}`;
  }

  // The server answered and could not do the work - which is our fault and not his, and is
  // the same thing the back end says in that case.
  if (status && status >= 500) return 'לארסון לא זמין כרגע. נסה שוב בעוד רגע.';

  // 413 is the upload ceiling; the ingestion engine says the same thing on its own path.
  if (status === 413) return 'הקובץ גדול מדי.';

  return 'החיבור לשרת נקטע.';
};

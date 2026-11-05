import { ReactNode } from 'react'


/**
 * Isolate left-to-right islands so a Hebrew sentence does not scramble them.
 *
 * Larson writes free Hebrew with English tag names, numbers and $ amounts mixed in, and the
 * browser's bidi algorithm reorders each island against the Hebrew and the punctuation around
 * it: "$53.83" loses its order, "Change in delta levels" reads backwards, a minus drifts onto
 * the wrong side. The render-side twin of quoted() on the server, and the one place the rule
 * lives so the two readers (the chat and the written profile) cannot drift apart.
 *
 * Two token kinds are isolated, each in its own <bdi>, and nothing else:
 *   - A Latin-letter phrase: words plus the connectors that bind them. A connector (space,
 *     apostrophe, dot, slash, hyphen) is taken only when a LETTER follows it - never a digit -
 *     so a ticker like "MNQU6" stays whole (its digit is glued, no connector), while a count
 *     after a space is left out: "Change in delta levels — 9 עסקאות" and "Daily 50% FVG" keep
 *     the number its own token, beside the Hebrew noun ("9 עסקאות") or as a clean "50%", not
 *     merged into the English word as "Daily 50" with a stray "%".
 *   - A number/currency token: an amount, percentage, ratio, time, date or numeric range,
 *     kept whole (its . , : / separators join only digit-to-digit, so "-$18", "16:00–17:00"
 *     and "25/08" stay one unit while a trailing sentence comma or period is left OUT -
 *     "$1,195.50," keeps its thousands comma but drops the list comma, which would otherwise
 *     double up against the Hebrew comma before it). A letter suffix glued straight onto a
 *     number joins it ("2.9R", "5K", "50%WR") so it does not render reversed as "R2.9".
 *
 * Everything else - plain Hebrew, a lone space, a middot, an em-dash, a bare separator -
 * flows as text. Consecutive isolated islands keep their logical order when read right-to-left,
 * so a compound citation like "25/08 17:36 · MNQU6 · 87 שניות · -$255" reads correctly. The
 * raw text copied by the copy button or sent to the server is never altered.
 */
const LETTER = "[A-Za-z](?:[A-Za-z0-9]|[ '’./\\-](?=[A-Za-z]))*";
const NUMBER = "[-–]?[$€£₪¥]?\\d+(?:[.,:/]\\d+)*%?[A-Za-z]*(?:\\s*[–-]\\s*[$€£₪¥]?\\d+(?:[.,:/]\\d+)*%?[A-Za-z]*)*";
const ISLAND = new RegExp("(" + LETTER + "|" + NUMBER + ")", "g");
const WHOLE = new RegExp("^(?:" + LETTER + "|" + NUMBER + ")$");

export const isolate = (text: string, keyBase: string): ReactNode[] =>
  text.split(ISLAND).map((chunk, index) =>
    chunk && WHOLE.test(chunk) ? <bdi key={`${keyBase}-${index}`}>{chunk}</bdi> : chunk);

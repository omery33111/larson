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
 *     the number its own token, beside the Hebrew noun ("9 עסקאות") or as a clean "50%".
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
const LEADING_DASH = /^[-–]/;
const HEBREW_END = /[֐-׿]$/;

/**
 * The base direction a paragraph should render in, by which script carries it.
 *
 * Our pages are RTL, so a <p> inherits RTL and a fully English answer from Larson renders
 * scrambled (phrases reversed, the period thrown to the front). The fix is to set the
 * paragraph's own dir: more Hebrew letters than Latin -> rtl, otherwise ltr. Counting letters
 * (not the first strong character, which `dir="auto"` uses) keeps a Hebrew sentence that opens
 * with an English ticker — "MNQU6 הוא הטיקר..." — right-to-left, while a mostly-English answer
 * goes left-to-right. Within either, isolate() and the browser's own bidi handle the embedded
 * runs of the other script.
 */
export const baseDir = (text: string): 'rtl' | 'ltr' => {
  const hebrew = (text.match(/[֐-׿]/g) || []).length;
  const latin = (text.match(/[A-Za-z]/g) || []).length;
  return hebrew >= latin ? 'rtl' : 'ltr';
};


export const isolate = (text: string, keyBase: string): ReactNode[] => {
  const parts = text.split(ISLAND);
  const nodes: ReactNode[] = [];
  parts.forEach((chunk, index) => {
    if (!chunk) return;
    if (!WHOLE.test(chunk)) { nodes.push(chunk); return; }

    // A leading dash right after a Hebrew letter is a prefix maqaf (ה-, ל-, ב-, ו-, מ-), not a
    // minus sign. Absorbed into the number it flips to the island's far edge and detaches,
    // rendering "ה-1:5" as "ה1:5-". Keep it out as plain text beside the Hebrew word; a dash
    // after a space is a real negative and stays in the island ("שפל -$18"). A regex lookbehind
    // would be cleaner but throws at parse time on older iOS Safari and takes the page down, so
    // the check is done here on the preceding chunk instead.
    const previous = parts[index - 1];
    if (LEADING_DASH.test(chunk) && previous && HEBREW_END.test(previous)) {
      nodes.push(chunk[0]);
      nodes.push(<bdi key={`${keyBase}-${index}`}>{chunk.slice(1)}</bdi>);
    } else {
      nodes.push(<bdi key={`${keyBase}-${index}`}>{chunk}</bdi>);
    }
  });
  return nodes;
};

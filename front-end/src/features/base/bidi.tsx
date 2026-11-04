import { ReactNode } from 'react'


/**
 * Isolate left-to-right islands so a Hebrew sentence does not scramble them.
 *
 * Larson writes free Hebrew with English tag names, numbers and $ amounts mixed in, and the
 * browser's bidi algorithm reorders each island against the Hebrew and the punctuation around
 * it: "$53.83" loses its order, "Change in delta levels" reads backwards, a minus drifts onto
 * the wrong side. Wrapping every run that carries a Latin letter, a digit or a currency sign
 * in <bdi> isolates it - the render-side twin of quoted() on the server, and the one place the
 * rule lives so the two readers (the chat and the written profile) cannot drift apart. A run
 * with no such character (plain Hebrew, a lone space or comma) is left untouched, and the raw
 * text copied by the copy button or sent to the server is never altered.
 */
const LTR_ISLAND = /([^֐-׿]*[A-Za-z0-9$€£₪¥][^֐-׿]*)/g;
const HAS_LTR = /[A-Za-z0-9$€£₪¥]/;

export const isolate = (text: string, keyBase: string): ReactNode[] =>
  text.split(LTR_ISLAND).map((chunk, index) =>
    HAS_LTR.test(chunk) ? <bdi key={`${keyBase}-${index}`}>{chunk}</bdi> : chunk);

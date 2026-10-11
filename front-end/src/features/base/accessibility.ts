/**
 * What the trader chose about how the site should look, and where that choice lives.
 *
 * **A menu like this does not make a site accessible, and it is important to be straight
 * about that.** ת"י 5568 is WCAG 2.0 AA applied to the site itself - keyboard reach, real
 * labels, contrast, landmarks, focus - and a floating widget bolted onto a site that fails
 * those is a sticker over a warning light. The widget earns its place for a different and
 * real reason: somebody with low vision wants bigger text *on this site* without changing
 * it everywhere else, and somebody with vestibular sensitivity wants the pulsing aura to
 * stop. Those are preferences the page itself must honour, and nothing else offers them.
 *
 * Every preference is a class on `<html>`, never an inline style. A class can be answered
 * by a media query and overridden per breakpoint; an inline style can only be beaten by
 * `!important`, and this project has none.
 */

export interface Preferences {
  /** 0 is the design's own size; each step is +12.5%, to a ceiling of +50%. */
  textStep: number;
  highContrast: boolean;
  highlightLinks: boolean;
  stopMotion: boolean;
  readableFont: boolean;
}

export const NONE: Preferences = {
  textStep: 0,
  highContrast: false,
  highlightLinks: false,
  stopMotion: false,
  readableFont: false,
};

export const MAX_STEP = 4;

const KEY = 'larson-accessibility';


/**
 * **Read through a try/catch, and a failure means the defaults.** In a private window, with
 * site data blocked, or during a thumbnail capture, the accessor itself can throw - and a
 * preferences store that can take the page down with it is worse than no store.
 */
export const read = (): Preferences => {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return NONE;

    const saved = JSON.parse(raw) as Partial<Preferences>;

    return {
      textStep: Math.min(MAX_STEP, Math.max(0, Number(saved.textStep) || 0)),
      highContrast: !!saved.highContrast,
      highlightLinks: !!saved.highlightLinks,
      stopMotion: !!saved.stopMotion,
      readableFont: !!saved.readableFont,
    };
  } catch {
    return NONE;
  }
};


export const write = (preferences: Preferences) => {
  try {
    localStorage.setItem(KEY, JSON.stringify(preferences));
  } catch {
    // Nothing to do and nothing to say: the choice still applies to this page, it just
    // will not survive a reload. Failing loudly here would be worse than forgetting.
  }
};


/**
 * Put the choices on the document.
 *
 * **The text size is a variable and not a `font-size` on the root**, because the product
 * sizes almost everything in `rem` and `clamp()`: multiplying the root would scale the
 * layout as well as the words, and a page whose boxes grow with its text runs out of room
 * long before the text is big enough to help.
 */
export const apply = (preferences: Preferences) => {
  const root = document.documentElement;

  root.style.setProperty('--a11y-text-scale', String(1 + preferences.textStep * 0.125));

  root.classList.toggle('a11y-contrast', preferences.highContrast);
  root.classList.toggle('a11y-links', preferences.highlightLinks);
  root.classList.toggle('a11y-still', preferences.stopMotion);
  root.classList.toggle('a11y-readable', preferences.readableFont);
};

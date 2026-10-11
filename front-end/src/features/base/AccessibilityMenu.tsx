import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { FiMinus, FiPlus, FiRotateCcw, FiX } from 'react-icons/fi'
import { MdAccessibility } from 'react-icons/md'
import { MAX_STEP, NONE, Preferences, apply, read, write } from './accessibility'
import './accessibility.css'


/**
 * The accessibility menu, and the statement it links to.
 *
 * **It is reachable by keyboard before anything else on the page**, which is the only way a
 * menu like this is worth having: somebody who needs it is frequently somebody who is not
 * using a mouse, and a widget they have to tab past the whole navigation to find is a
 * widget they will not find.
 *
 * Escape closes it, focus returns to the button that opened it, and the panel is a real
 * `dialog` so a screen reader announces it as one. None of that is decoration - a control
 * that traps you is worse than no control.
 */

const AccessibilityMenu = () => {

  const [open, setOpen] = useState(false);
  const [preferences, setPreferences] = useState<Preferences>(NONE);

  const opener = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);

  // Read once and put it on the document, so a reload looks the way he left it.
  useEffect(() => {
    const saved = read();
    setPreferences(saved);
    apply(saved);
  }, []);

  const change = (next: Preferences) => {
    setPreferences(next);
    apply(next);
    write(next);
  };

  const toggle = (key: keyof Preferences) => () =>
    change({ ...preferences, [key]: !preferences[key] } as Preferences);

  const step = (by: number) => () =>
    change({ ...preferences, textStep: Math.min(MAX_STEP, Math.max(0, preferences.textStep + by)) });

  // **Escape closes it and the focus goes home.** Leaving focus inside a panel that is no
  // longer on screen is the classic way a keyboard user gets stranded.
  useEffect(() => {
    if (!open) return;

    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
        opener.current?.focus();
      }
    };

    const onPointer = (event: MouseEvent) => {
      if (panel.current && !panel.current.contains(event.target as Node)
          && !opener.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };

    document.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onPointer);

    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('mousedown', onPointer);
    };
  }, [open]);

  const Switch = ({ on, onClick, children }:
                  { on: boolean, onClick: () => void, children: React.ReactNode }) => (
    <button type="button" className={`a11y-option ${on ? 'a11y-option-on' : ''}`}
      onClick={onClick} role="switch" aria-checked={on}>
      <span>{children}</span>
      <span className="a11y-state" aria-hidden="true">{on ? 'פועל' : 'כבוי'}</span>
    </button>
  );

  return (
    <>
      <button
        ref={opener}
        type="button"
        className="a11y-open"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label="תפריט נגישות"
        title="תפריט נגישות"
      >
        <MdAccessibility />
      </button>

      {open && (
        <div className="a11y-panel" ref={panel} role="dialog" aria-modal="false"
             aria-label="תפריט נגישות">

          <div className="a11y-head">
            <h2 className="a11y-title">נגישות</h2>
            <button type="button" className="a11y-close" onClick={() => {
              setOpen(false); opener.current?.focus();
            }} aria-label="סגירת תפריט הנגישות">
              <FiX />
            </button>
          </div>

          <div className="a11y-row">
            <span id="a11y-text-label">גודל הטקסט</span>

            <div className="a11y-stepper">
              <button type="button" onClick={step(-1)} disabled={preferences.textStep === 0}
                aria-label="הקטנת הטקסט"><FiMinus /></button>

              {/* The number is announced, so somebody who cannot see it still knows where
                  in the range they are. */}
              <span className="a11y-step-value" aria-live="polite">
                {preferences.textStep === 0 ? 'רגיל' : `+${preferences.textStep * 12.5}%`}
              </span>

              <button type="button" onClick={step(1)} disabled={preferences.textStep === MAX_STEP}
                aria-label="הגדלת הטקסט"><FiPlus /></button>
            </div>
          </div>

          <Switch on={preferences.highContrast} onClick={toggle('highContrast')}>
            ניגודיות גבוהה
          </Switch>

          <Switch on={preferences.highlightLinks} onClick={toggle('highlightLinks')}>
            הדגשת קישורים
          </Switch>

          <Switch on={preferences.stopMotion} onClick={toggle('stopMotion')}>
            עצירת אנימציות
          </Switch>

          <Switch on={preferences.readableFont} onClick={toggle('readableFont')}>
            גופן קריא יותר
          </Switch>

          <button type="button" className="a11y-reset" onClick={() => change(NONE)}>
            <FiRotateCcw /> איפוס
          </button>

          {/* **The statement is the part the regulations actually name**, and the menu is
              the most likely place somebody will look for it. */}
          <Link className="a11y-statement-link" to="/accessibility"
                onClick={() => setOpen(false)}>
            הצהרת הנגישות של האתר
          </Link>
        </div>
      )}
    </>
  )
}

export default AccessibilityMenu

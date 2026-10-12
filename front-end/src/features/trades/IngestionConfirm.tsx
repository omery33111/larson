import { useEffect, useRef } from 'react'
import Dialog from '@mui/material/Dialog'
import { FiAlertCircle } from 'react-icons/fi'
import Problem from '../base/Problem'
import { useAppDispatch, useAppSelector } from '../../app/hooks'
import {
  confirmTradesAsync, resetIngestion, selectIsConfirming, selectTradesMessage,
  selectIsConfirmOpen, selectPreview
} from './tradesSlice'
import './trades.css'



// Trades are stored as true UTC. They are rendered back in the timezone the file's clock
// came from, so the screen shows the hour the trader actually traded at - not the hour in
// whatever timezone the browser happens to sit in.
const formatDate = (value: string | null, timeZone: string) => {
  if (!value) return '—';
  return new Date(value).toLocaleDateString('he-IL', { timeZone });
};

const formatDateTime = (value: string, timeZone: string) => {
  const date = new Date(value);
  const day = date.toLocaleDateString('he-IL', { timeZone });
  const time = date.toLocaleTimeString('he-IL', { timeZone, hour: '2-digit', minute: '2-digit' });
  return `${day} ${time}`;
};

const directionLabel = (direction: string) => {
  if (direction === 'long') return 'לונג';
  if (direction === 'short') return 'שורט';
  return '—';
};

const outcomeLabel = (outcome: string) => {
  if (outcome === 'win') return 'רווח';
  if (outcome === 'loss') return 'הפסד';
  if (outcome === 'breakeven') return 'BE';
  return '—';
};



const IngestionConfirm = () => {

  const dispatch = useAppDispatch();

  // The dialog owns its own visibility through the store, so nothing is passed down as props.
  const isConfirmOpen = useAppSelector(selectIsConfirmOpen);
  const preview = useAppSelector(selectPreview);
  const isConfirming = useAppSelector(selectIsConfirming);
  const message = useAppSelector(selectTradesMessage);

  /**
   * **Where the focus goes when the gate closes, which MUI cannot do for us here.**
   *
   * Measured on the live site after the conversion: focus moved into the dialog correctly
   * and then landed on `body` when it closed - so a keyboard user who cancels is returned
   * to the top of the document and has to tab through the whole navbar to get back.
   *
   * **The cause is structural and worth knowing: this component returns `null` when the
   * gate is shut, so the dialog *unmounts* rather than closing.** MUI restores focus in its
   * close path, and that path never runs - the whole subtree simply disappears. The rules
   * panel and "my resume" stay mounted and toggle `open`, which is why they restore focus
   * and this did not. (Verified: the rules panel returns focus to the button that opened it.)
   *
   * Reshaping this one to match them would mean keeping it mounted and rendering an empty
   * paper for the length of the exit transition, so instead the restore is explicit here -
   * eight lines that depend on nothing inside MUI.
   *
   * While the gate is shut, whoever holds focus is whoever is about to open it; the listener
   * only exists in that state, so it costs nothing while the dialog is up.
   */
  const opener = useRef<HTMLElement | null>(null);
  const wasOpen = useRef(false);

  useEffect(() => {
    if (isConfirmOpen) {
      wasOpen.current = true;
      return;
    }

    if (wasOpen.current) {
      wasOpen.current = false;
      opener.current?.focus?.();
    }

    const remember = () => {
      const active = document.activeElement as HTMLElement | null;
      // `body` is not an opener - it is what we are trying to avoid being sent back to.
      if (active && active !== document.body) opener.current = active;
    };

    remember();
    document.addEventListener('focusin', remember);

    return () => document.removeEventListener('focusin', remember);
  }, [isConfirmOpen]);

  if (!isConfirmOpen || !preview) return null;

  const { report, sample, trade_file } = preview;

  const timeZone = report.source_timezone || 'UTC';

  const onConfirm = () => {
    dispatch(confirmTradesAsync(trade_file.id));
  };

  const onCancel = () => {
    dispatch(resetIngestion());
  };


  return (
    /**
     * **The gate that decides what enters the resume was the one modal in the product that
     * was not a dialog.** It was a hand-rolled `div` overlay: no `role`, so a screen reader
     * never announced that it opened; no focus move, so focus stayed wherever it was behind
     * the overlay; no focus trap, so Tab walked the page underneath it; no Escape; and no
     * focus restore on close. The three real dialogs - the chat delete, the rules panel and
     * "my resume" - get all five from MUI, and the project's own note on the first of them
     * already says MUI here is **behaviour only**. This is that note applied to the fourth.
     *
     * **The paper is stripped and `.confirm-dialog` stays exactly as it was**, so the box on
     * screen is the same box: same fill, same border, same radius, same `max-width: 720px`
     * and `max-height: 90dvh` with its own scroll. Nothing visual changed hands.
     *
     * **`zIndex: 1400` is kept, and it is not redundant.** `.confirm-backdrop` carried it to
     * sit above MUI's 1300 layer, because this gate must never end up underneath the dialog
     * that opened it - which happened once already. "My resume" also closes itself while the
     * gate is open, and the doc is explicit that those are two guards and not one. Becoming
     * a MUI dialog would have quietly dropped the second.
     *
     * `onClose` is backdrop-click and Escape together, which is what the old overlay's
     * click-through handler did minus the `stopPropagation` dance it needed to do it.
     */
    <Dialog
      open
      onClose={onCancel}
      maxWidth={false}
      /* It locks body scroll and compensates with padding; `scrollbar-gutter: stable` is
         reserved on every page, so that measurement shifts the whole layout sideways the
         moment it opens. */
      disableScrollLock
      aria-labelledby="confirm-title"
      sx={{ zIndex: 1400 }}
      slotProps={{
        paper: {
          sx: {
            width: 'min(720px, 100%)',
            margin: '1rem',
            maxHeight: 'none',
            background: 'none',
            boxShadow: 'none',
            borderRadius: 0,
            overflow: 'visible',
          },
        },
      }}
    >

      <div className="confirm-dialog">

        <h2 className="confirm-title" id="confirm-title">אישור קליטה לרזומה</h2>

        <p className="confirm-headline">
          זיהינו <b>{report.parsed}</b> עסקאות
          {report.accounts.length > 0 && <> מחשבון <b>{report.accounts.join(', ')}</b></>}
          , בטווח <b>{formatDate(report.date_from, timeZone)}</b> עד <b>{formatDate(report.date_to, timeZone)}</b>.
        </p>

        {report.mapped_by_model && (
          /* The dictionary could not read this format, so the columns below were identified
             by Larson rather than matched. That is a guess, and a guess that is about to
             become part of the record deserves to be looked at before it is accepted. */
          <p className="confirm-guessed">
            <FiAlertCircle /> הפורמט הזה לא היה מוכר, ולארסון זיהה את העמודות בעצמו.
            <b> עבור על הדוגמאות למטה</b> ואשר רק אם הן נקראו נכון.
          </p>
        )}

        <div className="confirm-stats">
          <div className="confirm-stat">
            <span className="confirm-stat-value">{report.new_count}</span>
            <span className="confirm-stat-label">חדשות</span>
          </div>
          <div className="confirm-stat">
            <span className="confirm-stat-value">{report.duplicate_count}</span>
            <span className="confirm-stat-label">כפולות</span>
          </div>
          <div className="confirm-stat">
            <span className="confirm-stat-value">{report.skipped_count}</span>
            <span className="confirm-stat-label">שורות שדולגו</span>
          </div>
        </div>

        <h3 className="confirm-section">דוגמאות מהקובץ</h3>

        <div className="confirm-table-wrap">
          <table className="confirm-table">
            <thead>
              <tr>
                <th>תאריך</th>
                <th>נכס</th>
                <th>כיוון</th>
                <th>כמות</th>
                <th>כניסה</th>
                <th>יציאה</th>
                <th>סיווג</th>
                <th>תוצאה</th>
              </tr>
            </thead>
            <tbody>
              {sample.map((trade, index) => (
                <tr key={index}>
                  <td>{formatDateTime(trade.executed_at, timeZone)}</td>
                  <td>{trade.symbol}</td>
                  <td>{directionLabel(trade.direction)}</td>
                  <td>{trade.quantity ?? '—'}</td>
                  <td>{trade.entry_price ?? '—'}</td>
                  <td>{trade.exit_price ?? '—'}</td>
                  <td className={`outcome-${trade.outcome}`}>{outcomeLabel(trade.outcome)}</td>
                  <td className={(trade.pnl ?? 0) >= 0 ? 'pnl-positive' : 'pnl-negative'}>
                    {trade.pnl ?? '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <p className="confirm-outcome-note">
          {report.outcome_derived === 0
            ? `סיווג רווח/הפסד/BE נקרא ישירות מהיומן שלך בכל ${report.outcome_from_file} העסקאות.`
            : report.outcome_from_file === 0
              ? `ליומן שלך אין עמודת סיווג, אז חישבנו אותו לפי הסכומים: עסקה מתחת ל-${report.breakeven_threshold} נחשבת BE.`
              : `${report.outcome_from_file} סיווגים נקראו מהיומן, ו-${report.outcome_derived} חושבו לפי הסכומים (סף BE: ${report.breakeven_threshold}).`}
        </p>

        <h3 className="confirm-section">מה הקובץ הזה מאפשר לנתח</h3>

        <div className="confirm-fields">
          {report.enrichment_found.map((field) => (
            <span key={field.key} className="field-chip field-chip-found">
              ✓ {field.label}
              {field.coverage !== undefined && field.coverage < (field.total ?? 0) &&
                <span className="field-chip-coverage"> ({field.coverage} מתוך {field.total})</span>}
            </span>
          ))}
        </div>

        {report.enrichment_empty.length > 0 && (
          <>
            <h3 className="confirm-section">עמודות שקיימות בקובץ אבל ריקות</h3>
            <p className="confirm-note">
              מילוי השדות האלה ביומן שלך יפתח את הניתוחים הבאים בקליטה הבאה:
            </p>
            <div className="confirm-fields">
              {report.enrichment_empty.map((field) => (
                <span key={field.key} className="field-chip field-chip-empty">◌ {field.label}</span>
              ))}
            </div>
          </>
        )}

        {report.enrichment_missing.length > 0 && (
          <>
            <h3 className="confirm-section">לא קיים בייצוא הזה</h3>
            <div className="confirm-fields">
              {report.enrichment_missing.map((field) => (
                <span key={field.key} className="field-chip field-chip-missing">✕ {field.label}</span>
              ))}
            </div>
          </>
        )}

        {report.skipped_rows.length > 0 && (
          <>
            <h3 className="confirm-section">שורות שלא נקלטו</h3>
            <ul className="confirm-skipped">
              {report.skipped_rows.map((skipped, index) => (
                <li key={index}>שורה {skipped.row}: {skipped.reason}</li>
              ))}
            </ul>
          </>
        )}

        {/* A confirm can fail too - the file is re-read from the original at this point, so
            this is where a storage fault or a parser change shows up. It was written into
            the slice and displayed nowhere, which left the gate looking like it had simply
            ignored the press. */}
        {message && <Problem>{message}</Problem>}

        <div className="confirm-actions">
          <button className="app-btn app-btn-primary" onClick={onConfirm} disabled={isConfirming}>
            {isConfirming ? 'שומר...' : `לשמור ${report.new_count} עסקאות לרזומה`}
          </button>

          <button className="app-btn app-btn-dark" onClick={onCancel} disabled={isConfirming}>
            ביטול
          </button>
        </div>

      </div>

    </Dialog>
  )
}

export default IngestionConfirm

import { useEffect, useRef, useState } from 'react'
import Dialog from '@mui/material/Dialog'
import { FiAlertTriangle, FiTrash2, FiUploadCloud, FiX } from 'react-icons/fi'
import Problem from '../base/Problem'
import { useAppDispatch, useAppSelector } from '../../app/hooks'
import {
  armDeletion, closeResume, deleteResumeAsync, disarmDeletion, getSummaryAsync,
  resetIngestion, selectConfirmResult, selectIsArmed, selectIsConfirmOpen, selectIsDeleting,
  selectIsResumeOpen, selectIsUploading, selectSummary, selectTradesMessage, uploadTradesAsync
} from './tradesSlice'
import './trades.css'



/**
 * The resume, in one place.
 *
 * A dialog and not a page, because none of this is a destination: you come here to look at
 * what Larson holds, to add to it, or to throw it away, and then you go back to what you were
 * doing. Making it a page was the mistake the upload screen made - it turned an errand into
 * somewhere you have to navigate to and back from.
 */

const formatDate = (value: string | null | undefined, timeZone = 'UTC') =>
  value ? new Date(value).toLocaleDateString('he-IL', { timeZone }) : '—';


/** The word the trader has to type to arm the delete. Nothing else enables it. */
const CONFIRM_WORD = 'מחיקה';


const ResumeDialog = () => {

  const dispatch = useAppDispatch();

  const isOpen = useAppSelector(selectIsResumeOpen);
  const isConfirmOpen = useAppSelector(selectIsConfirmOpen);
  const isArmed = useAppSelector(selectIsArmed);
  const isDeleting = useAppSelector(selectIsDeleting);
  const isUploading = useAppSelector(selectIsUploading);
  const summary = useAppSelector(selectSummary);
  const message = useAppSelector(selectTradesMessage);
  const confirmResult = useAppSelector(selectConfirmResult);

  const picker = useRef<HTMLInputElement>(null);

  const [typed, setTyped] = useState('');
  const [isDragging, setIsDragging] = useState(false);

  useEffect(() => {
    if (isOpen) {
      dispatch(getSummaryAsync());
      setTyped('');
    }
  }, [isOpen, dispatch]);

  // The resume grew, so what the dialog reports about it has to be re-read.
  useEffect(() => {
    if (confirmResult) {
      dispatch(getSummaryAsync());
    }
  }, [confirmResult, dispatch]);

  const handleFile = (file: File | undefined) => {
    if (!file) return;

    // `resetIngestion` also clears the message, so a second attempt starts clean.
    dispatch(resetIngestion());
    dispatch(uploadTradesAsync(file));
  };

  const close = () => {
    dispatch(closeResume());
    dispatch(resetIngestion());
  };

  const hasResume = summary.total_trades > 0;

  return (
    <>
      {/* Steps aside while the ingestion gate is up, rather than sitting under it. The two
          were stacking: attaching a file here opened the confirmation on top of a dialog that
          was still there, and both were on screen at once. It stays "open" - the trader comes
          straight back to it, with the new numbers already in it. */}
      <Dialog open={isOpen && !isConfirmOpen} onClose={close} disableScrollLock
        /* Named from its own heading - see the note in `RulesPanel`. */
        aria-labelledby="resume-title"
        slotProps={{
          paper: {
            sx: {
              width: 'min(520px, 100%)',
              backgroundColor: '#15181f',
              border: '1px solid #2b303b',
              borderRadius: '14px',
              color: '#e8e8e8',
              margin: '16px',
            },
          },
        }}
      >
        <div className="resume-dialog">

          <div className="resume-head">
            <h2 className="resume-title" id="resume-title">הרזומה שלי</h2>

            <button className="resume-close" onClick={close} aria-label="סגירה">
              <FiX />
            </button>
          </div>

          {hasResume ? (
            <>
              <p className="resume-lede">
                זה מה שלארסון מכיר עליך. כל ניתוח שהוא עושה נשען על זה בלבד.
              </p>

              <div className="resume-facts">
                <div className="resume-fact">
                  <span className="resume-fact-value">{summary.total_trades}</span>
                  <span className="resume-fact-label">עסקאות</span>
                </div>

                <div className="resume-fact">
                  <span className="resume-fact-value">{summary.files?.length ?? 0}</span>
                  <span className="resume-fact-label">קבצים</span>
                </div>

                <div className="resume-fact">
                  <span className="resume-fact-value">{summary.accounts?.length || 1}</span>
                  <span className="resume-fact-label">חשבונות</span>
                </div>
              </div>

              <dl className="resume-lines">
                <div className="resume-line">
                  <dt>טווח התאריכים</dt>
                  <dd>{formatDate(summary.date_from)} — {formatDate(summary.date_to)}</dd>
                </div>

                <div className="resume-line">
                  <dt>עודכן לאחרונה</dt>
                  <dd>{formatDate(summary.last_updated)}</dd>
                </div>

                {summary.symbols && summary.symbols.length > 0 && (
                  <div className="resume-line">
                    <dt>נכסים</dt>
                    <dd>{summary.symbols.join(', ')}</dd>
                  </div>
                )}
              </dl>
            </>
          ) : (
            <p className="resume-lede">
              הרזומה שלך ריק. הקובץ הראשון שתוסיף הוא הבסיס שכל מה שיבוא אחריו יימדד מולו.
            </p>
          )}

          {/* Adding is the everyday errand here, so it is the one thing with a target. */}
          <div
            className={`resume-drop ${isDragging ? 'resume-drop-active' : ''}`}
            onClick={() => picker.current?.click()}
            onDragOver={(event) => { event.preventDefault(); setIsDragging(true); }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setIsDragging(false);
              handleFile(event.dataTransfer.files?.[0]);
            }}
          >
            <FiUploadCloud className="resume-drop-icon" />

            <span className="resume-drop-text">
              <b>{isUploading ? 'קורא את הקובץ...' : hasResume ? 'הוספת עסקאות' : 'הוספת הקובץ הראשון'}</b>
              <span className="resume-drop-note">
                גרור לכאן קובץ או לחץ לבחירה · ממוזג עם דה־דופ, אחרי אישור
              </span>
            </span>

            <input
              ref={picker}
              type="file"
              className="upload-input"
              accept=".csv,.tsv,.txt,.xlsx,.xlsm,.xls,.html,.htm"
              onChange={(event) => { handleFile(event.target.files?.[0]); event.target.value = ''; }}
            />
            {/* **This had nowhere to go at all, which is worse than a toast.** `uploadTrades`,
                `confirmTrades` and `deleteResume` all write a sentence into the slice and
                nothing read it - so a file in a format we cannot read, a file missing a
                required column, or an export of individual fills was refused in complete
                silence. **And that refusal is the most useful thing this engine says**: it
                names what is missing and how to export it correctly, which is the whole
                reason the parser writes an explanation instead of an error. It belongs
                under the drop zone, where the file was handed over. */}
            {message && <Problem onClose={() => dispatch(resetIngestion())}>{message}</Problem>}
          </div>

          {hasResume && (
            <div className="resume-danger">
              {!isArmed ? (
                <div className="resume-footer">
                  <button className="resume-delete-open" onClick={() => dispatch(armDeletion())}>
                    <FiTrash2 /> מחיקת הרזומה
                  </button>

                  <button className="app-btn app-btn-dark resume-done" onClick={close}>
                    סגור
                  </button>
                </div>
              ) : (
                <>
                  <p className="resume-danger-title">
                    <FiAlertTriangle /> פעולה בלתי הפיכה
                  </p>

                  {/* Named one by one. "Delete everything" is not something anyone should
                      have to guess the meaning of. */}
                  <p className="resume-danger-body">
                    יימחקו {summary.total_trades} העסקאות שלך, {summary.files?.length ?? 0} קבצי
                    המקור שהעלית, והפרופיל הכתוב שלארסון כתב עליך. אי אפשר לשחזר.
                    <br />
                    <span className="resume-danger-keep">השיחות שלך עם לארסון יישארו.</span>
                  </p>

                  <label className="resume-danger-label" htmlFor="resume-confirm">
                    כדי לאשר, הקלד <b>{CONFIRM_WORD}</b>
                  </label>

                  <input
                    id="resume-confirm"
                    className="app-input resume-danger-input"
                    value={typed}
                    autoFocus
                    onChange={(event) => setTyped(event.target.value)}
                    aria-label={`הקלד ${CONFIRM_WORD} כדי לאשר`}
                  />

                  <div className="resume-danger-actions">
                    <button
                      className="app-btn app-btn-dark"
                      onClick={() => { dispatch(disarmDeletion()); setTyped(''); }}
                    >
                      ביטול
                    </button>

                    <button
                      className="app-btn resume-danger-go"
                      disabled={typed.trim() !== CONFIRM_WORD || isDeleting}
                      onClick={() => dispatch(deleteResumeAsync())}
                    >
                      {isDeleting ? 'מוחק...' : 'למחוק הכל'}
                    </button>
                  </div>
                </>
              )}
            </div>
          )}

        </div>
      </Dialog>

    </>
  )
}

export default ResumeDialog

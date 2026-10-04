import { useEffect, useState } from 'react'
import Dialog from '@mui/material/Dialog'
import { FiCheck, FiTrash2, FiX } from 'react-icons/fi'
import { useAppDispatch, useAppSelector } from '../../app/hooks'
import {
  closeRules, deleteRuleAsync, getRulesAsync, saveRuleAsync, selectIsRulesLoading,
  selectIsRulesOpen, selectRuleKinds, selectRules
} from './mentorSlice'
import './mentor.css'



/**
 * The rules he sets for himself.
 *
 * **This is the line between an auditor and a mentor.** The debrief has always derived rules
 * from the record - the losing buckets, each carried with the evidence that produced it - and
 * that finds what is broken, which is the harder half. What it could not do was hold him to
 * something **he decided**: "this month I do not enter before ten." Nothing stored that he
 * had decided it, so nothing could check it.
 *
 * **Every rule here is a kind and a number, never a sentence**, and that is not a limitation
 * of the form. Every figure in this product is computed in python and only narrated by the
 * model; a rule typed as prose could only be judged by the model, which would make compliance
 * an opinion. A kind and a number are judged by a loop - which is why the debrief can name
 * the trade that broke it, by date and by time.
 */


/** What the number means, per kind. A rule whose unit is ambiguous gets set wrong once and
 *  then quietly never fires - so the unit is on screen, beside the field. */
const UNITS: Record<string, string> = {
  no_before: 'שעה (0–23)',
  no_after: 'שעה (0–23)',
  min_hold: 'דקות',
  max_size: 'חוזים',
  no_revenge_within: 'דקות',
  max_trades_per_day: 'עסקאות',
  max_daily_loss: 'סכום',
};

const SETUPS_KIND = 'only_setups';


/** How a saved rule reads back, so the panel shows the commitment and not the raw number. */
const describe = (kind: string, value: number | null, setups: string) => {
  if (kind === SETUPS_KIND) return setups || '—';
  if (value === null) return '—';

  if (kind === 'no_before') return `לפני ${String(Math.trunc(value)).padStart(2, '0')}:00`;
  if (kind === 'no_after') return `אחרי ${String(Math.trunc(value)).padStart(2, '0')}:00`;

  return `${value} ${UNITS[kind] ?? ''}`.trim();
};



const RulesPanel = () => {

  const dispatch = useAppDispatch();

  const isOpen = useAppSelector(selectIsRulesOpen);
  const isLoading = useAppSelector(selectIsRulesLoading);
  const rules = useAppSelector(selectRules);
  const kinds = useAppSelector(selectRuleKinds);

  // The only local state in here, and it is the one case the convention allows: the half-typed
  // contents of the open field. It belongs to nothing but this render and is thrown away on
  // save - putting it in the store would mean a draft that outlives the panel.
  const [editing, setEditing] = useState<string>('');
  const [value, setValue] = useState<string>('');

  useEffect(() => { if (isOpen) dispatch(getRulesAsync()); }, [dispatch, isOpen]);

  const byKind = Object.fromEntries(rules.map((rule) => [rule.kind, rule]));

  const start = (kind: string) => {
    const existing = byKind[kind];
    setEditing(kind);
    setValue(kind === SETUPS_KIND
      ? (existing?.setups ?? '')
      : (existing?.number != null ? String(existing.number) : ''));
  };

  const save = (kind: string) => {
    const trimmed = value.trim();
    if (!trimmed) return;

    dispatch(saveRuleAsync(kind === SETUPS_KIND
      ? { kind, number: null, setups: trimmed }
      : { kind, number: Number(trimmed), setups: '' }));

    setEditing('');
    setValue('');
  };

  return (
    <Dialog
      open={isOpen}
      onClose={() => dispatch(closeRules())}
      maxWidth="sm"
      fullWidth
      // It locks body scroll and compensates with padding; because `scrollbar-gutter: stable`
      // is already set on every page, that measurement shifts the whole layout sideways the
      // moment the dialog opens.
      disableScrollLock
      className="rules-dialog"
    >
      <div className="rules-panel">

        <header className="rules-head">
          <div>
            <h2 className="rules-title">הכללים שלך</h2>
            <p className="rules-sub">
              מה שתקבע כאן <b>לארסון בודק מול כל קובץ שתשלח</b> — ואומר לך בשמה את העסקה
              שחרגה. כלל שלא תקבע פשוט לא נבדק.
            </p>
          </div>

          <button type="button" className="rules-close" onClick={() => dispatch(closeRules())}
                  aria-label="סגירה">
            <FiX />
          </button>
        </header>

        {isLoading && !rules.length
          ? <p className="rules-loading">טוען…</p>
          : (
            <ul className="rules-list">
              {kinds.map(({ kind, label }) => {
                const existing = byKind[kind];
                const isEditing = editing === kind;

                return (
                  <li key={kind} className={`rules-row ${existing ? 'rules-row-set' : ''}`}>

                    <div className="rules-row-main">
                      <span className="rules-label">{label}</span>

                      {existing && !isEditing &&
                        <span className="rules-value">
                          {describe(kind, existing.number, existing.setups)}
                        </span>}
                    </div>

                    {isEditing
                      ? (
                        <div className="rules-edit">
                          <input
                            className="app-input rules-input"
                            type={kind === SETUPS_KIND ? 'text' : 'number'}
                            value={value}
                            onChange={(event) => setValue(event.target.value)}
                            placeholder={kind === SETUPS_KIND ? 'breakout, pullback' : UNITS[kind]}
                            autoFocus
                            onKeyDown={(event) => { if (event.key === 'Enter') save(kind); }}
                          />

                          <button type="button" className="app-btn app-btn-primary rules-save"
                                  onClick={() => save(kind)}>
                            <FiCheck /> שמירה
                          </button>

                          <button type="button" className="rules-cancel"
                                  onClick={() => { setEditing(''); setValue(''); }}>
                            ביטול
                          </button>
                        </div>
                      )
                      : (
                        <div className="rules-actions">
                          <button type="button" className="app-btn app-btn-dark rules-set"
                                  onClick={() => start(kind)}>
                            {existing ? 'שינוי' : 'קביעה'}
                          </button>

                          {existing &&
                            <button type="button" className="rules-drop"
                                    onClick={() => dispatch(deleteRuleAsync(kind))}
                                    aria-label="מחיקת הכלל">
                              <FiTrash2 />
                            </button>}
                        </div>
                      )}
                  </li>
                );
              })}
            </ul>
          )}

        <p className="rules-foot">
          <b>כלל שקבעת ושמרת עליו הוא הדבר הראשון שלארסון יציין</b>, גם ביום מפסיד — תהליך
          ותוצאה הם שני דברים.
        </p>

      </div>
    </Dialog>
  );
};


export default RulesPanel

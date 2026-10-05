import { useEffect, useState } from 'react'
import Dialog from '@mui/material/Dialog'
import { FiCheck, FiEdit3, FiPlus, FiTrash2, FiX } from 'react-icons/fi'
import { useAppDispatch, useAppSelector } from '../../app/hooks'
import {
  closeRules, deleteRuleAsync, getRulesAsync, saveRuleAsync, selectIsRulesLoading,
  selectHasLabels, selectIsRulesOpen, selectRuleKinds, selectRules
} from './mentorSlice'
import RuleTerms from './RuleTerms'
import './mentor.css'



/**
 * The rules he sets for himself.
 *
 * **This is the line between an auditor and a mentor.** The debrief has always derived rules
 * from the record - the losing buckets, each carried with the evidence that produced it - and
 * that finds what is broken, which is the harder half. What it could not do was hold him to
 * something **he decided**. Nothing stored that he had decided it, so nothing could check it.
 *
 * **His own sentence comes first on this screen, and the structured kinds below it are
 * examples.** That ordering is the feature. "Only enter when delta is high and there is an
 * IFVG" is what a trading plan actually sounds like; "do not enter before 10:00" is one
 * narrow case of it. Leading with the narrow cases teaches him this is a menu to pick from
 * rather than a place to write his plan down, and he would never find the field that matters.
 *
 * **And his sentence is still judged by a loop, never by the model.** It is interpreted once,
 * when he saves it, into terms stored on the row; every check after that is python comparing
 * strings. So the debrief names the trade that broke it by date and by time, exactly as it
 * does for the hour rule.
 *
 * The one thing it cannot do is told to him rather than hidden: a term can only be found in
 * text a trade actually carries, so the save reports how many of his trades can answer the
 * rule at all. Without that line he reads "kept" across a year of trades that said nothing.
 */


/** What the number means, per kind. A rule whose unit is ambiguous gets set wrong once and
 *  then quietly never fires - so the unit is on screen, beside the field. */
const UNITS: Record<string, string> = {
  no_before: 'שעה (0–23)',
  no_after: 'שעה (0–23)',
  max_size: 'חוזים',
  no_revenge_within: 'דקות',
  max_trades_per_day: 'עסקאות',
  max_daily_loss: 'סכום',
};

const SETUPS_KIND = 'only_setups';
const CUSTOM_KIND = 'custom';

/**
 * Concrete, and every one of them about something he writes on the trade himself.
 *
 * **"Do not enter during news" was here and was removed, and the reason generalises.** It
 * invites him to expect the engine to know when news happened. It cannot - it reads four
 * fields he filled in and nothing else - so every tagged trade without the word "news" on
 * it would be reported as a breach of a rule he may have kept perfectly. An example that
 * teaches the wrong model of what the feature knows is worse than one example fewer.
 */
const EXAMPLES = [
  'כניסה לעסקה רק כשיש IFVG או CISD',
  'רק סטאפים שסימנתי כ-A+',
  'כניסה לעסקה רק אחרי לקיחת נזילות משמעותית',
];


/** How a saved rule reads back, so the panel shows the commitment and not the raw number. */
const describe = (kind: string, value: number | null, setups: string) => {
  if (kind === SETUPS_KIND) return setups || '—';
  if (value === null) return '—';

  if (kind === 'no_before') return `לפני ${String(Math.trunc(value)).padStart(2, '0')}:00`;
  if (kind === 'no_after') return `אחרי ${String(Math.trunc(value)).padStart(2, '0')}:00`;

  return `${value} ${UNITS[kind] ?? ''}`.trim();
};


const MAX_CUSTOM = 5;



const RulesPanel = () => {

  const dispatch = useAppDispatch();

  const isOpen = useAppSelector(selectIsRulesOpen);
  const isLoading = useAppSelector(selectIsRulesLoading);
  const rules = useAppSelector(selectRules);
  const kinds = useAppSelector(selectRuleKinds);
  const hasLabels = useAppSelector(selectHasLabels);

  // The only local state in here, and it is the one case the convention allows: the half-typed
  // contents of the open field. It belongs to nothing but this render and is thrown away on
  // save - putting it in the store would mean a draft that outlives the panel.
  const [editing, setEditing] = useState<string>('');
  const [value, setValue] = useState<string>('');

  useEffect(() => { if (isOpen) dispatch(getRulesAsync()); }, [dispatch, isOpen]);

  const mine = rules.filter((rule) => rule.kind === CUSTOM_KIND);
  const byKind = Object.fromEntries(
    rules.filter((rule) => rule.kind !== CUSTOM_KIND).map((rule) => [rule.kind, rule]));

  // The templates, with the free-text kind pulled out of the list - it has its own section
  // above, and leaving it in would offer the same thing twice.
  const templates = kinds.filter(({ kind }) => kind !== CUSTOM_KIND);

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

  /** His own sentence. `id` present means he is rewording one he already has. */
  const saveMine = (id?: number) => {
    const trimmed = value.trim();
    if (!trimmed) return;

    dispatch(saveRuleAsync(id ? { kind: CUSTOM_KIND, text: trimmed, id }
                              : { kind: CUSTOM_KIND, text: trimmed }));

    setEditing('');
    setValue('');
  };

  const writing = editing === CUSTOM_KIND || editing.startsWith('custom:');

  const field = (id?: number) => (
    <div className="rules-write">
      <textarea
        className="app-input rules-textarea"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder={EXAMPLES[0]}
        rows={2}
        maxLength={200}
        autoFocus
        onKeyDown={(event) => {
          // Enter saves, shift+Enter would be a second line - and the rule is one line by
          // the time it is stored anyway, so offering two would only mislead.
          if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); saveMine(id); }
        }}
      />

      <div className="rules-write-actions">
        <button type="button" className="app-btn app-btn-primary rules-save"
                onClick={() => saveMine(id)}>
          <FiCheck /> שמירה
        </button>

        <button type="button" className="rules-cancel"
                onClick={() => { setEditing(''); setValue(''); }}>
          ביטול
        </button>
      </div>
    </div>
  );

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
            <>

              {/* ------------- HIS PLAN, IN HIS WORDS ------------- */}
              {/* First, and visually the loudest thing in the panel. A trader who scrolls
                  past this to a list of hour rules has been told the wrong thing about what
                  the feature is. */}
              <section className="rules-mine">

                <h3 className="rules-section-title">
                  <FiEdit3 /> התנאים שלך, בניסוח שלך
                </h3>

                {/* **One line, and the numbers carry the rest.** Every earlier version of
                    this section explained the mechanism in prose - where it looks, what it
                    cannot see, what happens when nothing matches - and a feature whose
                    whole appeal is that it is simple cannot open with a page of caveats.
                    None of those facts were dropped; they moved to where they are
                    unmissable and need no reading. A count of `0` beside a term teaches
                    faster than a paragraph saying a term might find nothing. */}
                <p className="rules-section-sub">
                  תכתוב תנאי בשפה שלך — לארסון יבדוק אותו <b>מול התגיות שסימנת</b>, בכל עסקה.
                </p>

                {!hasLabels &&
                  <p className="rules-needs-tags">
                    עוד לא תייגת עסקאות, אז תנאי כזה עדיין לא ייבדק.
                    <b> התבניות המוכנות עובדות.</b>
                  </p>}

                {mine.map((rule) => (
                  <div key={rule.id} className="rules-mine-row">
                    {editing === `custom:${rule.id}`
                      ? field(rule.id)
                      : (
                        <>
                          <span className="rules-mine-text">{rule.text}</span>

                          <div className="rules-actions">
                            <button type="button" className="rules-reword"
                                    onClick={() => {
                                      setEditing(`custom:${rule.id}`);
                                      setValue(rule.text);
                                    }}>
                              ניסוח מחדש
                            </button>

                            <button type="button" className="rules-drop"
                                    onClick={() => dispatch(deleteRuleAsync(rule.id))}
                                    aria-label="מחיקת התנאי">
                              <FiTrash2 />
                            </button>
                          </div>
                        </>
                      )}

                    {/* **What it looks for, on every rule and always - and editable.**
                        The model reads "only on an FVG" and produces `fair value gap`; his
                        trades are tagged `5m fvg retracement`. Only he knows that, so the
                        line that shows the mismatch is also the one that fixes it. */}
                    {editing !== `custom:${rule.id}` && <RuleTerms rule={rule} />}
                  </div>
                ))}

                {editing === CUSTOM_KIND
                  ? field()
                  : mine.length < MAX_CUSTOM &&
                    <button type="button" className="app-btn app-btn-primary rules-add"
                            onClick={() => { setEditing(CUSTOM_KIND); setValue(''); }}>
                      <FiPlus /> {mine.length ? 'תנאי נוסף' : 'לכתוב תנאי'}
                    </button>}

                {!mine.length && !writing &&
                  <ul className="rules-examples">
                    {EXAMPLES.map((example) => (
                      <li key={example}>
                        <button type="button" className="rules-example"
                                onClick={() => { setEditing(CUSTOM_KIND); setValue(example); }}>
                          {example}
                        </button>
                      </li>
                    ))}
                  </ul>}

                {mine.length >= MAX_CUSTOM &&
                  <p className="rules-note">הגעת ל-{MAX_CUSTOM} תנאים. תחקיר שעונה על יותר
                    מזה מפסיק להיקרא.</p>}

              </section>


              {/* ------------- AND THE TEMPLATES ------------- */}
              {/* Framed as what they are: the handful the engine already knows how to judge
                  without reading anything he wrote on the trade. */}
              <section className="rules-templates">

                <h3 className="rules-section-title">או תבנית מוכנה</h3>

                <p className="rules-section-sub">
                  אלה נבדקים מול הנתונים של העסקה עצמה — שעה, כמות, רצף —
                  <b> ולכן הם עובדים גם על עסקאות שלא תיעדת בכלל.</b>
                </p>

                <ul className="rules-list">
                  {templates.map(({ kind, label }) => {
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
                                        onClick={() => dispatch(deleteRuleAsync(existing.id))}
                                        aria-label="מחיקת הכלל">
                                  <FiTrash2 />
                                </button>}
                            </div>
                          )}
                      </li>
                    );
                  })}
                </ul>
              </section>
            </>
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

import { useEffect, useRef, useState } from 'react'
import { FiCheck, FiEdit2, FiPlus, FiX } from 'react-icons/fi'
import { useAppDispatch } from '../../app/hooks'
import { RulePreview, RuleTerms as Terms, TraderRule } from '../../models/Rule'
import mentorService from './mentorAPI'
import { saveRuleAsync } from './mentorSlice'



/**
 * What the rule looks for, and the ability to correct it.
 *
 * **The read-back alone told him something was wrong without letting him fix it.** The
 * model reads "only enter on an FVG" and produces `fvg` and `fair value gap`; his trades
 * are actually tagged `5m fvg retracement`. The short term finds it by substring and the
 * long one finds nothing - so the rule works, by luck, and the next one might not. Only he
 * knows what his own tags say.
 *
 * **Two things make the edit something he can do rather than another guess:**
 *
 * 1. **Every term shows how many of his trades it currently finds**, live, as he types.
 *    `fair value gap - 0` beside `fvg - 23` needs no explanation: the dead term is visibly
 *    dead. No model behind it, and the same matcher the debrief uses - a preview computed
 *    by a second copy of the rule could disagree with the thing it is previewing.
 * 2. **His own tags are listed, and one click adds one.** The fastest correct edit is
 *    picking the label he actually writes, not typing a guess at it, and a term taken from
 *    his record cannot be wrong about what exists.
 *
 * Saving with terms attached **skips the model entirely**: he has said exactly what to look
 * for, which is better information than any reading of his sentence.
 *
 * The draft lives in local state, which is the case the convention allows - it is the
 * half-finished contents of an open editor and is thrown away on save. Preview counts are
 * the same category: transient feedback about one open row, not state the app has.
 */


const clean = (value: string) => value.trim().toLowerCase().slice(0, 40);


const RuleTerms = ({ rule }: { rule: TraderRule }) => {

  const dispatch = useAppDispatch();

  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<Terms>({ require: [], forbid: [] });
  const [preview, setPreview] = useState<RulePreview | null>(null);
  const [adding, setAdding] = useState<string>('');
  const [target, setTarget] = useState<number | 'forbid' | null>(null);

  // The preview is a round trip per keystroke otherwise, and the counts are feedback rather
  // than something he is waiting on.
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (!open) return;

    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      mentorService.previewRule(draft).then(setPreview).catch(() => setPreview(null));
    }, 350);

    return () => window.clearTimeout(timer.current);
  }, [open, draft]);

  const start = () => {
    setDraft({
      require: (rule.terms?.require ?? []).map((group) => [...group]),
      forbid: [...(rule.terms?.forbid ?? [])],
    });
    setOpen(true);
  };

  const count = (term: string) => preview?.per_term?.[term];

  const drop = (where: number | 'forbid', term: string) => {
    setDraft((current) => where === 'forbid'
      ? { ...current, forbid: current.forbid.filter((t) => t !== term) }
      : {
        ...current,
        require: current.require
          .map((group, index) => index === where ? group.filter((t) => t !== term) : group)
          .filter((group) => group.length),
      });
  };

  const add = (where: number | 'forbid', raw: string) => {
    const term = clean(raw);
    if (!term) return;

    setDraft((current) => {
      if (where === 'forbid') {
        return current.forbid.includes(term)
          ? current
          : { ...current, forbid: [...current.forbid, term] };
      }

      const require = current.require.map((group, index) =>
        index === where && !group.includes(term) ? [...group, term] : group);

      // A new row is a new condition that must also hold - "and", not "or".
      return { ...current, require: where === require.length ? [...require, [term]] : require };
    });

    setAdding('');
  };

  const save = () => {
    dispatch(saveRuleAsync({ kind: 'custom', id: rule.id, text: rule.text, terms: draft }));
    setOpen(false);
    setPreview(null);
  };

  const total = draft.require.reduce((n, g) => n + g.length, 0) + draft.forbid.length;

  // ------------- THE QUIET LINE, WHEN HE IS NOT EDITING:

  if (!open) {
    const groups = rule.terms?.require ?? [];
    const forbidden = rule.terms?.forbid ?? [];
    const nothing = !groups.length && !forbidden.length;

    return (
      <p className="rules-looking">
        <span className="rules-looking-label">מחפש על העסקה:</span>

        {/* **Each term in its own box, and the connectives outside them.** One box around
            the whole line reads as a single opaque string; boxing the terms alone makes
            them read as what they are - the tags it will go looking for - and leaves "או"
            and "וגם" as the sentence holding them together. */}
        {nothing
          ? <code>{rule.looking_for || '—'}</code>
          : (
            <span className="rules-looking-terms">
              {groups.map((group, index) => (
                <span key={index} className="rules-looking-group">
                  {index > 0 && <em className="rules-join">וגם</em>}
                  {group.map((term, position) => (
                    <span key={term}>
                      {position > 0 && <em className="rules-join">או</em>}
                      <code>{term}</code>
                    </span>
                  ))}
                </span>
              ))}

              {forbidden.length > 0 &&
                <span className="rules-looking-group">
                  <em className="rules-join">{groups.length ? 'וגם בלי' : 'בלי'}</em>
                  {forbidden.map((term, position) => (
                    <span key={term}>
                      {position > 0 && <em className="rules-join">או</em>}
                      <code className="rules-forbidden">{term}</code>
                    </span>
                  ))}
                </span>}
            </span>
          )}

        {/* **A number, not a sentence.** Every earlier version of this screen explained in
            prose what happens when a rule's words appear in none of his trades. `0` in red
            says it without being read, and the per-term breakdown is one click away in the
            editor - which is where somebody who wants the detail is already going. */}
        {typeof rule.matched === 'number' &&
          <span className={`rules-hits ${rule.matched ? '' : 'rules-hits-none'}`}>
            {rule.matched} עסקאות
          </span>}

        <button type="button" className="rules-edit-terms" onClick={start}>
          <FiEdit2 /> לדייק
        </button>
      </p>
    );
  }

  // ------------- AND THE EDITOR:

  const chips = (where: number | 'forbid', terms: string[]) => (
    <div className="terms-chips">
      {terms.map((term) => {
        const found = count(term);

        return (
          <span key={term} className={`terms-chip ${found === 0 ? 'terms-chip-dead' : ''}`}>
            <code>{term}</code>
            {/* The number is the whole point: a term finding nothing is visibly doing
                nothing, and he fixes it before saving rather than a month after. */}
            {found !== undefined &&
              <b className="terms-count">{found === 0 ? 'לא נמצא' : `${found} עסקאות`}</b>}
            <button type="button" onClick={() => drop(where, term)} aria-label="הסרת המונח">
              <FiX />
            </button>
          </span>
        );
      })}

      {target === where
        ? (
          <input
            className="app-input terms-input"
            value={adding}
            onChange={(event) => setAdding(event.target.value)}
            onBlur={() => { add(where, adding); setTarget(null); }}
            onKeyDown={(event) => {
              if (event.key === 'Enter') { event.preventDefault(); add(where, adding); }
              if (event.key === 'Escape') { setAdding(''); setTarget(null); }
            }}
            placeholder="מילה מהתגית שלך"
            autoFocus
          />
        )
        : (
          <button type="button" className="terms-add"
                  onClick={() => { setAdding(''); setTarget(where); }}>
            <FiPlus />
          </button>
        )}
    </div>
  );

  return (
    <div className="terms-editor">

      <p className="terms-help">
        אם מילה כאן לא בדיוק מה שאתה מסמן — <b>תחליף אותה.</b>
      </p>

      {draft.require.map((group, index) => (
        <div key={index} className="terms-row">
          <span className="terms-row-label">{index === 0 ? 'חייב להופיע' : 'וגם'}</span>
          {chips(index, group)}
        </div>
      ))}

      <div className="terms-row">
        <span className="terms-row-label">
          {draft.require.length ? 'וגם' : 'חייב להופיע'}
        </span>
        {chips(draft.require.length, [])}
      </div>

      {(draft.forbid.length > 0 || target === 'forbid') &&
        <div className="terms-row">
          <span className="terms-row-label">אסור שיופיע</span>
          {chips('forbid', draft.forbid)}
        </div>}

      {!draft.forbid.length && target !== 'forbid' &&
        <button type="button" className="terms-add-forbid" onClick={() => setTarget('forbid')}>
          + מילה שאסור שתופיע
        </button>}

      {/* **One click beats typing a guess**, and a label out of his own record cannot be
          wrong about what exists. */}
      {!!preview?.labels?.length &&
        <div className="terms-vocab">
          <span className="terms-vocab-title">התגיות שלך — לחיצה מוסיפה:</span>
          <div className="terms-chips">
            {preview.labels.slice(0, 24).map((label) => (
              <button key={label} type="button" className="terms-vocab-chip"
                      onClick={() => add(target === 'forbid' ? 'forbid'
                                                             : Math.max(0, draft.require.length - 1),
                                         label)}>
                {label}
              </button>
            ))}
          </div>
        </div>}

      <div className="terms-actions">
        <button type="button" className="app-btn app-btn-primary" onClick={save}
                disabled={!total}>
          <FiCheck /> שמירה
        </button>

        <button type="button" className="rules-cancel"
                onClick={() => { setOpen(false); setPreview(null); }}>
          ביטול
        </button>

        {!total && <span className="terms-warn">צריך לפחות מונח אחד.</span>}
      </div>

    </div>
  );
};


export default RuleTerms

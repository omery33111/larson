import LarsonMark, { LarsonState } from './LarsonMark'
import './larson.css'



/**
 * Larson at a size you cannot miss, saying what he is doing right now.
 *
 * The visor has carried his state since milestone 4, but only ever at 46px on the avatar
 * beside an answer - and at that size the measurement was already known: **only the colour
 * survives, the shape of the line does not.** So the one thing the product built a face for
 * was being read as a slightly different shade of a small circle, and the trader had to
 * already know the feature existed to notice it at all.
 *
 * This is the same face at 76px with the state also written in words. Two channels for one
 * fact, which is the rule everywhere else in the product: never a colour alone, and never a
 * number without its unit.
 *
 * **The words are not a caption for the picture - they are the half that carries.** A green
 * ring says something happened; "שמרת על הכללים שלך" says what. Somebody who cannot tell the
 * green from the red, or who has never seen this screen before, still gets the whole fact.
 */

const COPY: Record<LarsonState, { headline: string; note: string }> = {
  idle: {
    headline: 'לארסון מקשיב',
    note: 'מחובר לרזומה שלך',
  },

  thinking: {
    headline: 'לארסון חושב',
    note: 'קורא את מה ששלחת',
  },

  // Only the written profile uses this one: there he has just read the whole history and
  // come back with something, which is literally what the spike in the visor means.
  found: {
    headline: 'לארסון קרא אותך',
    note: 'הניתוח מוכן למטה',
  },

  success: {
    headline: 'שמרת על הכללים שלך',
    note: 'בתחקיר האחרון לא נשברה אף מגבלה',
  },

  warning: {
    headline: 'נשבר כלל',
    note: 'בתחקיר האחרון יש מה לתקן',
  },
};


type Props = {
  state: LarsonState;

  /** Only the resting line differs between the screens; everything else is his, not theirs. */
  idleNote?: string;

  className?: string;
};


const LarsonPresence = ({ state, idleNote, className = '' }: Props) => {

  const copy = COPY[state];
  const note = state === 'idle' && idleNote ? idleNote : copy.note;

  return (
    <div className={`larson-presence larson-presence-${state} ${className}`}>

      <span className="larson-presence-disc larson-disc">
        {/* Behind him rather than around him, so it reads as light he is standing in and not
            as a second border drawn on the disc. It breathes only while he is thinking -
            a glow that is always moving stops meaning anything. */}
        <span className="larson-presence-halo" aria-hidden="true" />
        <LarsonMark state={state} />
      </span>

      {/* Polite, so the change is announced after whatever the reader is on rather than
          cutting into it - and it is announced at all, which a colour never is. */}
      <span className="larson-presence-words" aria-live="polite">
        <b className="larson-presence-headline">{copy.headline}</b>
        <span className="larson-presence-note">{note}</span>
      </span>

    </div>
  )
}


/**
 * The state of the conversation as a whole, which is the state of its most recent answer.
 *
 * Exactly the rule the avatar beside a single message already uses (`visorFor` in
 * ChatMessage), applied to the last one instead of to each - so the big mark and the small
 * one can never disagree about the same answer.
 *
 * A verdict is only computed for a debrief: it comes out of checking new trades against the
 * rules the trader's own history argues for. The general chat therefore has none, and its
 * answers rest at `idle` rather than being handed an invented one.
 */
export const presenceState = (
  isBusy: boolean,
  messages: { role: string; verdict?: string }[],
): LarsonState => {

  if (isBusy) return 'thinking';

  for (let i = messages.length - 1; i >= 0; i--) {
    const row = messages[i];
    if (row.role !== 'assistant') continue;

    return row.verdict === 'broken' ? 'warning'
      : row.verdict === 'kept' ? 'success'
      : 'idle';
  }

  return 'idle';
};


export default LarsonPresence

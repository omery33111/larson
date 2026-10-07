import { FiClock } from 'react-icons/fi'
import { useAppSelector } from '../../app/hooks'
import {
  selectAnswersLeft, selectIsExhausted, selectNextAnswerAt, selectScope, selectShouldWarn
} from './usageSlice'
import './usage.css'



/**
 * How much of his allowance is left - shown only once that is worth knowing, and said in
 * the only unit he can act on.
 *
 * **The judgement call is when NOT to show it, and that half has not changed.** A meter
 * that is always on screen teaches people to ration themselves: they ask the shorter
 * question, they skip the follow-up, they stop before the thing they actually came to find
 * out. That is the precise opposite of what this product asks of a trader - the mentor only
 * works if he tells it everything. But a wall hit with no warning is worse than a meter, so
 * nothing under 90%, one quiet line above it, and a clear panel at the ceiling.
 *
 * **What changed is what the line says.** It used to read "about 10% left, some of it frees
 * up in about 40 minutes", and every part of that produced a question instead of closing
 * one: ten percent of a number he has never seen, *some* of it which might or might not buy
 * a question, and - at the ceiling - a second time for when the allowance was whole, leaving
 * him to work out which of the two he was supposed to plan around.
 *
 * Now: how many more answers, and the one moment he can ask again.
 */

/** 0 and 1 and 2 each need their own Hebrew, and "about 0 answers" needs it most. */
const counted = (n: number) => {
  if (n < 1) return 'נותרה לך פחות מתשובה אחת';
  if (n === 1) return 'נותרה לך בערך תשובה אחת';
  if (n === 2) return 'נותרו לך בערך שתי תשובות';
  return `נותרו לך בערך ${n} תשובות`;
};


/**
 * One time, said the way a person says it - and computed here rather than sent as a
 * finished sentence **because this panel sits on screen while the clock moves.** A relative
 * phrase rendered by the server is already stale by the time he reads it; his own browser's
 * clock is also the one he is looking at, so it is right wherever he happens to be.
 */
const when = (iso: string | null) => {
  if (!iso) return '';

  const moment = new Date(iso);
  const minutes = Math.max(Math.round((moment.getTime() - Date.now()) / 60000), 1);

  // Under two hours a countdown is something he can wait out; past that it is useless and
  // a clock time is something he can plan around.
  if (minutes < 60) return `בעוד כ-${minutes} דקות`;
  if (minutes < 90) return 'בעוד כשעה';
  if (minutes < 120) return 'בעוד כשעה וחצי';

  const clock = moment.toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' });

  const days = Math.round(
    (new Date(moment).setHours(0, 0, 0, 0) - new Date().setHours(0, 0, 0, 0)) / 86400000);

  if (days <= 0) return `ב-${clock}`;
  if (days === 1) return `מחר ב-${clock}`;

  // **A weekday, because the budget runs a week now.** The version this replaced only knew
  // today and tomorrow, so anything further out rendered as "tomorrow" - a wrong answer to
  // the one question this line exists to answer. Past six days a weekday name stops being
  // unambiguous, so the date comes back.
  if (days <= 6) {
    return `ביום ${moment.toLocaleDateString('he-IL', { weekday: 'long' })
      .replace('יום ', '')} ב-${clock}`;
  }

  return `ב-${moment.toLocaleDateString('he-IL', { day: '2-digit', month: '2-digit' })} בשעה ${clock}`;
};


const UsageNotice = () => {

  const shouldWarn = useAppSelector(selectShouldWarn);
  const exhausted = useAppSelector(selectIsExhausted);
  const answersLeft = useAppSelector(selectAnswersLeft);
  const nextAnswerAt = useAppSelector(selectNextAnswerAt);
  const scope = useAppSelector(selectScope);

  if (!shouldWarn && !exhausted) return null;

  // **Named correctly or not at all.** A trader held by the week who is told "today" comes
  // back tomorrow and meets the same wall - the one failure that turns a limit into a fault.
  const period = scope === 'day' ? 'להיום' : 'לשבוע הזה';

  if (exhausted) {
    return (
      <div className="usage-notice usage-notice-out" role="status">
        <FiClock className="usage-notice-icon" aria-hidden="true" />

        <span className="usage-notice-text">
          <b>{`נגמרו התשובות שלך ${period}.`}</b>
          {/* A limit with no horizon reads as a fault; the same limit with a time on it
              reads as a queue. One time, and it is the moment an answer actually fits -
              not the moment anything at all frees up. */}
          <span className="usage-notice-when">
            {nextAnswerAt ? `תוכל לשאול שוב ${when(nextAnswerAt)}` : 'נסה שוב בעוד זמן קצר'}
          </span>
        </span>
      </div>
    );
  }

  return (
    <div className="usage-notice" role="status">
      <span className="usage-notice-text">
        {counted(answersLeft)} {period}
      </span>
    </div>
  );
}

export default UsageNotice

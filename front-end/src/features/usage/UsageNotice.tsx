import { FiClock } from 'react-icons/fi'
import { useAppSelector } from '../../app/hooks'
import {
  selectFullyRenewsAt, selectIsExhausted, selectRemainingPercent, selectRenewsAt,
  selectShouldWarn
} from './usageSlice'
import './usage.css'



/**
 * How much of today's quota is left - shown only once that is worth knowing.
 *
 * **The judgement call here is when NOT to show it, and it is the whole design.** A meter
 * that is always on screen teaches people to ration themselves: they ask the shorter
 * question, they skip the follow-up, they stop before the thing they actually came to find
 * out. That is the precise opposite of what this product is asking of a trader - the mentor
 * only works if he tells it everything.
 *
 * But a wall you hit with no warning is worse than a meter. So:
 *
 *   under 75%   nothing at all
 *   over 75%    one quiet line, no bar, no colour
 *   at 100%     a clear panel that says when it comes back
 *
 * Which is also how the products that get this right behave. Nobody shows you a fuel gauge
 * until there is a reason to look at one.
 */

const partial = (iso: string | null) => {
  if (!iso) return '';

  const minutes = Math.max(Math.round((new Date(iso).getTime() - Date.now()) / 60000), 1);

  if (minutes < 60) return `חלק ממנה בעוד כ-${minutes} דקות`;

  const hours = Math.round(minutes / 60);
  return hours === 1 ? 'חלק ממנה בעוד כשעה' : `חלק ממנה בעוד כ-${hours} שעות`;
};


/**
 * When the whole allowance is his again, **with the day on it.**
 *
 * "Some of it in about three hours" is a countdown he has to keep re-reading, so the hour
 * it is whole again was added - and printed bare it then read as this evening for something
 * twenty-three hours away. **The time was right and the sentence was still misleading**,
 * which is the harder of the two to catch.
 *
 * Rendered in his own browser's clock rather than a zone chosen here: this is the clock he
 * is looking at, and it is correct wherever he happens to be.
 */
const whole = (iso: string | null) => {
  if (!iso) return '';

  const when = new Date(iso);
  const clock = when.toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' });

  const midnight = new Date();
  midnight.setHours(24, 0, 0, 0);

  return when < midnight ? `מלאה שוב ב-${clock}` : `מלאה שוב מחר ב-${clock}`;
};


const UsageNotice = () => {

  const shouldWarn = useAppSelector(selectShouldWarn);
  const exhausted = useAppSelector(selectIsExhausted);
  const remaining = useAppSelector(selectRemainingPercent);
  const renewsAt = useAppSelector(selectRenewsAt);
  const fullyRenewsAt = useAppSelector(selectFullyRenewsAt);

  if (!shouldWarn && !exhausted) return null;

  if (exhausted) {
    return (
      <div className="usage-notice usage-notice-out" role="status">
        <FiClock className="usage-notice-icon" aria-hidden="true" />

        <span className="usage-notice-text">
          {/* **No period in the words, because there are two of them now.** A trader has a
              rolling week that bounds the money and a rolling day that bounds the speed, and
              either can be the one refusing him. Calling it "daily" while the week is what
              stopped him promises tomorrow and means Thursday - and the time underneath is
              already the honest answer, whichever ceiling produced it. */}
          <b>נגמרה מכסת השימוש שלך.</b>
          {/* Said plainly, because a limit with no horizon reads as a fault and the same
              limit with a time on it reads as a queue. */}
          <span className="usage-notice-when">
            {[partial(renewsAt), whole(fullyRenewsAt)].filter(Boolean).join(' · ')
              || 'היא מתחדשת בהמשך.'}
          </span>
        </span>
      </div>
    );
  }

  return (
    <div className="usage-notice" role="status">
      <span className="usage-notice-text">
        נותרו כ-<b>{remaining}%</b> ממכסת השימוש שלך
        <span className="usage-notice-when">{partial(renewsAt)}</span>
      </span>
    </div>
  );
}

export default UsageNotice

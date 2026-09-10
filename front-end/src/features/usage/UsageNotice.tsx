import { FiClock } from 'react-icons/fi'
import { useAppSelector } from '../../app/hooks'
import {
  selectIsExhausted, selectRemainingPercent, selectRenewsAt, selectShouldWarn
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

const renewalText = (iso: string | null) => {
  if (!iso) return '';

  const minutes = Math.max(Math.round((new Date(iso).getTime() - Date.now()) / 60000), 1);

  if (minutes < 60) return `מתחדשת בהדרגה — חלק ממנה בעוד כ-${minutes} דקות`;

  const hours = Math.round(minutes / 60);
  return hours === 1
    ? 'מתחדשת בהדרגה — חלק ממנה בעוד כשעה'
    : `מתחדשת בהדרגה — חלק ממנה בעוד כ-${hours} שעות`;
};


const UsageNotice = () => {

  const shouldWarn = useAppSelector(selectShouldWarn);
  const exhausted = useAppSelector(selectIsExhausted);
  const remaining = useAppSelector(selectRemainingPercent);
  const renewsAt = useAppSelector(selectRenewsAt);

  if (!shouldWarn && !exhausted) return null;

  if (exhausted) {
    return (
      <div className="usage-notice usage-notice-out" role="status">
        <FiClock className="usage-notice-icon" aria-hidden="true" />

        <span className="usage-notice-text">
          <b>נגמרה מכסת השימוש היומית שלך.</b>
          {/* Said plainly, because a limit with no horizon reads as a fault and the same
              limit with a time on it reads as a queue. */}
          <span className="usage-notice-when">{renewalText(renewsAt) || 'היא מתחדשת בהמשך היום.'}</span>
        </span>
      </div>
    );
  }

  return (
    <div className="usage-notice" role="status">
      <span className="usage-notice-text">
        נותרו כ-<b>{remaining}%</b> ממכסת השימוש היומית שלך
        <span className="usage-notice-when">{renewalText(renewsAt)}</span>
      </span>
    </div>
  );
}

export default UsageNotice

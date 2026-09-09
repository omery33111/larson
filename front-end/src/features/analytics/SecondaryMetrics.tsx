import { FiChevronDown, FiChevronUp } from 'react-icons/fi'
import { useAppDispatch, useAppSelector } from '../../app/hooks'
import { selectCore, selectDaily, selectIsMetricsOpen, selectOverview, toggleMetrics } from './analyticsSlice'
import { money, ratio as ratioText } from './format'
import './analytics.css'



/**
 * The second tier of numbers. Real, but not what a trader should meet first - so it sits
 * collapsed directly under the three headline cards and opens on request.
 *
 * Shown or not shown, with no height animation. Both alternatives were tried and both were
 * worse: the CSS 0fr -> 1fr grid never expanded, because the overflow:hidden that trick
 * needs also zeroes the row's automatic minimum size, and MUI's Collapse stayed stuck at
 * its expanded height when closing. A plain conditional render cannot get either wrong, and
 * the row keeps its own place in the layout either way.
 *
 * The open state lives in the slice rather than a local useState, so the strip renders
 * itself and nothing is threaded through props.
 */
const SecondaryMetrics = () => {

  const dispatch = useAppDispatch();

  const isOpen = useAppSelector(selectIsMetricsOpen);
  const core = useAppSelector(selectCore);
  const daily = useAppSelector(selectDaily);
  const overview = useAppSelector(selectOverview);

  if (!core || !daily) return null;

  const currency = overview.currency || 'USD';

  return (
    <div className="secondary-metrics">

      {isOpen && (
        <div className="metric-strip">
          <div className="metric">
            <span className="metric-label">רווח נקי</span>
            <span className={`metric-value ${core.net_pnl >= 0 ? 'pnl-positive' : 'pnl-negative'}`}>
              {money(core.net_pnl, currency)}
            </span>
          </div>
          <div className="metric">
            <span className="metric-label">תוחלת לעסקה</span>
            <span className={`metric-value ${core.expectancy >= 0 ? 'pnl-positive' : 'pnl-negative'}`}>
              {money(core.expectancy, currency)}
            </span>
          </div>
          <div className="metric">
            <span className="metric-label">פקטור רווח</span>
            <span className="metric-value">{ratioText(core.profit_factor)}</span>
          </div>
          <div className="metric">
            <span className="metric-label">דראודאון מקסימלי</span>
            <span className="metric-value pnl-negative">{money(-core.max_drawdown, currency)}</span>
          </div>
          <div className="metric">
            <span className="metric-label">רצף הפסדים ארוך</span>
            <span className="metric-value">{overview.streaks?.longest_loss_streak ?? '—'}</span>
          </div>
          <div className="metric">
            <span className="metric-label">עסקאות ליום</span>
            <span className="metric-value">{daily.avg_trades_per_day}</span>
          </div>
        </div>
      )}

      <button
        className={`metrics-toggle ${isOpen ? 'metrics-toggle-open' : ''}`}
        onClick={() => dispatch(toggleMetrics())}
        aria-expanded={isOpen}
      >
        {/* The icon is swapped rather than rotated. A CSS transform on the react-icons
            <svg> did not take effect in this environment even when set inline, and two
            icons are simpler than fighting it. */}
        <span className="metrics-toggle-arrow">{isOpen ? <FiChevronUp /> : <FiChevronDown />}</span>
        {isOpen ? 'הסתרת נתונים נוספים' : 'נתונים נוספים'}
      </button>

    </div>
  )
}

export default SecondaryMetrics

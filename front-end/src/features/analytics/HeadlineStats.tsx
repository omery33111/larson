import Tooltip from '@mui/material/Tooltip'
import { AiOutlineInfoCircle } from 'react-icons/ai'
import { useAppSelector } from '../../app/hooks'
import { selectCore, selectDaily, selectOverview } from './analyticsSlice'
import { money, percent, ratio as ratioText } from './format'
import StatCard from './StatCard'
import './analytics.css'



/**
 * The three headline cards, ordered by what a trader checks first: are my days green, do I
 * win often enough, and is a win big enough to pay for the losses.
 */
const HeadlineStats = () => {

  const core = useAppSelector(selectCore);
  const daily = useAppSelector(selectDaily);
  const overview = useAppSelector(selectOverview);

  if (!core || !daily) return null;

  const currency = overview.currency || 'USD';

  const ratio = core.win_loss_ratio;

  // The split bar is proportional to the two averages, so the green share is literally the
  // share of a win inside a win-plus-loss pair.
  const winShare = core.avg_win + core.avg_loss > 0
    ? (core.avg_win / (core.avg_win + core.avg_loss)) * 100
    : 50;

  return (
    <div className="headline-grid">

      <StatCard
        label="ימים רווחיים"
        hint="אחוז ימי המסחר שנסגרו ברווח, מתוך הימים שהוכרעו. יום שנסגר בתוך טווח ה-BE שלך נחשב שטוח ולא נספר."
        value={percent(daily.green_day_rate)}
        percent={daily.green_day_rate}
        segments={[
          { value: daily.green_days, tone: 'good' },
          { value: daily.flat_days, tone: 'neutral' },
          { value: daily.red_days, tone: 'bad' },
        ]}
      />

      <StatCard
        label="אחוזי הצלחה"
        hint="אחוז העסקאות שנסגרו ברווח, מתוך העסקאות שהוכרעו. עסקאות BE לא נספרות בכלל — לא במונה ולא במכנה, בדיוק כמו ביומן שלך."
        value={percent(core.win_rate)}
        percent={core.win_rate}
        segments={[
          { value: core.wins, tone: 'good' },
          { value: core.breakeven, tone: 'neutral' },
          { value: core.losses, tone: 'bad' },
        ]}
      />

      <div className="stat-card stat-card-wide">
        <div className="stat-card-body stat-card-body-full">
          <span className="stat-card-label">
            <Tooltip title="הרווח הממוצע בעסקה מחולק בהפסד הממוצע. מעל 1 אומר שרווח טיפוסי גדול מהפסד טיפוסי." arrow enterTouchDelay={0}>
              <span className="stat-card-info"><AiOutlineInfoCircle /></span>
            </Tooltip>
            יחס רווח/הפסד ממוצע
          </span>
          <span className="stat-card-value">{ratioText(ratio)}</span>
        </div>

        <div className="split-bar-wrap">
          {/* Runtime-computed width - the one case where an inline style is correct,
              because the value is not knowable from a stylesheet. */}
          <div className="split-bar">
            <div className="split-bar-win" style={{ width: `${winShare}%` }} />
            <div className="split-bar-loss" style={{ width: `${100 - winShare}%` }} />
          </div>
          <div className="split-bar-labels">
            <span className="split-bar-win-label">{money(core.avg_win, currency)}</span>
            <span className="split-bar-loss-label">{money(-core.avg_loss, currency)}</span>
          </div>
        </div>
      </div>

    </div>
  )
}

export default HeadlineStats

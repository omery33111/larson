import { FiActivity, FiAward, FiTrendingDown } from 'react-icons/fi'
import { useAppSelector } from '../../app/hooks'
import { selectOverview } from './analyticsSlice'
import './analytics.css'



/**
 * Am I getting better?
 *
 * **The one question a mentor exists for, and until now this page could not answer it.**
 * Every figure above is computed over the whole record at once - one win rate, one
 * expectancy, one breakdown by hour - and **an aggregate over everything cannot say whether
 * it is rising.** Asked how last month compared with the one before, the page had nothing.
 *
 * All of it is computed in `analytics/periods.py`, deterministically, like every other number
 * here. Nothing on this card was written by the model.
 *
 * It renders nothing at all below two windows' worth of trades, and says so rather than
 * drawing an empty frame: **a trend line through eight trades is noise in the costume of a
 * direction**, and that is worse than silence.
 */

const DIRECTION_CLASS: Record<string, string> = {
  'משתפר': 'progress-up',
  'מדרדר': 'progress-down',
  'ללא מגמה': 'progress-flat',
};


/** Strips the markdown emphasis the engine writes for the model, which the screen renders
 *  as weight instead. One source of sentences, two readers. */
const plain = (text: string) => text.replace(/\*\*/g, '');


const Progress = () => {

  const overview = useAppSelector(selectOverview);
  const periods = (overview as any)?.periods;

  if (!periods) return null;

  if (!periods.available) {
    return (
      <section className="breakdown-card progress-card">
        <h2 className="progress-title"><FiActivity /> לאורך הזמן</h2>
        <p className="progress-empty">{periods.reason}</p>
      </section>
    );
  }

  const trend = periods['מגמה'];
  const recent = periods['השוואה_אחרונה'];
  const months = periods['חודשים'] || [];
  const records = periods['שיאים'] || [];
  const drawdown = periods['הדראודאון_הגדול'];
  const drift = periods['נדידה'] || [];
  const stopped = periods['מה_הפסקת'] || [];

  return (
    <section className="breakdown-card progress-card">

      <h2 className="progress-title"><FiActivity /> לאורך הזמן</h2>

      {/* The verdict first, because it is the answer and everything else is the working. */}
      {recent?.available &&
        <p className={`progress-verdict ${DIRECTION_CLASS[trend?.['כיוון']] ?? ''}`}>
          {plain(recent['פסיקה'])}
        </p>}

      {trend?.available &&
        <p className="progress-trend">
          <span className={`progress-pill ${DIRECTION_CLASS[trend['כיוון']] ?? ''}`}>
            {trend['כיוון']}
          </span>
          {trend.detail}
        </p>}

      {months.length > 1 &&
        <div className="progress-months">
          {months.map((month: any) => (
            <div key={month['חודש']} className="progress-month">
              <span className="progress-month-name">{month['חודש']}</span>
              <span className="progress-month-figure">{month['תוחלת']}</span>
              <span className="progress-month-meta">
                {month['עסקאות']} עסקאות · {month['אחוז_הצלחה']}
              </span>
            </div>
          ))}
        </div>}

      {records.length > 0 &&
        <div className="progress-group">
          <h3 className="progress-subtitle"><FiAward /> שיאים</h3>
          <ul className="progress-list">
            {records.map((record: any) => (
              <li key={record['שיא']}>
                <b>{record['שיא']}</b> — {record.detail}
              </li>
            ))}
          </ul>
        </div>}

      {drawdown?.available &&
        <div className="progress-group">
          <h3 className="progress-subtitle"><FiTrendingDown /> הדראודאון הגדול</h3>
          {/* A figure says how bad; a span says when, for how long, and what it started
              from - and the last of those is the only one he can act on. */}
          <p className="progress-line">{drawdown.detail}</p>
        </div>}

      {drift.length > 0 &&
        <div className="progress-group">
          <h3 className="progress-subtitle">מה נדד</h3>
          <ul className="progress-list">
            {drift.map((row: any) => (
              <li key={row['מה']}>{plain(row.detail)}</li>
            ))}
          </ul>
        </div>}

      {stopped.length > 0 &&
        <div className="progress-group">
          <h3 className="progress-subtitle">מה הפסקת</h3>
          {/* **The hardest thing to notice about yourself is what you stopped doing** - it
              leaves no row anywhere, only a gap. Only the profitable ones are listed:
              dropping a losing setup is the system working. */}
          <ul className="progress-list">
            {stopped.map((row: any) => (
              <li key={row['מה']}><b>{row['מה']}</b> — {row.detail}</li>
            ))}
          </ul>
        </div>}

    </section>
  );
};


export default Progress

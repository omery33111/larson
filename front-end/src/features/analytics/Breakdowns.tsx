import { useAppSelector } from '../../app/hooks'
import { GroupStat } from '../../models/Analytics'
import { selectBreakdowns, selectCore, selectOverview } from './analyticsSlice'
import { money, percent } from './format'
import './analytics.css'



const WEEKDAYS = ['שני', 'שלישי', 'רביעי', 'חמישי', 'שישי', 'שבת', 'ראשון'];

const GroupTable = ({ title, hint, groups, formatKey, currency }:
  { title: string, hint: string, groups: GroupStat[], formatKey?: (key: any) => string, currency: string }) => {

  const rows = groups.filter((g) => g.is_significant).slice(0, 8);

  if (rows.length === 0) return null;

  return (
    <div className="breakdown-card">
      <h3 className="breakdown-title">{title}</h3>
      <p className="breakdown-hint">{hint}</p>

      <div className="breakdown-table-wrap">
        <table className="breakdown-table">
          <thead>
            <tr>
              <th>ערך</th>
              <th>עסקאות</th>
              <th>תוחלת לעסקה</th>
              <th>אחוזי הצלחה</th>
              <th>סה"כ רווח/הפסד</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((group) => (
              <tr key={String(group.key)}>
                <td className="breakdown-key">
                  {formatKey ? formatKey(group.key) : String(group.key)}
                  {/* The ticker stays visible; the readable name sits beside it, because a
                      trader recognises "NQ" faster than the index's full name. */}
                  {!formatKey && group.label && group.label !== String(group.key) && (
                    <span className="breakdown-key-label"> · {group.label}</span>
                  )}
                </td>
                <td>{group.trades}</td>
                <td className={group.expectancy >= 0 ? 'pnl-positive' : 'pnl-negative'}>
                  {money(group.expectancy, currency)}
                </td>
                <td>{percent(group.win_rate)}</td>
                <td className={group.net_pnl >= 0 ? 'pnl-positive' : 'pnl-negative'}>
                  {money(group.net_pnl, currency)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};



/**
 * The breakdowns sit below the score and the shoulders on purpose: they are the evidence,
 * and a trader should reach them after they already know what to look for.
 */
const Breakdowns = () => {

  const breakdowns = useAppSelector(selectBreakdowns);
  const core = useAppSelector(selectCore);
  const overview = useAppSelector(selectOverview);

  if (!breakdowns || !core) return null;

  const currency = overview.currency || 'USD';

  return (
    <section className="breakdowns-section">

      {/* The tables carried no shared heading, so they read as six loose cards rather than
          as one body of evidence. */}
      <header className="section-head">
        <h2 className="section-title">סטטיסטיקות לפי תנאים</h2>
        <p className="section-subtitle">
          אותן עסקאות, חתוכות לפי תנאי אחד בכל פעם. כאן רואים איפה בדיוק היתרון — ואיפה הוא נעלם.
        </p>
      </header>

      <div className="breakdowns">

      <GroupTable
        title="לפי סטאפ"
        hint="איפה באמת נמצאת התוחלת שלך. סטאפ עם תוחלת שלילית לאורך מספיק עסקאות הוא מועמד להסרה מהתוכנית."
        groups={breakdowns.by_setup}
        currency={currency}
      />

      <GroupTable
        title="לפי טעות מתועדת"
        hint="מה כל טעות שסימנת בעצמך עולה לך בפועל."
        groups={breakdowns.by_mistake}
        currency={currency}
      />

      <GroupTable
        title="לפי יום בשבוע"
        hint="ימים חלשים חוזרים על עצמם יותר משנדמה."
        groups={breakdowns.by_weekday}
        formatKey={(key) => WEEKDAYS[Number(key)] ?? String(key)}
        currency={currency}
      />

      <GroupTable
        title="לפי משך החזקה"
        hint="האם העסקאות המהירות שלך טובות יותר מהאיטיות, או להפך."
        groups={breakdowns.by_duration}
        currency={currency}
      />

      <GroupTable
        title="לפי כיוון"
        hint="הטיה ללונג או לשורט היא אחד הדפוסים שהכי קשה לראות מבפנים."
        groups={breakdowns.by_direction}
        formatKey={(key) => (key === 'long' ? 'לונג' : key === 'short' ? 'שורט' : 'לא ידוע')}
        currency={currency}
      />

      <GroupTable
        title="לפי נכס"
        hint="פיזור על יותר מדי נכסים מדלל את היתרון."
        groups={breakdowns.by_symbol}
        currency={currency}
      />

      </div>

    </section>
  )
}

export default Breakdowns

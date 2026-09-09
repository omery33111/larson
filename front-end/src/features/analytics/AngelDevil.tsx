import { useAppSelector } from '../../app/hooks'
import { Finding } from '../../models/Analytics'
import { selectLeaks, selectStrengths } from './analyticsSlice'
import LarsonMark from '../larson/LarsonMark'
import './analytics.css'



const FindingCard = ({ finding, side }: { finding: Finding, side: 'angel' | 'devil' }) => (
  <li className={`finding finding-${side}`}>
    <h4 className="finding-title">{finding.title}</h4>
    <p className="finding-detail">{finding.detail}</p>
    <span className="finding-evidence">{finding.evidence}</span>
  </li>
);



/**
 * The two shoulders, in one frame.
 *
 * They used to be two separate cards, which read as two unrelated features. They are not:
 * they are the same trader seen from two sides, and the whole point is the comparison. One
 * card with a divider says that; two cards side by side do not.
 *
 * Each side is headed by an instruction rather than a label. "המלאך שלך" tells the trader
 * nothing to do with the information; "אל תיגע בזה" is the actual finding. Larson wearing a
 * halo or horns already says which side is which, so the words are free to carry the point.
 *
 * Every line here is arithmetic from the trades, never model output - which is why each one
 * carries the sample size it came from. The order is the ranking; no number is printed for
 * it, because the sort key is money for most findings and a heuristic weight for a few, and
 * a figure that means two different things depending on the row has no business on screen.
 */
const AngelDevil = () => {

  const strengths = useAppSelector(selectStrengths);
  const leaks = useAppSelector(selectLeaks);

  if (!strengths || !leaks) return null;

  return (
    <section className="shoulders">

      <header className="shoulders-head">
        <h3 className="shoulders-title">המלאך והשטן</h3>
        <p className="shoulders-subtitle">מה שאסור לך לגעת בו — ומה שעולה לך הכי הרבה</p>
      </header>

      <div className="shoulders-body">

        <div className="shoulder shoulder-angel">
          <header className="shoulder-head">
            <span className="shoulder-icon"><LarsonMark variant="angel" /></span>
            <div>
              <h4 className="shoulder-title">אל תיגע בזה</h4>
              <p className="shoulder-subtitle">מה שכבר עובד אצלך. שינוי כאן הוא סיכון, לא שיפור.</p>
            </div>
          </header>

          {strengths.length > 0 ? (
            <ul className="finding-list">
              {strengths.map((finding) => (
                <FindingCard key={finding.key} finding={finding} side="angel" />
              ))}
            </ul>
          ) : (
            <p className="shoulder-empty">לארסון עוד לא מצא כאן חוזקה מובהקת. צריך יותר עסקאות.</p>
          )}
        </div>

        <div className="shoulders-divider" aria-hidden="true" />

        <div className="shoulder shoulder-devil">
          <header className="shoulder-head">
            <span className="shoulder-icon"><LarsonMark variant="devil" /></span>
            <div>
              <h4 className="shoulder-title">זה מה שמדמם</h4>
              <p className="shoulder-subtitle">הדליפות היקרות שלך. כאן נמצא הכסף שאפשר להחזיר.</p>
            </div>
          </header>

          {leaks.length > 0 ? (
            <ul className="finding-list">
              {leaks.map((finding) => (
                <FindingCard key={finding.key} finding={finding} side="devil" />
              ))}
            </ul>
          ) : (
            <p className="shoulder-empty">לארסון לא מצא כאן דליפה מובהקת. זה נדיר — תמשיך ככה.</p>
          )}
        </div>

      </div>

    </section>
  )
}

export default AngelDevil

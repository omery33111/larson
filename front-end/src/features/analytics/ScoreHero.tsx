import { Gauge, gaugeClasses } from '@mui/x-charts/Gauge'
import LinearProgress from '@mui/material/LinearProgress'
import Tooltip from '@mui/material/Tooltip'
import { AiOutlineInfoCircle } from 'react-icons/ai'
import { useAppSelector } from '../../app/hooks'
import { selectCore, selectScore } from './analyticsSlice'
import './analytics.css'



const toneFor = (value: number) => {
  if (value >= 70) return 'good';
  if (value >= 45) return 'mid';
  return 'bad';
};

const COLOURS: { [key: string]: string } = {
  good: '#2fa66a',
  mid: '#f0b90b',
  bad: '#d1494e',
};

const PILLAR_HINTS: { [key: string]: string } = {
  profitability: 'נגזר מפקטור הרווח - כמה דולר הרווחת על כל דולר שהפסדת. 1.0 הוא איזון, 2.0 הוא יתרון אמיתי.',
  risk: 'יחס התאוששות: הרווח הנקי חלקי הדראודאון העמוק ביותר. מודד כמה כאב עלה לך מה שנשאר בכיס.',
  consistency: 'שילוב של אחוז הימים הירוקים ושל מידת התלות שלך ביום בודד יוצא דופן.',
  discipline: 'מתחיל מ-100 ויורד על כל דליפה התנהגותית שנמצאה: נקמה, טעויות מתועדות, יתר מסחר, גודל לא יציב ורצפי הפסד.',
  execution: 'יחס הרווח הממוצע להפסד הממוצע, בניכוי קנס אם אתה מחזיק מפסידות יותר מרווחיות.',
};



/**
 * The headline of the page. A single number is a verdict, so every pillar that built it is
 * shown next to it with its own weight and the sentence that explains it.
 */
const ScoreHero = () => {

  const score = useAppSelector(selectScore);
  const core = useAppSelector(selectCore);

  if (!score || !core) return null;

  const tone = toneFor(score.total);

  return (
    <section className="score-hero">

      <div className="score-hero-gauge">
        <Gauge
          value={score.total}
          startAngle={-140}
          endAngle={140}
          innerRadius="76%"
          outerRadius="100%"
          cornerRadius={4}
          text={() => ''}
          sx={{
            [`& .${gaugeClasses.valueArc}`]: { fill: COLOURS[tone] },
            [`& .${gaugeClasses.referenceArc}`]: { fill: '#2b303b' },
          }}
        />
        <div className="score-hero-center">
          <span className={`score-hero-number score-${tone}`}>{score.total}</span>
          <span className="score-hero-grade">{score.grade}</span>
        </div>
      </div>

      <div className="score-hero-pillars">
        <h2 className="score-hero-title">
          <Tooltip
            title="ציון משוקלל מ-0 עד 100, מחמישה עמודים. הוא לא מודד כמה הרווחת אלא כמה התהליך שלך יציב."
            arrow enterTouchDelay={0}>
            <span className="stat-card-info"><AiOutlineInfoCircle /></span>
          </Tooltip>
          ציון המסחר שלך
        </h2>

        {score.pillars.map((pillar) => (
          <div key={pillar.key} className="pillar-row">

            <div className="pillar-head">
              <span className="pillar-label">
                <Tooltip title={PILLAR_HINTS[pillar.key] || ''} arrow enterTouchDelay={0}>
                  <span className="stat-card-info"><AiOutlineInfoCircle /></span>
                </Tooltip>
                {pillar.label}
              </span>
              <span className="pillar-weight">{pillar.weight}% מהציון הכללי</span>
              <span className={`pillar-value score-${toneFor(pillar.value)}`}>{pillar.value}</span>
            </div>

            <LinearProgress
              variant="determinate"
              value={pillar.value}
              sx={{
                height: 6,
                borderRadius: 3,
                backgroundColor: '#2b303b',
                '& .MuiLinearProgress-bar': {
                  backgroundColor: COLOURS[toneFor(pillar.value)],
                  borderRadius: 3,
                },
              }}
            />

            <p className="pillar-detail">{pillar.detail}</p>
          </div>
        ))}
      </div>

    </section>
  )
}

export default ScoreHero

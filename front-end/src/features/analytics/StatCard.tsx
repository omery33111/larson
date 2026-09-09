import { Gauge, gaugeClasses } from '@mui/x-charts/Gauge'
import Tooltip from '@mui/material/Tooltip'
import { AiOutlineInfoCircle } from 'react-icons/ai'
import './analytics.css'



const GREEN = '#2fa66a';
const RED = '#d1494e';
const TRACK = '#2b303b';


interface Segment {
  value: number;
  tone: 'good' | 'neutral' | 'bad';
}


interface StatCardProps {
  label: string;
  hint: string;
  value: string;
  /** 0-100. Drives the arc. */
  percent: number;
  segments?: Segment[];
}



/**
 * The gauge card: an arc on one side, the headline number on the other, and the raw counts
 * underneath so the percentage is never shown without the sample it came from.
 */
const StatCard = ({ label, hint, value, percent, segments }: StatCardProps) => {

  const safePercent = Math.max(0, Math.min(100, percent));

  return (
    <div className="stat-card">

      <div className="stat-card-gauge">
        <Gauge
          value={safePercent}
          startAngle={-100}
          endAngle={100}
          innerRadius="72%"
          outerRadius="100%"
          cornerRadius={3}
          text={() => ''}
          sx={{
            [`& .${gaugeClasses.valueArc}`]: { fill: safePercent >= 50 ? GREEN : RED },
            [`& .${gaugeClasses.referenceArc}`]: { fill: TRACK },
          }}
        />

        {segments && (
          <div className="stat-card-segments">
            {segments.map((segment, index) => (
              <span key={index} className={`stat-segment stat-segment-${segment.tone}`}>
                {segment.value}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="stat-card-body">
        <span className="stat-card-label">
          <Tooltip title={hint} arrow enterTouchDelay={0}>
            <span className="stat-card-info"><AiOutlineInfoCircle /></span>
          </Tooltip>
          {label}
        </span>
        <span className="stat-card-value">{value}</span>
      </div>

    </div>
  )
}

export default StatCard

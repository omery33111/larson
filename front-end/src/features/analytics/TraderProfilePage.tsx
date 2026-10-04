import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAppDispatch, useAppSelector } from '../../app/hooks'
import { selectIsLogged } from '../authentication/authenticationSlice'
import AccountSelector from './AccountSelector'
import AngelDevil from './AngelDevil'
import Breakdowns from './Breakdowns'
import Progress from './Progress'
import HeadlineStats from './HeadlineStats'
import ScoreHero from './ScoreHero'
import SecondaryMetrics from './SecondaryMetrics'
import WrittenProfile from './WrittenProfile'
import {
  getOverviewAsync, selectAnalyticsIsLoading, selectCore, selectOverview
} from './analyticsSlice'
import { selectResumeVersion } from '../trades/tradesSlice'
import './analytics.css'



const formatDate = (value: string | undefined, timeZone: string) =>
  value ? new Date(value).toLocaleDateString('he-IL', { timeZone }) : '—';



/**
 * The profile page, ordered by what matters first:
 *   score -> headline stats -> the two shoulders -> written profile -> the raw breakdowns.
 * A trader who reads only the top third should already know what to do differently tomorrow.
 */
const TraderProfilePage = () => {

  const dispatch = useAppDispatch();
  const navigate = useNavigate();

  const isLogged = useAppSelector(selectIsLogged);
  const overview = useAppSelector(selectOverview);
  const core = useAppSelector(selectCore);
  const isLoading = useAppSelector(selectAnalyticsIsLoading);

  // Adding a file through the resume dialog leaves this page describing the resume as it was
  // a moment ago. Watching the version means the page re-reads itself the instant the
  // ingestion is confirmed, from wherever it was started - and after a deletion too.
  const resumeVersion = useAppSelector(selectResumeVersion);

  useEffect(() => {
    if (!isLogged) {
      navigate('/authentication/login');
      return;
    }
    dispatch(getOverviewAsync());
  }, [isLogged, resumeVersion, dispatch]);


  if (isLoading && !core) {
    return (
      <div className="app-container analytics-page">
        <p className="analytics-loading">מחשב את הנתונים שלך...</p>
      </div>
    );
  }

  if (!overview.total_trades) {
    return (
      <div className="app-container analytics-page analytics-empty">
        <h1 className="analytics-title">הרזומה שלך ריק</h1>
        <p className="analytics-subtitle">
          העלה קובץ ייצוא של עסקאות, ומכאן והלאה לארסון ידע עליך הכל.
        </p>
        {/* The mentor, not an upload form. An empty resume is not a missing file, it is a
            trader Larson has not met - and that screen is built to start the relationship. */}
        <button className="app-btn app-btn-primary" onClick={() => navigate('/mentor')}>
          להכיר את לארסון
        </button>
      </div>
    );
  }

  const timeZone = overview.timezone || 'UTC';

  return (
    <div className="app-container analytics-page">

      <header className="analytics-header">
        <h1 className="analytics-title">תעודת הזהות המסחרית</h1>

        {/* The title stays centred on its own line; what the page is computed *from* sits
            below it as a row - the scope on the right, the control that changes it on the
            left, with the width between them. */}
        <div className="analytics-header-row">
          <p className="analytics-subtitle">
            {overview.total_trades} עסקאות · {formatDate(overview.date_from, timeZone)} עד {formatDate(overview.date_to, timeZone)}
          </p>

          <AccountSelector />
        </div>
      </header>

      <WrittenProfile />

      <ScoreHero />

      <HeadlineStats />

      <SecondaryMetrics />

      {/* **Am I getting better** - the one question a mentor exists for, and the one this
          page could not answer until the periods engine existed.

          **Above the shoulders, which is the trader's own ordering and the right one.** The
          shoulders say what is strong and what bleeds across the whole record; direction is
          the frame you read both of those inside. A leak that is shrinking and a leak that
          is growing are not the same finding, and seeing the trend first is what makes them
          read differently. */}
      <Progress />

      <AngelDevil />

      <Breakdowns />

    </div>
  )
}

export default TraderProfilePage

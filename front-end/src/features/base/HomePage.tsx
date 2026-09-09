import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAppSelector } from '../../app/hooks'
import { selectIsLogged } from '../authentication/authenticationSlice'
import LarsonMark from '../larson/LarsonMark'
import './base.css';



/**
 * The front door, and only that.
 *
 * A signed-in trader never sees this page: he lands in the mentor, where the recurring loop
 * lives. A menu that links to the app is a click the product does not need, and for a new
 * account the mentor is the only screen whose empty state is designed to convert - the
 * identity card and the chat both open on "there is nothing here yet".
 */
const HomePage = () => {

  const navigate = useNavigate();

  const isLogged = useAppSelector(selectIsLogged);

  useEffect(() => {
    if (isLogged) {
      navigate('/mentor', { replace: true });
    }
  }, [isLogged, navigate]);

  if (isLogged) return null;

  return (
    <div className="app-container home-page">

      <div className="home-guest">

        <span className="home-mark">
          <LarsonMark state="idle" />
        </span>

        <h1 className="home-title">Larson</h1>

        <p className="home-subtitle">
          היומן שלך מתעד. לארסון מנתח.
        </p>

        <p className="home-pitch">
          מעלים את העסקאות, ולארסון קורא מהן מי אתה כסוחר — מה עובד לך, מה דולף,
          ומה השתנה בך מאז הפעם הקודמת.
        </p>

        <div className="home-actions">
          <button className="app-btn app-btn-primary" onClick = {() => navigate('/authentication/register')}>
            להתחיל
          </button>

          <button className="app-btn app-btn-dark" onClick = {() => navigate('/authentication/login')}>
            התחברות
          </button>
        </div>

      </div>

    </div>
  )
}

export default HomePage

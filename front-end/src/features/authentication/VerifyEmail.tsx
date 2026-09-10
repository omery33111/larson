import { useEffect, useRef, useState } from 'react'
import { FiCheckCircle, FiXCircle } from 'react-icons/fi'
import { useNavigate, useParams } from 'react-router-dom'
import { useAppDispatch } from '../../app/hooks'
import LarsonMark from '../larson/LarsonMark'
import { resendVerificationAsync, verifyEmailAsync } from './authenticationSlice'
import './authentication.css'



/**
 * Where the link in the verification mail lands.
 *
 * It fires on arrival rather than asking for a click - the trader already clicked, in his
 * mail client, and asking him to confirm the confirmation is a step that means nothing.
 */
const VerifyEmail = () => {

  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const { uid = '', token = '' } = useParams();

  const [state, setState] = useState<'working' | 'done' | 'failed'>('working');
  const [resent, setResent] = useState(false);
  const [email, setEmail] = useState('');

  // React runs effects twice in development under StrictMode. The endpoint is safe to call
  // twice - a spent link still answers "already verified" - but firing two requests for one
  // arrival is noise in the log and in the rate limit.
  const fired = useRef(false);

  useEffect(() => {
    if (fired.current) return;
    fired.current = true;

    dispatch(verifyEmailAsync({ uid, token })).then((result) => {
      setState(verifyEmailAsync.fulfilled.match(result) ? 'done' : 'failed');
    });
  }, [uid, token, dispatch]);

  return (
    <div className="app-container auth-page">

      <div className="auth-form auth-verify">

        <span className="auth-verify-mark">
          <LarsonMark state={state === 'working' ? 'thinking' : state === 'done' ? 'found' : 'warning'} />
        </span>

        {state === 'working' && (
          <>
            <h1 className="auth-title">רגע, מאשרים</h1>
            <p className="auth-subtitle">בודקים את הקישור...</p>
          </>
        )}

        {state === 'done' && (
          <>
            <h1 className="auth-title"><FiCheckCircle /> הכתובת אושרה</h1>
            <p className="auth-subtitle">החשבון פעיל. אפשר להתחבר ולהתחיל.</p>

            <div className="auth-actions">
              <button type="button" className="app-btn app-btn-primary"
                onClick={() => navigate('/authentication/login')}>
                להתחברות
              </button>
            </div>
          </>
        )}

        {state === 'failed' && (
          <>
            <h1 className="auth-title"><FiXCircle /> הקישור אינו תקף</h1>
            <p className="auth-subtitle">
              יכול להיות שפג תוקפו — הוא טוב ל-24 שעות — או שהוא נחתך באמצע בדרך מהמייל.
            </p>

            {resent ? (
              <p className="auth-note">אם הכתובת ממתינה לאישור, מייל חדש בדרך.</p>
            ) : (
              <>
                <div className="auth-field">
                  <input
                    type="email"
                    className="app-input"
                    value={email}
                    placeholder="כתובת האימייל שנרשמת איתה"
                    onChange={(event) => setEmail(event.target.value)}
                  />
                </div>

                <div className="auth-actions">
                  <button type="button" className="app-btn app-btn-primary"
                    disabled={!email.trim()}
                    onClick={() => {
                      dispatch(resendVerificationAsync(email.trim()));
                      setResent(true);
                    }}>
                    שלחו לי קישור חדש
                  </button>
                </div>
              </>
            )}
          </>
        )}

      </div>

    </div>
  )
}

export default VerifyEmail

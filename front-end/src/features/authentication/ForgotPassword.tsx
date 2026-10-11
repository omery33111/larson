import { useState } from 'react'
import { FiMail } from 'react-icons/fi'
import { useNavigate } from 'react-router-dom'
import Problem from '../base/Problem'
import { useAppDispatch, useAppSelector } from '../../app/hooks'
import { forgotPasswordAsync, selectIsLoading } from './authenticationSlice'
import './authentication.css'



/**
 * Asking for a reset link.
 *
 * **The screen says the same thing whether or not the address is registered**, because the
 * server does. An answer that distinguished the two would turn this form into a way to ask,
 * one address at a time, who the customers of a trading product are - and the screen has to
 * hold that line as carefully as the endpoint does, or it gives away what the endpoint was
 * careful not to.
 */
const ForgotPassword = () => {

  const dispatch = useAppDispatch();
  const navigate = useNavigate();

  const isLoading = useAppSelector(selectIsLoading);

  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [problem, setProblem] = useState('');

  const onSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    // **A bare `return` here was a button that did nothing.** He clicks "send a link",
    // the screen does not move, and there is no way to tell whether it worked, whether it
    // is still working, or whether he is being ignored - on the one screen reached by
    // somebody already locked out. Silence is the worst answer this form can give.
    if (!email.trim()) {
      setProblem("צריך למלא כתובת אימייל.");
      return;
    }

    setProblem('');
    dispatch(forgotPasswordAsync(email.trim()));
    setSent(true);
  };

  return (
    <div className="app-container auth-page">

      <form className="auth-form" onSubmit={onSubmit}>

        <h1 className="auth-title">
          <FiMail /> שכחתי סיסמה
        </h1>

        {sent ? (
          <>
            <p className="auth-subtitle">
              אם הכתובת רשומה אצלנו, שלחנו אליה קישור לבחירת סיסמה חדשה. הקישור תקף ל-24 שעות.
            </p>

            <p className="auth-note">
              לא הגיע כלום? בדוק בתיקיית הספאם, וּודא שזו הכתובת שנרשמת איתה.
            </p>

            <div className="auth-actions">
              <button type="button" className="app-btn app-btn-primary"
                onClick={() => navigate('/authentication/login')}>
                חזרה להתחברות
              </button>
            </div>
          </>
        ) : (
          <>
            <p className="auth-subtitle">נשלח לך קישור לבחירת סיסמה חדשה.</p>

            <div className="auth-field">
              <input
                type="email"
                className="app-input"
                name="email"
                value={email}
                placeholder="כתובת האימייל שלך"
                autoComplete="email"
                onChange={(event) => { setEmail(event.target.value); setProblem(''); }}
              />
            </div>

            {/* Under the field that produced it, and cleared by typing - the shape every
                other form in the product uses. */}
            {problem && <Problem>{problem}</Problem>}

            <div className="auth-actions">
              <button type="submit" className="app-btn app-btn-primary" disabled={isLoading}>
                שליחת קישור
              </button>

              <button type="button" className="app-btn app-btn-dark auth-secondary-btn"
                onClick={() => navigate('/authentication/login')}>
                חזרה
              </button>
            </div>
          </>
        )}

      </form>

    </div>
  )
}

export default ForgotPassword

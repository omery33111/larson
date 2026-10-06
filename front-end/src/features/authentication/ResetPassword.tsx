import { useState } from 'react'
import Problem from '../base/Problem'
import { FiKey } from 'react-icons/fi'
import { useNavigate, useParams } from 'react-router-dom'
import { useAppDispatch, useAppSelector } from '../../app/hooks'
import { resetPasswordAsync, selectIsLoading } from './authenticationSlice'
import './authentication.css'



/**
 * Choosing a new password from a mailed link.
 *
 * The two fields are compared here and the strength is judged by the server, which is the
 * right way round: a rule enforced only in the browser is not a rule, and duplicating
 * Django's validators in TypeScript would give two answers that drift apart.
 */
const ResetPassword = () => {

  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const { uid = '', token = '' } = useParams();

  const isLoading = useAppSelector(selectIsLoading);

  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [done, setDone] = useState(false);

  // Under the note that states the rules, which is exactly what the server's refusal is
  // usually about - a common password, or all digits.
  const [problem, setProblem] = useState('');

  const onSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    setProblem('');

    if (password !== confirm) {
      setProblem('שתי הסיסמאות אינן זהות.');
      return;
    }

    const result = await dispatch(resetPasswordAsync({ uid, token, password }));

    if (resetPasswordAsync.fulfilled.match(result)) {
      setDone(true);
      return;
    }

    setProblem((result.payload as string) || 'לא הצלחנו להחליף את הסיסמה. נסה שוב.');
  };

  return (
    <div className="app-container auth-page">

      <form className="auth-form" onSubmit={onSubmit}>

        <h1 className="auth-title">
          <FiKey /> סיסמה חדשה
        </h1>

        {done ? (
          <>
            <p className="auth-subtitle">הסיסמה הוחלפה.</p>

            {/* Said plainly, because it is a consequence the trader can see for himself the
                moment he checks another device - and because it is the point of the feature:
                if somebody else was inside the account, they are out now. */}
            <p className="auth-note">
              כל החיבורים האחרים לחשבון נותקו. אם היית מחובר במכשיר אחר, תצטרך להתחבר בו מחדש.
            </p>

            <div className="auth-actions">
              <button type="button" className="app-btn app-btn-primary"
                onClick={() => navigate('/authentication/login')}>
                להתחברות
              </button>
            </div>
          </>
        ) : (
          <>
            <p className="auth-subtitle">בחר סיסמה חדשה לחשבון שלך.</p>

            <div className="auth-field">
              <input
                type="password"
                className="app-input"
                name="password"
                value={password}
                placeholder="סיסמה חדשה"
                onChange={(event) => { setPassword(event.target.value); setProblem(''); }}
              />
            </div>

            <div className="auth-field">
              <input
                type="password"
                className="app-input"
                name="confirm"
                value={confirm}
                placeholder="וידוא סיסמה"
                onChange={(event) => { setConfirm(event.target.value); setProblem(''); }}
              />
            </div>

            <p className="auth-note">
              לפחות 8 תווים, ולא סיסמה נפוצה או כולה ספרות.
            </p>

            {problem && <Problem>{problem}</Problem>}

            <div className="auth-actions">
              <button type="submit" className="app-btn app-btn-primary" disabled={isLoading}>
                החלפת הסיסמה
              </button>
            </div>
          </>
        )}

      </form>

    </div>
  )
}

export default ResetPassword

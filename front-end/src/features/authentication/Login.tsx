import { useEffect, useState } from 'react'
import Problem from '../base/Problem'
import { FaSignInAlt } from 'react-icons/fa'
import { useAppSelector, useAppDispatch } from "../../app/hooks";
import { useNavigate } from 'react-router-dom';
import {
  clearVerificationPrompt, googleLoginAsync, loginAsync, resendVerificationAsync, reset,
  selectIsError, selectIsSuccess, selectNeedsVerification, selectUnverifiedEmail
} from "./authenticationSlice"
import GoogleSignIn, { GOOGLE_ENABLED } from './GoogleSignIn';
import './authentication.css';



const Login = () => {
  const [formData, setFormData] = useState({
    username: '',
    password: '',
  });

  const { username, password } = formData;

  const navigate = useNavigate();
  const dispatch = useAppDispatch();

  const isSuccess = useAppSelector(selectIsSuccess);
  const isError = useAppSelector(selectIsError);
  const needsVerification = useAppSelector(selectNeedsVerification);
  const unverifiedEmail = useAppSelector(selectUnverifiedEmail);

  const [resent, setResent] = useState(false);

  // **Under the two fields it is about.** A wrong password belongs beside the password, not
  // in a corner that times out while he is still looking at the form.
  const [problem, setProblem] = useState<string>('');

  // **Off by default, and that is the decision.** Ticking it keeps the session after the
  // browser closes; leaving it means the session dies with the tab. On a borrowed machine the
  // safe answer has to be the one that happens when nobody touches anything.
  const [remember, setRemember] = useState(false);

  useEffect(() =>
  {
      if (isSuccess)
      {
        dispatch(reset())
        navigate("/")
      }

  }, [isSuccess, navigate, dispatch])

  useEffect(() => {
    // An unconfirmed address is not a wrong password, and saying it is would send the trader
    // off to check a password that was right all along. It gets the panel below instead,
    // which carries the one thing he can actually do about it.
    if (isError && !needsVerification) {
      setProblem('הפרטים שגויים. נסה שוב.');
    }
  }, [isError, needsVerification]);

  const onChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    // The reason described what was typed a moment ago; once he edits, it describes nothing.
    setProblem('');
    setFormData((prevState) => ({
      ...prevState,
      [name]: value,
    }));
  };

  const onSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    const passwordRegex = /^[^\s]+$/;

    if (!passwordRegex.test(password)) {
        setProblem("הסיסמה לא יכולה להכיל רווחים.");
        return;
    }

    // `loginTime` is written by the API once the pair comes back, because until then it is
    // not known which storage the session belongs in.
    const userData = { username, password, remember };

    dispatch(clearVerificationPrompt());
    setResent(false);
    setProblem('');
    dispatch(loginAsync(userData));
  };


  return (
    <div className="app-container auth-page">

      <form className="auth-form" onSubmit={onSubmit}>

        <h1 className="auth-title">
          <FaSignInAlt /> התחברות
        </h1>

        <p className="auth-subtitle">הזן פרטי משתמש</p>

        <div className="auth-field">
          <input
            type="text"
            className="app-input"
            id="username"
            name="username"
            value={username}
            placeholder="שם משתמש"
            onChange={onChange}
          />
        </div>

        <div className="auth-field">
          <input
            type="password"
            className="app-input"
            id="password"
            name="password"
            value={password}
            placeholder="סיסמה"
            onChange={onChange}
          />
        </div>

        {needsVerification && (
          <div className="auth-prompt">
            {resent ? (
              <>שלחנו מייל אישור חדש ל-<b>{unverifiedEmail}</b>. פתח אותו וחזור לכאן.</>
            ) : (
              <>
                הסיסמה נכונה — רק כתובת המייל עוד לא אושרה.
                {' '}
                <button
                  type="button"
                  className="auth-prompt-link"
                  onClick={() => {
                    dispatch(resendVerificationAsync(unverifiedEmail));
                    setResent(true);
                  }}
                >
                  שלחו לי את המייל שוב
                </button>
              </>
            )}
          </div>
        )}

        <label className="auth-remember">
          <input
            type="checkbox"
            checked={remember}
            onChange={(e) => setRemember(e.target.checked)}
          />
          <span>להישאר מחובר בדפדפן הזה</span>
        </label>

        {problem && !needsVerification && <Problem>{problem}</Problem>}

        <div className="auth-actions">
          <button type="submit" className="app-btn app-btn-primary">
            התחברות
          </button>

          <button type="button" className="app-btn app-btn-dark auth-secondary-btn" onClick = {() => navigate('/authentication/register')}>
            הרשמה
          </button>
        </div>

        <button type="button" className="auth-forgot"
          onClick={() => navigate('/authentication/forgot')}>
          שכחת סיסמה?
        </button>

        {/* Below the form and not above it: the password is how most accounts here were
            opened, and putting a third party's button first suggests otherwise. */}
        {GOOGLE_ENABLED && (
          <>
            <div className="auth-divider"><span>או</span></div>

            <GoogleSignIn
              oneTap
              text="signin_with"
              onCredential={(credential) => dispatch(googleLoginAsync({ credential, remember }))}
            />
          </>
        )}

      </form>

    </div>
  )
}

export default Login

import { useEffect, useState } from 'react'
import { FaSignInAlt } from 'react-icons/fa'
import { useAppSelector, useAppDispatch } from "../../app/hooks";
import { useNavigate } from 'react-router-dom';
import {
  clearVerificationPrompt, loginAsync, resendVerificationAsync, reset, selectIsError,
  selectIsSuccess, selectNeedsVerification, selectUnverifiedEmail
} from "./authenticationSlice"
import { toast } from 'react-toastify';
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

  useEffect(() =>
  {
      if (isSuccess)
      {
        dispatch(reset())
        navigate("/")
      }

  }, [isSuccess, navigate, dispatch])

  useEffect(() => {
    // An unconfirmed address is not a wrong password, and a red toast saying it is would
    // send the trader off to check a password that was right all along. It gets the panel
    // below instead, which carries the one thing he can actually do about it.
    if (isError && !needsVerification) {
      toast.error('הפרטים שגויים. נסה שוב.');
    }
  }, [isError, needsVerification]);

  const onChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prevState) => ({
      ...prevState,
      [name]: value,
    }));
  };

  const onSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    const passwordRegex = /^[^\s]+$/;

    if (!passwordRegex.test(password)) {
        toast.error("הסיסמה לא יכולה להכיל רווחים.");
        return;
    }

    const userData = {
        username,
        password,
    };

    const submitTime = new Date().toISOString();
    localStorage.setItem('loginTime', submitTime);

    dispatch(clearVerificationPrompt());
    setResent(false);
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

      </form>

    </div>
  )
}

export default Login

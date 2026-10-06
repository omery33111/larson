import { useState } from 'react';
import Problem from '../base/Problem'
import { AiOutlineUser } from 'react-icons/ai';
import { FiMail } from 'react-icons/fi';
import { useNavigate } from 'react-router-dom';
import { Link } from 'react-router-dom';
import { useAppDispatch } from "../../app/hooks";
import { googleLoginAsync, registerAsync, resendVerificationAsync, reset } from "./authenticationSlice";
import GoogleSignIn, { GOOGLE_ENABLED } from './GoogleSignIn';
import './authentication.css';



const Register = () => {
    const [formData, setFormData] = useState
    ({
        username: "",
        password: "",
        password2: "",
        email: ""
    })
    const { username, password, password2, email } = formData


    // Registration no longer ends at the login form: the account is not usable until the
    // address is confirmed, so sending him to a form that would reject him is the one thing
    // this screen must not do.
    const [sent, setSent] = useState(false)
    const [resent, setResent] = useState(false)

    // **Unticked to begin with, and the server refuses a registration without it.** Consent
    // that the product assumed rather than asked for is not consent, and this one matters
    // here in particular: the privacy policy is where it says that a summary of the trading
    // record is sent to a third party to answer him.
    const [accepted, setAccepted] = useState(false)

    // **Under the tick box and the buttons, which is where all four of these are about.**
    // Cleared on the next edit, because a reason describing what was typed a moment ago
    // describes nothing once he changes it.
    const [problem, setProblem] = useState<string>('')

    const navigate = useNavigate()
    const dispatch = useAppDispatch()



    const onChange = (event: any) => {
      setProblem('')
      setFormData((PreviousState) => ({ ...PreviousState, [event.target.name]: event.target.value}))
    }

    const onSubmit = (event: any) => {
      event.preventDefault();

      // Only the two things the browser is the right place to check: a length floor so an
      // obviously empty attempt does not cost a round trip, and whether the two fields agree
      // - which the server cannot know. **Everything else is the server's to judge.** The
      // rule used to be stricter here than in Django, so a perfectly good passphrase with no
      // capital letter was refused by the browser and never reached the validators that
      // would have accepted it.
      setProblem('');

      if (!accepted) {
        setProblem("צריך לאשר את תנאי השימוש ומדיניות הפרטיות.");
      } else if (password.length < 8) {
        setProblem("הסיסמה צריכה להיות באורך 8 תווים לפחות.");
      } else if (password !== password2) {
        setProblem("הסיסמאות לא זהות.");
      } else {
        const userData = {
          username,
          email,
          password,
          accepted_terms: accepted
        };

        // **The server's own sentence, under the form.** It is the one that names which
        // field it objected to - a password on Django's common list, an address that cannot
        // receive mail, a username already taken - and none of that is knowable here.
        dispatch(registerAsync(userData))
          .unwrap()
          .then(() => {
            // "isSuccess" is shared with the login flow, so it is cleared before the
            // screen changes - otherwise the login page would see it and jump home.
            dispatch(reset())
            setSent(true)
          })
          .catch((reason: string) => {
            setProblem(reason || "לא הצלחנו ליצור את החשבון. נסה שוב.")
          });
      }
    }

    if (sent) {
      return (
        <div className="app-container auth-page">
          <div className="auth-form auth-verify">

            <h1 className="auth-title"><FiMail /> בדוק את המייל</h1>

            <p className="auth-subtitle">
              שלחנו קישור אישור ל-<b>{email}</b>. פתח אותו כדי להפעיל את החשבון.
            </p>

            <p className="auth-note">
              הקישור תקף ל-24 שעות. לא הגיע? בדוק בתיקיית הספאם.
            </p>

            {resent ? (
              <p className="auth-note">שלחנו שוב.</p>
            ) : (
              <div className="auth-actions">
                <button type="button" className="app-btn app-btn-dark"
                  onClick={() => { dispatch(resendVerificationAsync(email)); setResent(true); }}>
                  שלחו שוב
                </button>
              </div>
            )}

            <button type="button" className="auth-forgot"
              onClick={() => navigate('/authentication/login')}>
              כבר אישרתי — למסך ההתחברות
            </button>

          </div>
        </div>
      )
    }

    return (
        <div className="app-container auth-page">

          <form className="auth-form" onSubmit={onSubmit}>

            <h1 className="auth-title">
              <AiOutlineUser /> הרשמה
            </h1>

            <div className="auth-field">
              <input
                type="text"
                className="app-input"
                id="username"
                name="username"
                value={username}
                placeholder="הזן שם משתמש"
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

            <div className="auth-field">
              <input
                type="password"
                className="app-input"
                id="password2"
                name="password2"
                value={password2}
                placeholder="וידוא סיסמה"
                onChange={onChange}
              />
            </div>

            <div className="auth-field">
              <input
                type="text"
                className="app-input"
                id="email"
                name="email"
                value={email}
                placeholder="כתובת אימייל"
                onChange={onChange}
              />
            </div>

            <label className="auth-consent">
              <input
                type="checkbox"
                checked={accepted}
                onChange={(event) => setAccepted(event.target.checked)}
              />
              <span>
                קראתי ואני מאשר את <Link to="/terms">תנאי השימוש</Link> ואת{' '}
                <Link to="/privacy">מדיניות הפרטיות</Link>.
              </span>
            </label>

            {problem && <Problem>{problem}</Problem>}

            <div className="auth-actions">
              <button type="submit" className="app-btn app-btn-primary">
                הירשמות
              </button>

              <button type="button" className="app-btn app-btn-dark auth-secondary-btn" onClick = {() => navigate('/authentication/login')}>
                כבר יש לי חשבון
              </button>
            </div>

            {GOOGLE_ENABLED && (
              <>
                <div className="auth-divider"><span>או</span></div>

                {/* The same tick box governs this route: pressing it without accepting is
                    refused here, rather than opening an account whose consent nobody
                    recorded. */}
                <GoogleSignIn
                  text="signup_with"
                  onCredential={(credential) => {
                    if (!accepted) {
                      setProblem("צריך לאשר את תנאי השימוש ומדיניות הפרטיות.");
                      return;
                    }

                    dispatch(googleLoginAsync({ credential, remember: false }))
                      .then((action) => {
                        if (action.meta.requestStatus === "fulfilled") navigate("/mentor");
                      });
                  }}
                />
              </>
            )}

          </form>

        </div>
      )
}



export default Register

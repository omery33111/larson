import { useEffect, useState } from 'react'
import axios from 'axios'
import { Link, useParams } from 'react-router-dom'
import LarsonMark from '../larson/LarsonMark'
import { unsubscribeURL } from '../../endpoints/endpoints'
import './authentication.css'



/**
 * Where the unsubscribe link in the weekly mail lands.
 *
 * **Public on purpose, and it has to be.** Asking somebody to sign in before he can stop
 * receiving email is how a sender earns a spam complaint - and a complaint lands on the
 * domain that also carries the verification and password-reset mail. **An email nobody can
 * stop is a threat to account recovery for people who never received it.**
 *
 * It acts on load rather than offering a button. The link was already the decision; a page
 * that asks "are you sure" after he clicked "stop emailing me" is a page arguing with him.
 */

const Unsubscribe = () => {

  const { token } = useParams();

  const [state, setState] = useState<'working' | 'done' | 'failed'>('working');

  useEffect(() => {
    let cancelled = false;

    const run = async () => {
      try {
        await axios.post(unsubscribeURL, { token });
        if (!cancelled) setState('done');
      } catch {
        if (!cancelled) setState('failed');
      }
    };

    run();

    return () => { cancelled = true; };
  }, [token]);

  return (
    <div className="app-container auth-page">
      <div className="auth-card unsubscribe-card">

        <div className="unsubscribe-mark">
          <LarsonMark state={state === 'failed' ? 'warning' : 'idle'} />
        </div>

        {state === 'working' &&
          <p className="unsubscribe-text">רגע…</p>}

        {state === 'done' && (
          <>
            <h1 className="auth-title">הסיכום השבועי בוטל</h1>
            <p className="unsubscribe-text">
              <b>לא תקבל יותר את המייל השבועי.</b> מיילים על החשבון עצמו — אימות, איפוס סיסמה
              והודעות אבטחה — ממשיכים להישלח, כי בלעדיהם אין דרך לחזור לחשבון.
            </p>
            <p className="unsubscribe-text unsubscribe-quiet">
              שינית את דעתך? אפשר להחזיר את זה בכל רגע בעמוד החשבון.
            </p>
          </>
        )}

        {state === 'failed' && (
          <>
            <h1 className="auth-title">הקישור לא תקף</h1>
            <p className="unsubscribe-text">
              ייתכן שהוא נפתח כבר או שעבר יותר מדי זמן. <b>אפשר לבטל את הסיכום גם מעמוד
              החשבון</b>, אחרי התחברות.
            </p>
          </>
        )}

        <Link to="/" className="app-btn app-btn-dark unsubscribe-home">חזרה לאתר</Link>

      </div>
    </div>
  );
};


export default Unsubscribe

import { useEffect, useRef, useState } from 'react'
import { FiAlertTriangle, FiDownload, FiKey, FiUser } from 'react-icons/fi'
import { useNavigate } from 'react-router-dom'
import { toast } from 'react-toastify'
import { useAppDispatch, useAppSelector } from '../../app/hooks'
import {
  changePasswordAsync, deleteAccountAsync, exportDataAsync, selectIsLogged, selectIsLoading,
  selectUser
} from './authenticationSlice'
import './authentication.css'



// The same standard the resume deletion already sets: a word typed by hand, not a click.
const CONFIRM_WORD = 'מחיקה';


/**
 * What a person is entitled to do with their own record: take it, or end it.
 *
 * The two live on one screen because they are one decision seen from both sides, and because
 * putting the export next to the deletion is what makes the deletion safe to offer at all -
 * **the last thing shown before the irreversible button is the way to keep a copy.**
 */
const AccountPage = () => {

  const dispatch = useAppDispatch();
  const navigate = useNavigate();

  const isLogged = useAppSelector(selectIsLogged);
  const isLoading = useAppSelector(selectIsLoading);
  const userName = useAppSelector(selectUser);

  const [isArmed, setIsArmed] = useState(false);
  const [typed, setTyped] = useState('');
  const [password, setPassword] = useState('');

  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');

  // Deleting the account also makes `isLogged` false, and without this the guard below
  // would read that as "not signed in" and send him to a login form a second after he
  // deleted the thing he would be logging into. The front page is where that ends.
  const deleting = useRef(false);

  useEffect(() => {
    if (!isLogged && !deleting.current) navigate('/authentication/login');
  }, [isLogged, navigate]);

  const download = async () => {
    const result = await dispatch(exportDataAsync());

    if (exportDataAsync.rejected.match(result)) {
      toast.error(result.payload as string);
      return;
    }

    toast.success('הקובץ ירד. הוא כולל את כל מה שלארסון מחזיק עליך.');
  };

  const changePassword = async () => {
    if (next !== confirm) {
      toast.error('שתי הסיסמאות אינן זהות.');
      return;
    }

    const result = await dispatch(changePasswordAsync({ currentPassword: current, password: next }));

    if (changePasswordAsync.rejected.match(result)) {
      toast.error(result.payload as string);
      return;
    }

    setCurrent(''); setNext(''); setConfirm('');
    toast.success('הסיסמה הוחלפה. שאר החיבורים לחשבון נותקו.');
  };

  const erase = async () => {
    deleting.current = true;
    const result = await dispatch(deleteAccountAsync(password));

    if (deleteAccountAsync.rejected.match(result)) {
      deleting.current = false;
      toast.error(result.payload as string);
      return;
    }

    toast.success('החשבון נמחק.');
    navigate('/');
  };

  return (
    <div className="app-container account-page">

      <h1 className="account-title"><FiUser /> החשבון שלי</h1>
      <p className="account-subtitle">מחובר בתור <b>{userName}</b></p>


      {/* ------------- TAKING IT ------------- */}
      <section className="account-card">
        <h2 className="account-card-title"><FiDownload /> הורדת הנתונים שלי</h2>

        <p className="account-card-body">
          קובץ JSON אחד עם כל מה שהמערכת מחזיקה עליך: העסקאות שלך, הקבצים שהעלית,
          הפרופיל הכתוב, וכל השיחות עם לארסון — שלו ושלך.
        </p>

        <button className="app-btn app-btn-dark" onClick={download} disabled={isLoading}>
          הורדת הכל
        </button>
      </section>


      {/* ------------- CHANGING THE KEY ------------- */}
      <section className="account-card">
        <h2 className="account-card-title"><FiKey /> החלפת סיסמה</h2>

        <p className="account-card-body">
          {/* Said up front, because it is a consequence and not a footnote: somebody who
              changes a password because he suspects a break-in needs to know the other side
              is out, and somebody who is just tidying up needs to know his phone will ask
              him to sign in again. */}
          החלפת הסיסמה מנתקת את כל שאר החיבורים לחשבון — כאן תישאר מחובר.
        </p>

        <label className="account-label" htmlFor="account-current">הסיסמה הנוכחית</label>
        <input id="account-current" type="password" className="app-input" value={current}
          placeholder="סיסמה נוכחית"
          onChange={(event) => setCurrent(event.target.value)} />

        <label className="account-label" htmlFor="account-next">סיסמה חדשה</label>
        <input id="account-next" type="password" className="app-input" value={next}
          placeholder="לפחות 8 תווים"
          onChange={(event) => setNext(event.target.value)} />

        <label className="account-label" htmlFor="account-confirm-new">וידוא הסיסמה החדשה</label>
        <input id="account-confirm-new" type="password" className="app-input" value={confirm}
          placeholder="שוב, לוודא"
          onChange={(event) => setConfirm(event.target.value)} />

        <div className="account-danger-actions">
          <button className="app-btn app-btn-primary"
            disabled={!current || !next || !confirm || isLoading}
            onClick={changePassword}>
            החלפת הסיסמה
          </button>
        </div>
      </section>


      {/* ------------- ENDING IT ------------- */}
      <section className="account-card account-danger">
        <h2 className="account-card-title account-danger-title">
          <FiAlertTriangle /> מחיקת החשבון
        </h2>

        {!isArmed ? (
          <>
            <p className="account-card-body">
              מוחק את החשבון ואת כל מה שמתחתיו — לצמיתות ובלי אפשרות שחזור.
            </p>

            <p className="account-card-note">
              כדאי להוריד קודם את הנתונים שלך. אחרי המחיקה אין מאיפה לקחת אותם.
            </p>

            <button className="app-btn app-btn-dark account-danger-arm"
              onClick={() => setIsArmed(true)}>
              אני רוצה למחוק את החשבון
            </button>
          </>
        ) : (
          <>
            <p className="account-card-body">
              יימחקו: <b>העסקאות שלך</b>, <b>קבצי המקור שהעלית</b>, <b>הפרופיל הכתוב</b>,
              <b> כל השיחות עם לארסון</b>, ו<b>המשתמש עצמו</b>. אי אפשר לשחזר.
            </p>

            <label className="account-label" htmlFor="account-password">הסיסמה שלך</label>
            <input
              id="account-password"
              type="password"
              className="app-input"
              value={password}
              placeholder="סיסמה"
              onChange={(event) => setPassword(event.target.value)}
            />

            <label className="account-label" htmlFor="account-confirm">
              הקלד <b>{CONFIRM_WORD}</b> כדי לאשר
            </label>
            <input
              id="account-confirm"
              type="text"
              className="app-input"
              value={typed}
              placeholder={CONFIRM_WORD}
              onChange={(event) => setTyped(event.target.value)}
            />

            <div className="account-danger-actions">
              <button className="app-btn app-btn-dark"
                onClick={() => { setIsArmed(false); setTyped(''); setPassword(''); }}>
                ביטול
              </button>

              <button
                className="app-btn account-danger-go"
                disabled={typed.trim() !== CONFIRM_WORD || !password || isLoading}
                onClick={erase}
              >
                למחוק את החשבון
              </button>
            </div>
          </>
        )}
      </section>

    </div>
  )
}

export default AccountPage

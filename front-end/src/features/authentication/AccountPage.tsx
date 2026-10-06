import { useEffect, useRef, useState } from 'react'
import { FiAlertTriangle, FiDownload, FiKey, FiLogOut, FiMail, FiUser } from 'react-icons/fi'
import { useNavigate } from 'react-router-dom'
import { toast } from 'react-toastify'
import Problem from '../base/Problem'
import { useAppDispatch, useAppSelector } from '../../app/hooks'
import {
  changePasswordAsync, deleteAccountAsync, emailPrefsAsync, endSessionsAsync, exportDataAsync,
  getIndexAsync, saveEmailPrefsAsync, selectEmailPrefs, selectGoogleEmail, selectHasPassword,
  selectIsLogged, selectIsLoading, selectUser
} from './authenticationSlice'
import GoogleSignIn from './GoogleSignIn'
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
  const emailPrefs = useAppSelector(selectEmailPrefs);
  const navigate = useNavigate();

  const isLogged = useAppSelector(selectIsLogged);
  const isLoading = useAppSelector(selectIsLoading);
  const userName = useAppSelector(selectUser);

  // **Which doors this account actually has.** An account opened with Google has no password,
  // and two of the three cards below are built on the assumption that one exists.
  const hasPassword = useAppSelector(selectHasPassword);
  const googleEmail = useAppSelector(selectGoogleEmail);

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

  // Asked for on arrival rather than assumed from the session: the answer decides which
  // version of two whole cards is drawn.
  useEffect(() => { dispatch(getIndexAsync()); dispatch(emailPrefsAsync()); }, [dispatch]);

  /**
   * **Keyed by card, not one string for the page.** Four unrelated actions live here -
   * download, end other sessions, change password, delete the account - and a reason from
   * one of them rendered under another is worse than no reason at all. The key is the card
   * it belongs to, so only that card can show it.
   *
   * Successes stay as toasts: "the file downloaded" is a passing confirmation with nothing
   * to act on, and pinning it to a card would leave it sitting there afterwards.
   */
  const [problem, setProblem] = useState<{ where: string, text: string } | null>(null);

  const failed = (where: string, text: string) =>
    setProblem({ where, text: text || 'הפעולה לא הצליחה. נסה שוב.' });

  const reason = (where: string) => problem?.where === where
    ? <Problem>{problem.text}</Problem>
    : null;

  const download = async () => {
    setProblem(null);
    const result = await dispatch(exportDataAsync());

    if (exportDataAsync.rejected.match(result)) {
      failed('export', result.payload as string);
      return;
    }

    toast.success('הקובץ ירד. הוא כולל את כל מה שלארסון מחזיק עליך.');
  };

  const changePassword = async () => {
    setProblem(null);

    if (next !== confirm) {
      failed('password', 'שתי הסיסמאות אינן זהות.');
      return;
    }

    const result = await dispatch(changePasswordAsync({ currentPassword: current, password: next }));

    if (changePasswordAsync.rejected.match(result)) {
      failed('password', result.payload as string);
      return;
    }

    setCurrent(''); setNext(''); setConfirm('');
    toast.success('הסיסמה הוחלפה. שאר החיבורים לחשבון נותקו.');
  };

  const endEverywhereElse = async () => {
    setProblem(null);
    const result = await dispatch(endSessionsAsync());

    if (endSessionsAsync.rejected.match(result)) {
      failed('sessions', result.payload as string);
      return;
    }

    toast.success('כל שאר החיבורים לחשבון נותקו. כאן נשארת מחובר.');
  };

  const erase = async (googleCredential = '') => {
    setProblem(null);
    deleting.current = true;
    const result = await dispatch(deleteAccountAsync({ password, googleCredential }));

    if (deleteAccountAsync.rejected.match(result)) {
      deleting.current = false;
      failed('delete', result.payload as string);
      return;
    }

    toast.success('החשבון נמחק.');
    navigate('/');
  };

  return (
    <div className="app-container account-page">

      <h1 className="account-title"><FiUser /> החשבון שלי</h1>
      <p className="account-subtitle">
        מחובר בתור <b>{userName}</b>
        {googleEmail && <> · מקושר לחשבון גוגל <b>{googleEmail}</b></>}
      </p>


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

        {reason('export')}
      </section>


      {/* ------------- CLOSING THE OTHER DOORS ------------- */}
      {/* Separate from the password card on purpose. **The situation this is for does not
          always involve a password** - a session left open on somebody else's laptop, a phone
          that was lost - and making him change a password he is happy with in order to close
          a door is a tax on doing the safe thing. */}
      {/* ------------- WHAT MAY BE SENT TO HIM ------------- */}
      {/* **Opt-out and not opt-in**, and a toggle that exists even though the law probably
          does not require one: somebody who cannot turn an email off clicks "spam" instead,
          and a complaint lands on the domain that carries the verification mail. */}
      <section className="account-card">
        <h2 className="account-card-title"><FiMail /> מה נשלח אליך במייל</h2>

        <p className="account-card-body">
          <b>הסיכום השבועי נשלח ביום ראשון, ורק כשיש מה לסכם.</b> שבוע שלא העלית בו עסקאות —
          לארסון שותק. אחרי פער ארוך תגיע <b>תזכורת אחת</b>, לא אחת לשבוע.
        </p>

        <label className="account-toggle">
          <input
            type="checkbox"
            checked={emailPrefs.weekly_digest}
            onChange={(event) =>
              dispatch(saveEmailPrefsAsync({ weekly_digest: event.target.checked }))}
          />
          <span>לקבל את הסיכום השבועי</span>
        </label>

        <label className="account-toggle">
          <input
            type="checkbox"
            checked={emailPrefs.product_news}
            onChange={(event) =>
              dispatch(saveEmailPrefsAsync({ product_news: event.target.checked }))}
          />
          <span>לקבל עדכונים על המוצר ועל שינויי מחיר</span>
        </label>

        <p className="account-card-note">
          מיילים על החשבון עצמו — אימות, איפוס סיסמה והודעות אבטחה — נשלחים בכל מקרה.
          <b> בלעדיהם אין דרך לחזור לחשבון.</b>
        </p>
      </section>

      <section className="account-card">
        <h2 className="account-card-title"><FiLogOut /> ניתוק החיבורים האחרים</h2>

        <p className="account-card-body">
          מנתק את החשבון מכל דפדפן ומכל מכשיר אחר שמחוברים אליו עכשיו — כאן תישאר מחובר.
          שימושי אם נשארת מחובר במחשב של מישהו אחר, או אם אבד לך מכשיר.
        </p>

        <button className="app-btn app-btn-dark" onClick={endEverywhereElse} disabled={isLoading}>
          לנתק את כל השאר
        </button>

        {reason('sessions')}
      </section>


      {/* ------------- CHANGING THE KEY ------------- */}
      <section className="account-card">
        <h2 className="account-card-title"><FiKey /> {hasPassword ? 'החלפת סיסמה' : 'קביעת סיסמה'}</h2>

        {!hasPassword ? (
          /* **The reset mail rather than a field here**, and that is the security of it: a
             session that only holds an access token must not be able to fit the account with
             a second, permanent door. The mail proves the mailbox all over again. */
          <>
            <p className="account-card-body">
              החשבון הזה נפתח עם גוגל ואין לו סיסמה, אז אין מה להחליף. אפשר להמשיך להתחבר
              עם גוגל תמיד — ואם בכל זאת תרצה גם סיסמה, נשלח אליך קישור למייל.
            </p>

            <button className="app-btn app-btn-dark"
              onClick={() => navigate('/authentication/forgot')}>
              לקבוע סיסמה דרך המייל
            </button>
          </>
        ) : (
        <>
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
          onChange={(event) => { setCurrent(event.target.value); if (problem?.where === 'password') setProblem(null); }} />

        <label className="account-label" htmlFor="account-next">סיסמה חדשה</label>
        <input id="account-next" type="password" className="app-input" value={next}
          placeholder="לפחות 8 תווים"
          onChange={(event) => { setNext(event.target.value); if (problem?.where === 'password') setProblem(null); }} />

        <label className="account-label" htmlFor="account-confirm-new">וידוא הסיסמה החדשה</label>
        <input id="account-confirm-new" type="password" className="app-input" value={confirm}
          placeholder="שוב, לוודא"
          onChange={(event) => { setConfirm(event.target.value); if (problem?.where === 'password') setProblem(null); }} />

        {reason('password')}

        <div className="account-danger-actions">
          <button className="app-btn app-btn-primary"
            disabled={!current || !next || !confirm || isLoading}
            onClick={changePassword}>
            החלפת הסיסמה
          </button>
        </div>
        </>
        )}
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

            {hasPassword && (
              <>
                <label className="account-label" htmlFor="account-password">הסיסמה שלך</label>
                <input
                  id="account-password"
                  type="password"
                  className="app-input"
                  value={password}
                  placeholder="סיסמה"
                  onChange={(event) => setPassword(event.target.value)}
                />
              </>
            )}

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

            {/* An account with no password proves itself with the thing it does have. The
                button appears only once the word is typed, because Google's own button cannot
                be disabled and an armed control that ignores you is worse than one that is
                not there yet. */}
            {!hasPassword && typed.trim() === CONFIRM_WORD && (
              <p className="account-card-note">
                לאישור אחרון, התחבר שוב עם חשבון הגוגל המקושר. המחיקה תתבצע מיד אחרי זה.
              </p>
            )}

            {reason('delete')}

            <div className="account-danger-actions">
              <button className="app-btn app-btn-dark"
                onClick={() => { setIsArmed(false); setTyped(''); setPassword(''); setProblem(null); }}>
                ביטול
              </button>

              {hasPassword ? (
                <button
                  className="app-btn account-danger-go"
                  disabled={typed.trim() !== CONFIRM_WORD || !password || isLoading}
                  onClick={() => erase()}
                >
                  למחוק את החשבון
                </button>
              ) : (
                typed.trim() === CONFIRM_WORD && (
                  <GoogleSignIn
                    text="continue_with"
                    onCredential={(credential) => erase(credential)}
                  />
                )
              )}
            </div>
          </>
        )}
      </section>

    </div>
  )
}

export default AccountPage

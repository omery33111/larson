import { useEffect } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { IconContext } from 'react-icons';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import { useAppDispatch, useAppSelector } from './app/hooks';
import { isRemembered, readItem } from './app/session';
import { logoutAsync, selectIsLogged } from './features/authentication/authenticationSlice';
import MyFooter from './features/navigators/MyFooter';
import MyNavbar from './features/navigators/MyNavbar';
import AccessibilityMenu from './features/base/AccessibilityMenu';
import IngestionConfirm from './features/trades/IngestionConfirm';
import './index.css';



// **The page title for every screen, and a default that says something.**
//
// This was a `switch` whose default was a bare "Larson", and seven screens fell through it:
// forgot password, the two policy pages, the account page, the three that arrive from an
// email - verify, reset, unsubscribe - and the 404 itself. Every tab read the same word,
// which makes a row of open tabs and the browser's own history useless, and the one page
// that most needs to say what happened said nothing at all.
const EXACT: Record<string, string> = {
  '/': 'Larson - המנטור שלך',
  '/mentor': 'Larson - המנטור',

  // **"צ'אט" and not "שיחה עם לארסון".** The nav bar was renamed and the title was left
  // behind, so the tab and the link he clicked to get there disagreed on the screen's name.
  '/chat': "Larson - צ'אט",

  '/profile': 'Larson - תעודת הזהות המסחרית',
  '/account': 'Larson - החשבון שלי',
  '/authentication/login': 'Larson - התחברות',
  '/authentication/register': 'Larson - הרשמה',
  '/authentication/forgot': 'Larson - שכחתי סיסמה',
  '/terms': 'Larson - תנאי שימוש',
  '/privacy': 'Larson - מדיניות פרטיות',
  '/accessibility': 'Larson - הצהרת נגישות',
};

// These three arrive from an email and carry a token in the path, so they match on prefix.
const PREFIXED: [string, string][] = [
  ['/authentication/verify/', 'Larson - אימות כתובת המייל'],
  ['/authentication/reset/', 'Larson - סיסמה חדשה'],
  ['/email/unsubscribe/', 'Larson - הסרה מרשימת התפוצה'],
];


function ScrollToTop() {
  const { pathname } = useLocation();

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);

  return null;
}

function App() {
  const dispatch = useAppDispatch();

  const { pathname } = useLocation();

  const isLogged = useAppSelector(selectIsLogged);

  // **Skipped entirely for a session the trader asked to keep.** This cap is what made
  // "stay signed in" meaningless before: whatever the refresh token was good for, the app
  // signed him out after a day anyway. Unticked, the session is in `sessionStorage` and dies
  // with the tab in any case, and the cap is the belt to that pair of braces.
  useEffect(() => {
    if (isRemembered()) return;

    const storedloginTime = readItem('loginTime');

    if (storedloginTime && isLogged) {
      const submitTime = new Date(storedloginTime);
      const currentTime = new Date();

      // Calculate the time difference in milliseconds
      const timeDifference = currentTime.getTime() - submitTime.getTime();

      // Convert 24 hours to milliseconds
      const twentyFourHoursInMillis = 24 * 60 * 60 * 1000;

      if (timeDifference > twentyFourHoursInMillis) {
        dispatch(logoutAsync());
      }
    }
  }, [pathname, isLogged]);

  useEffect(() => {
    const prefixed = PREFIXED.find(([at]) => pathname.startsWith(at));

    document.title = EXACT[pathname] ?? prefixed?.[1] ?? 'Larson - הדף לא נמצא';
  }, [pathname]);


  // The two conversation screens are the ones where the page itself must not scroll - the
  // thread scrolls inside them. That needs a definite height at the top of the chain, and
  // `min-height` cannot give one: with it, the shell is sized by its own content and pushes
  // the footer down.
  const isFullHeight = pathname === '/chat' || pathname === '/mentor';

  return (
    /*
     * **Every icon in the product is decorative, and now says so.** `react-icons` renders a
     * bare `<svg>`, which a screen reader walks into and reads as a graphic with no name -
     * four of them on the login screen alone. They all sit beside the words they illustrate,
     * so the right answer is for them to be silent, and one provider is the whole fix.
     * An icon that genuinely carries meaning on its own overrides this with its own label.
     */
    <IconContext.Provider value={{ attr: { 'aria-hidden': 'true', focusable: 'false' } }}>
    <div className={`App ${isFullHeight ? 'App-fullheight' : ''}`}>
      <ToastContainer />

      {/*
        * **WCAG 2.4.1, and it was missing.** Every page opens with the same navigation, so
        * a keyboard or screen-reader user had to walk the whole bar on every single screen
        * before reaching anything. It is invisible until focused, which is the first thing
        * Tab reaches.
        */}
      <a className="skip-link" href="#main">דילוג לתוכן הראשי</a>

      <MyNavbar />

      <main className="app-main" id="main" tabIndex={-1}>
        <ScrollToTop />
        <Outlet />
      </main>

      <MyFooter />

      <AccessibilityMenu />

      {/* Mounted once for the whole app. It is driven entirely by the store and takes no
          props, so every screen that starts an ingestion - the mentor, the resume dialog -
          shares this one. Two of them on the same page meant two stacked overlays. */}
      <IngestionConfirm />
    </div>
    </IconContext.Provider>
  );
}

export default App;

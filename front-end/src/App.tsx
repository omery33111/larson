import { useEffect } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import { useAppDispatch, useAppSelector } from './app/hooks';
import { isRemembered, readItem } from './app/session';
import { logoutAsync, selectIsLogged } from './features/authentication/authenticationSlice';
import MyFooter from './features/navigators/MyFooter';
import MyNavbar from './features/navigators/MyNavbar';
import IngestionConfirm from './features/trades/IngestionConfirm';
import './index.css';


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
    let title = 'Larson';

    switch (pathname) {
      case '/':
        title = 'Larson - המנטור שלך';
        break;
      case '/authentication/login':
        title = 'Larson - התחברות';
        break;
      case '/authentication/register':
        title = 'Larson - הרשמה';
        break;
      case '/profile':
        title = 'Larson - תעודת הזהות המסחרית';
        break;
      case '/chat':
        title = 'Larson - שיחה עם לארסון';
        break;
      case '/mentor':
        title = 'Larson - המנטור';
        break;

      default:
        title = 'Larson';
        break;
    }

    document.title = title;
  }, [pathname]);


  // The two conversation screens are the ones where the page itself must not scroll - the
  // thread scrolls inside them. That needs a definite height at the top of the chain, and
  // `min-height` cannot give one: with it, the shell is sized by its own content and pushes
  // the footer down.
  const isFullHeight = pathname === '/chat' || pathname === '/mentor';

  return (
    <div className={`App ${isFullHeight ? 'App-fullheight' : ''}`}>
      <ToastContainer />
      <MyNavbar />

      <main className="app-main">
        <ScrollToTop />
        <Outlet />
      </main>

      <MyFooter />

      {/* Mounted once for the whole app. It is driven entirely by the store and takes no
          props, so every screen that starts an ingestion - the mentor, the resume dialog -
          shares this one. Two of them on the same page meant two stacked overlays. */}
      <IngestionConfirm />
    </div>
  );
}

export default App;

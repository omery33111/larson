import { useEffect, useState } from 'react'
import Menu from '@mui/material/Menu'
import MenuItem from '@mui/material/MenuItem'
import { Link, useNavigate } from 'react-router-dom'
import { AiOutlineUser } from 'react-icons/ai'
import { FaSignInAlt, FaSignOutAlt } from 'react-icons/fa'
import {
  FiActivity, FiBarChart2, FiChevronDown, FiDatabase, FiMessageSquare
} from 'react-icons/fi'
import { useAppDispatch, useAppSelector } from '../../app/hooks'
import { logoutAsync, selectIsLogged, selectUser } from '../authentication/authenticationSlice'
import { getMentorAsync, selectResumeState } from '../mentor/mentorSlice'
import ResumeDialog from '../trades/ResumeDialog'
import { openResume, selectResumeVersion } from '../trades/tradesSlice'
import LarsonMark from '../larson/LarsonMark'
import './navigators.css';



// A trader who traded yesterday is not behind, so the nudge stays quiet until there is a real
// gap between the trading he has done and the trading he has told Larson about.
const STALE_AFTER_DAYS = 2;


const MyNavbar = () => {

  const dispatch = useAppDispatch();
  const navigate = useNavigate();

  const isLogged = useAppSelector(selectIsLogged);
  const userName = useAppSelector(selectUser);
  const resume = useAppSelector(selectResumeState);
  const resumeVersion = useAppSelector(selectResumeVersion);

  // An anchor element, not application state, which is why it stays local - the same call the
  // account selector makes.
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);

  // Read once per session. It is what lets the nudge live in the navbar, which is the only
  // place it can be seen from every screen.
  useEffect(() => {
    if (isLogged) {
      dispatch(getMentorAsync());
    }
    // Re-read after every change to the resume, so the days counter is never left saying
    // something that stopped being true the moment a file went in.
  }, [isLogged, resumeVersion, dispatch]);

  const close = () => setAnchor(null);

  const go = (path: string) => {
    close();
    navigate(path);
  };

  const handleLogout = async () => {
    close();
    await dispatch(logoutAsync());
    navigate('/');
  };

  const isStale = resume.total_trades > 0
    && resume.days_since !== null
    && resume.days_since >= STALE_AFTER_DAYS;

  return (
    <nav className="my-navbar">

      <div className="app-container my-navbar-container">

        <Link to = "/" className="my-navbar-brand">
          <span className="larson-mark">
            <LarsonMark state="idle" />
          </span>
          <span className="my-navbar-wordmark">Larson</span>
        </Link>

        {isLogged ? (
          <>
            {/* Where you talk to Larson. Two surfaces, one of them primary - everything about
                you and your data lives under your name instead of competing here. */}
            <div className="my-navbar-nav">

              <Link to = "/mentor" className="my-navbar-link my-navbar-primary"
                title="סוגרים איתו סשן מסחר: שולחים את העסקאות האחרונות ומקבלים תחקיר">
                <FiActivity /> המנטור

                {isStale && (
                  <span className="my-navbar-badge">{resume.days_since} ימים</span>
                )}
              </Link>

              <Link to = "/chat" className="my-navbar-link"
                title="צ'אט חופשי עם לארסון על הנתונים שלך — כמה שיחות במקביל">
                <FiMessageSquare /> צ'אט
              </Link>

              <Link to = "/profile" className="my-navbar-link"
                title="הציון, המדדים והפילוחים שלך">
                <FiBarChart2 /> תעודת הזהות
              </Link>

            </div>

            <button
              className="my-navbar-account"
              onClick={(event) => setAnchor(event.currentTarget)}
              aria-label="החשבון שלי"
            >
              <span className="my-navbar-avatar">{userName?.charAt(0).toUpperCase()}</span>
              <span className="my-navbar-name">{userName}</span>
              <FiChevronDown className="my-navbar-chevron" />
            </button>

            {/* MUI for the behaviour only - anchoring, focus, Escape. Everything visible is
                the product's own CSS, set at the call site the way the account selector
                already does it. */}
            <Menu
              anchorEl={anchor}
              open={Boolean(anchor)}
              onClose={close}
              /* MUI locks body scroll while a menu is open, which removes the page scrollbar
                 and shifts everything sideways by its width. */
              disableScrollLock
              anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
              transformOrigin={{ vertical: 'top', horizontal: 'center' }}
              slotProps={{
                paper: {
                  sx: {
                    minWidth: 236,
                    backgroundColor: '#15181f',
                    border: '1px solid #2b303b',
                    borderRadius: '12px',
                    color: '#e8e8e8',
                    marginTop: '6px',
                  },
                },
              }}
            >
              {/* His name is the way to his own page, which is what a name in a navbar should
                  do. The line under it is what Larson currently knows. */}
              <MenuItem
                onClick={() => go('/profile')}
                sx={{ flexDirection: 'column', alignItems: 'flex-start', gap: '2px', py: 1.1 }}
              >
                <span className="my-navbar-menu-title">תעודת הזהות המסחרית</span>
                <span className="my-navbar-menu-sub">
                  {resume.total_trades > 0
                    ? `הרזומה: ${resume.total_trades} עסקאות`
                    : 'הרזומה עדיין ריק'}
                </span>
              </MenuItem>

              <div className="my-navbar-menu-line" />

              {/* A dialog rather than a page. Looking at what Larson holds, adding to it or
                  throwing it away are errands, not destinations - the upload screen turned
                  one into somewhere you have to navigate to and back from. */}
              <MenuItem
                onClick={() => { close(); dispatch(openResume()); }}
                className="my-navbar-menu-item"
              >
                <FiDatabase /> הרזומה שלי
              </MenuItem>

              <div className="my-navbar-menu-line" />

              <MenuItem onClick={handleLogout} className="my-navbar-menu-item">
                <FaSignOutAlt /> התנתקות
              </MenuItem>
            </Menu>

            <ResumeDialog />
          </>
        ) : (
          <div className="my-navbar-nav">
            <Link to = "/authentication/login" className="my-navbar-link">
              <FaSignInAlt /> התחברות
            </Link>

            <Link to = "/authentication/register" className="my-navbar-link my-navbar-primary">
              <AiOutlineUser /> הרשמה
            </Link>
          </div>
        )}

      </div>

    </nav>
  )
}

export default MyNavbar

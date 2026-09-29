import { Component, ErrorInfo, ReactNode } from 'react';
import LarsonMark from '../larson/LarsonMark';
import './base.css';



/**
 * The one thing standing between a thrown render and a white page.
 *
 * **React unmounts the entire tree when a render throws and nothing catches it.** Not the
 * screen - the application: navbar, footer and every route, replaced by nothing at all. The
 * trader is left with a blank window, no message, and no way back other than knowing to
 * reload; and because the tree is gone, the toast layer that would have said something is
 * gone with it.
 *
 * It is a class because that is the only form React gives this. There is no hook for it.
 */

type Props = { children: ReactNode };
type State = { failed: boolean };


class ErrorBoundary extends Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Written down where somebody can find it. The error monitor picks console errors up, and
    // without this line a crash that a trader reports as "it went white" has nothing behind it.
    console.error('Render failed:', error, info.componentStack);
  }

  render() {
    if (!this.state.failed) return this.props.children;

    return (
      <div className="app-container crash-page">
        {/* His warning face, because this is the product failing and the product has one. */}
        <div className="crash-mark">
          <LarsonMark state="warning" />
        </div>

        <h1 className="crash-title">משהו נשבר כאן</h1>

        <p className="crash-body">
          זו תקלה אצלנו ולא משהו שעשית. <b>הנתונים שלך לא נפגעו</b> — העסקאות, הפרופיל
          והשיחות נשמרים בשרת ולא בדף הזה.
        </p>

        {/* **The one place in this product where reloading the page is correct**, and the
            single exception to the rule that nothing here reloads. The component tree is the
            thing that failed; a router navigation would reuse it, and the state that produced
            the crash would still be sitting in it. */}
        <button className="app-btn app-btn-primary" onClick={() => window.location.reload()}>
          לטעון מחדש
        </button>
      </div>
    );
  }
}


export default ErrorBoundary;

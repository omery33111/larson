import { FiX } from 'react-icons/fi'



/**
 * What went wrong, where it went wrong.
 *
 * **Every error in the product renders through this, and none of them is a toast.** A toast
 * fails an error message in three ways at once, and the trader hit all three on the same
 * sentence: it lands in a corner far from the thing it is about, it arrives after the screen
 * has moved on, and it leaves on a timer while he is still reading it.
 *
 * Two shapes. A reason under a field needs no close button - editing the field answers it,
 * and the form clears it on the next keystroke. A reason about the page has nothing to edit,
 * so it carries one; without that it would sit above the composer for the rest of the
 * session.
 */


const Problem = ({ children, onClose }: { children: React.ReactNode, onClose?: () => void }) => (
  <p className={`app-problem ${onClose ? 'app-problem-wide' : ''}`} role="alert">
    <span>{children}</span>

    {onClose &&
      <button type="button" className="app-problem-close" onClick={onClose} aria-label="סגירה">
        <FiX />
      </button>}
  </p>
);


export default Problem

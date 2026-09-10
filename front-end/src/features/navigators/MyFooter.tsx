import { Link } from 'react-router-dom'
import './navigators.css';



const MyFooter = () => {

  return (
    <footer className="my-footer">

      <div className="app-container">

        <p className="my-footer-text">
          Larson — היומן שלך מתעד. המנטור שלך מבין.
        </p>

        <p className="my-footer-disclaimer">
          המערכת היא כלי אנליטי־חינוכי בלבד ואינה מהווה ייעוץ השקעות.
        </p>

        {/* The disclaimer above is the one-line version. These are where the same claim is
            made in full, and where the trader can check what leaves the server. */}
        <nav className="my-footer-links">
          <Link to="/terms">תנאי שימוש</Link>
          <span aria-hidden="true">·</span>
          <Link to="/privacy">מדיניות פרטיות</Link>
        </nav>

      </div>

    </footer>
  )
}

export default MyFooter

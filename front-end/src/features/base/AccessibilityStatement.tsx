import { Link } from 'react-router-dom'
import './legal.css'
import './accessibility.css'


/**
 * הצהרת נגישות — the artefact the regulations actually name.
 *
 * **This is the part that is required, and the floating menu is not.** תקנה 35 of תקנות
 * שוויון זכויות לאנשים עם מוגבלות (התאמות נגישות לשירות) points at ת"י 5568, which is WCAG
 * 2.0 AA applied to the site itself; the statement is how a visitor learns what was done,
 * what is still not done, and who to tell when they hit something.
 *
 * **It says what is not accessible too, and that is deliberate.** A statement that claims
 * everything is perfect is the one nobody believes and the one a regulator reads hardest.
 * Naming the known gaps, with a way to report a new one, is both the honest version and
 * the one the regulations are actually asking for.
 */

/**
 * **One constant, in one file**, read by this page and by the privacy policy.
 *
 * It is a Google Group and not a personal mailbox, and the reason is that this address is
 * published three times over: on Google's own consent screen, here as the accessibility
 * coordinator, and in the privacy policy as the route for a data request. A group keeps
 * all three pointing at a working address without putting a personal inbox on the page,
 * and mail to it still lands in that inbox - the owner is subscribed to every message.
 *
 * **"Who can post" on the group is "anyone on the web", and that is the setting the whole
 * thing turns on.** Google's default is members only, which would have bounced every
 * stranger who wrote to any of the three - silently, from their side.
 */
export const ACCESSIBILITY_CONTACT = 'larson-support@googlegroups.com';


const AccessibilityStatement = () => (
  <div className="app-container legal-page">

    <h1 className="legal-title">הצהרת נגישות</h1>
    <p className="legal-updated">עודכן לאחרונה: אוקטובר 2026</p>

    <section className="legal-section">
    <h2>המחויבות שלנו</h2>
    <p>
      Larson נבנה כך שאפשר יהיה להשתמש בו גם עם מקלדת בלבד, גם עם קורא מסך, וגם כשצריך
      טקסט גדול יותר או ניגודיות גבוהה יותר. אנחנו פועלים לעמידה ב<b>תקן הישראלי ת"י 5568</b>{' '}
      ברמה AA, המבוסס על הנחיות <span dir="ltr">WCAG 2.0</span> של ארגון <span dir="ltr">W3C</span>.
    </p>

    </section>

    <section className="legal-section">
    <h2>מה נעשה באתר</h2>
    <ul>
      <li>ניווט מלא במקלדת, כולל קישור דילוג ישירות לתוכן בראש כל עמוד.</li>
      <li>סימון מיקוד נראה לעין על כל כפתור, קישור ושדה שאפשר להגיע אליהם במקלדת.</li>
      <li>תווית לכל שדה טופס, גם כשהעיצוב מציג אותה רק כטקסט רמז בתוך השדה.</li>
      <li>מבנה כותרות תקין, אזורי ניווט ותוכן מסומנים, וטקסט חלופי לכל תמונה נושאת מידע.</li>
      <li>יחס ניגודיות של 4.5:1 לפחות לכל טקסט — נמדד, לא נאמד.</li>
      <li>האתר עובד מרוחב של 320 פיקסלים ללא גלילה אופקית.</li>
      <li>
        תפריט נגישות בפינה: הגדלת טקסט, ניגודיות גבוהה, הדגשת קישורים, עצירת אנימציות
        וגופן קריא יותר. הבחירה נשמרת בדפדפן שלך.
      </li>
      <li>האתר מכבד את הגדרת <span dir="ltr">prefers-reduced-motion</span> של מערכת ההפעלה.</li>
    </ul>

    </section>

    <section className="legal-section">
    <h2>מה עדיין לא נגיש</h2>
    <p>
      אנחנו מעדיפים לומר את זה מראש מאשר שתגלו את זה לבד:
    </p>
    <ul>
      <li>
        <b>כפתור הכניסה עם Google</b> מגיע מגוגל ומוטמע כמו שהוא. אין לנו שליטה על הסימון
        הפנימי שלו. יש דרך כניסה מלאה וחלופית עם שם משתמש וסיסמה, והיא נגישה.
      </li>
      <li>
        <b>טבלאות הפילוח</b> בתעודת הזהות רחבות, ובמסך צר נדרשת גלילה אופקית בתוך הטבלה
        עצמה. הנתונים עצמם קריאים לקורא מסך.
      </li>
      <li>
        <b>התשובות של לארסון נכתבות על ידי מודל שפה</b>, ולכן אורכן ומבנה הפסקאות בהן
        משתנים. הן מוגשות כטקסט רגיל שניתן להגדלה, להקראה ולהעתקה.
      </li>
    </ul>

    </section>

    <section className="legal-section">
    <h2>נתקלתם במשהו שלא עובד?</h2>
    <p>
      זה הדבר הכי מועיל שאפשר לעשות בשבילנו. כתבו לנו מה ניסיתם לעשות, באיזה עמוד, ובאיזה
      אמצעי (דפדפן, קורא מסך, מקלדת) — ונחזור אליכם.
    </p>
    <p>
      <b>רכז הנגישות:</b> עומר ינאי<br />
      <b>דוא"ל:</b>{' '}
      <a href={`mailto:${ACCESSIBILITY_CONTACT}`} dir="ltr">{ACCESSIBILITY_CONTACT}</a>
    </p>

    </section>

    <section className="legal-section">
    <h2>איך נבדק</h2>
    <p>
      הנגישות נבדקה בבדיקה ידנית ובמדידה אוטומטית של יחסי ניגודיות, שמות נגישים לפקדים,
      מבנה כותרות וניווט במקלדת, על פני כל מסכי האתר. הבדיקה חוזרת עם כל שינוי משמעותי.
    </p>

    </section>

    <p className="legal-footer">
      <Link to="/">חזרה לדף הבית</Link> · <Link to="/privacy">מדיניות פרטיות</Link> ·{' '}
      <Link to="/terms">תנאי שימוש</Link>
    </p>

  </div>
)

export default AccessibilityStatement

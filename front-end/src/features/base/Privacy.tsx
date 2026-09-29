import { Link } from 'react-router-dom'
import './legal.css'



/**
 * What is held, where it goes, and how to get rid of it.
 *
 * **The section that actually matters is "מה יוצא החוצה".** This product sends a summary of
 * somebody's trading record to a third party in order to answer a question about it, and a
 * privacy policy that does not say so plainly is not a privacy policy - it is a formality
 * that happens to be published. Everything else here is ordinary.
 */
const Privacy = () => (
  <div className="app-container legal-page">

    <h1 className="legal-title">מדיניות פרטיות</h1>
    <p className="legal-updated">עודכן לאחרונה: ספטמבר 2026</p>

    <section className="legal-section">
      <h2>מה אנחנו שומרים</h2>
      <ul>
        <li><b>פרטי החשבון:</b> שם משתמש, כתובת מייל, וסיסמה — ששמורה מוצפנת (hash) ולא ניתנת לשחזור, גם לא על ידינו.</li>
        <li><b>קבצי העסקאות שהעלית</b>, כפי שהם, וכן העסקאות המנורמלות שנקראו מהם.</li>
        <li><b>הפרופיל הכתוב</b> וכל השיחות שלך עם לארסון — שלך ושלו.</li>
      </ul>
      <p>
        זה הכול. אנחנו לא מחזיקים פרטי אמצעי תשלום, לא מתחברים לברוקר שלך, ולא אוספים מידע
        על גלישה מחוץ לאתר.
      </p>
    </section>

    <section className="legal-section legal-highlight">
      <h2>מה יוצא החוצה</h2>
      <p>
        כדי לענות לך, לארסון שולח את הנתונים הרלוונטיים <b>ל-Anthropic</b>, שמפעילה את מודל
        השפה שמנסח את התשובות. מה שנשלח: <b>סטטיסטיקות מחושבות, הפרופיל הכתוב, וההודעות
        בשיחה</b>. מה שלא נשלח: הסיסמה שלך, כתובת המייל שלך, וקבצי המקור עצמם.
      </p>
      <p>
        זה קורה רק כשאתה מבקש ניתוח, תחקיר או תשובה בצ'אט. שאר העמודים — כל המספרים, הציון,
        והפילוחים — <b>מחושבים אצלנו ולא עוזבים את השרת</b>.
      </p>
      <p className="legal-note">
        אנחנו מתקשרים עם Anthropic דרך ה-API העסקי שלה, שבו נתוני לקוחות אינם משמשים לאימון
        מודלים. מדיניות הפרטיות שלה זמינה באתר שלה.
      </p>
    </section>

    <section className="legal-section">
      <h2>כניסה עם גוגל</h2>
      <p>
        אם בחרת להיכנס עם חשבון גוגל, הדפדפן שלך מתחבר ל-<b>Google</b> ומקבל ממנה אישור חתום.
        אנחנו מקבלים מהאישור הזה שלושה דברים בלבד: <b>כתובת המייל שלך, השם שבחשבון, ומזהה
        קבוע של החשבון</b> — ומשתמשים בהם כדי לזהות לאיזה חשבון אצלנו אתה שייך.
      </p>
      <p>
        <b>אין לנו גישה לתיבת הדואר שלך, לאנשי הקשר שלך או לכל דבר אחר בחשבון הגוגל</b>, ואנחנו
        לא שולחים לגוגל שום דבר על המסחר שלך. אם תעדיף, אפשר תמיד להיכנס עם סיסמה במקום.
      </p>
      <p className="legal-note">
        השימוש בכפתור הזה כפוף גם למדיניות הפרטיות של גוגל, שזמינה באתר שלה.
      </p>
    </section>

    <section className="legal-section">
      <h2>מה אתה יכול לעשות בכל רגע</h2>
      <ul>
        <li><b>להוריד הכול:</b> קובץ אחד עם כל מה שמוחזק עליך, מעמוד <Link to="/account">החשבון שלי</Link>.</li>
        <li><b>למחוק את הרזומה:</b> העסקאות, קבצי המקור והפרופיל הכתוב, מתוך "הרזומה שלי".</li>
        <li><b>למחוק את החשבון כולו:</b> הכול נמחק לצמיתות, כולל השיחות והמשתמש עצמו.</li>
      </ul>
      <p>מחיקה היא מחיקה — לא סימון כמוסתר. אין גיבוי שממנו נשלוף את זה בחזרה.</p>
    </section>

    <section className="legal-section">
      <h2>אבטחה</h2>
      <p>
        הסיסמאות נשמרות מוצפנות, הגישה לכל נתון עוברת אימות, וכל בקשה מוגבלת בקצב. בכל זאת:
        שום מערכת אינה חסינה, ואנחנו לא יכולים להבטיח אחרת.
      </p>
    </section>

    <section className="legal-section">
      <h2>יצירת קשר</h2>
      <p>
        לשאלות על המידע שלך, או לבקשת מחיקה שלא הצלחת לבצע לבד — אפשר לפנות אלינו במייל
        שמופיע באתר.
      </p>
    </section>

    <p className="legal-footer">
      ראה גם: <Link to="/terms">תנאי שימוש</Link>
    </p>

  </div>
)

export default Privacy

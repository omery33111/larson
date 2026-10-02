import { Link } from 'react-router-dom'
import './legal.css'



/**
 * What is held, where it goes, and how to get rid of it.
 *
 * **The section that actually matters is "מה יוצא החוצה".** This product sends a summary of
 * somebody's trading record to a third party in order to answer a question about it, and a
 * privacy policy that does not say so plainly is not a privacy policy - it is a formality
 * that happens to be published. Everything else here is ordinary.
 *
 * **"מה נשמר בדפדפן שלך" is a disclosure, not a consent gate, and that is deliberate.** It was
 * written from a measurement of the live site rather than from assumption: the landing page
 * stores nothing and loads no third-party script, and the only cookie that exists anywhere is
 * Google's `g_state` on the three sign-in screens. Consent is owed for storage a visitor could
 * decline and still be served - analytics, advertising, cross-site tracking - and this product
 * has none of it, so a banner here would have no honest button on it. **The day a usage-measuring
 * tool is installed, that stops being true and a real accept/refuse banner is owed** - built
 * against whatever is actually installed, which is why it is not built in advance.
 */
const Privacy = () => (
  <div className="app-container legal-page">

    <h1 className="legal-title">מדיניות פרטיות</h1>
    <p className="legal-updated">עודכן לאחרונה: אוקטובר 2026</p>

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
      <p>
        בנוסף, כשמשהו באתר נשבר נשלח <b>דיווח שגיאה טכני</b> לשירות <b>Sentry</b>, שדרכו אנחנו
        רואים מה נשבר ואיפה. הדיווח נושא את סוג התקלה ואת המקום בקוד — <b>ולא את תוכן הבקשה
        שלך, לא את העוגיות שלה ולא את הכותרות שלה</b>. זו הגדרה שנקבעה כאן בכוונה, והיא אינה
        ברירת המחדל של השירות.
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
      <h2>מה נשמר בדפדפן שלך</h2>
      <p>
        <b>אין באתר הזה אנליטיקס, פיקסלים של פרסום, ושום מעקב חוצה־אתרים.</b> עמוד הבית אינו
        שומר כלום ואינו טוען אף סקריפט חיצוני. שני הדברים היחידים שכן נשמרים הם אלה:
      </p>
      <ul>
        <li>
          <b>הכניסה שלך</b> — אסימון הגישה ושם המשתמש. אם סימנת "להישאר מחובר" הוא נשמר עד
          שתתנתק, ואחרת הוא נמחק ברגע שסגרת את הלשונית. <b>"התנתקות" מוחקת אותו מיד.</b>
        </li>
        <li>
          <b>עוגייה אחת של גוגל</b> בשם <b>g_state</b>, שנוצרת רק במסכי ההתחברות וההרשמה
          וזוכרת אם סגרת את חלונית הכניסה המהירה, כדי שלא תוצג לך שוב. <b>שום אתר אחר לא
          יכול לקרוא אותה.</b>
        </li>
      </ul>
      <p>
        <b>אין כאן דבר שאפשר לוותר עליו והאתר ימשיך לעבוד</b>, ולכן גם אין מסך שמבקש הסכמה
        לעוגיות. אם נוסיף אי פעם כלי שמודד שימוש — <b>תקבל אפשרות לאשר או לסרב לו לפני שהוא
        יאסוף דבר</b>.
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

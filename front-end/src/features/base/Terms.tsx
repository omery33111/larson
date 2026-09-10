import { Link } from 'react-router-dom'
import './legal.css'



/**
 * What the product is, and - more to the point - what it is not.
 *
 * The disclaimer in the footer has always said "not investment advice". This is the same
 * sentence with the reasoning attached, in the one place where somebody who wants to check
 * will look for it.
 */
const Terms = () => (
  <div className="app-container legal-page">

    <h1 className="legal-title">תנאי שימוש</h1>
    <p className="legal-updated">עודכן לאחרונה: ספטמבר 2026</p>

    <section className="legal-section legal-highlight">
      <h2>זה לא ייעוץ השקעות</h2>
      <p>
        Larson הוא <b>כלי אנליטי וחינוכי</b>. הוא קורא את היסטוריית המסחר שאתה מספק, מחשב
        ממנה סטטיסטיקות, ומנסח עליהן טקסט.
      </p>
      <p>
        הוא <b>אינו</b> ייעוץ השקעות, אינו שיווק השקעות, ואינו תחזית שוק. הוא לא ימליץ לך מה
        לקנות או למכור ומתי, ואם תבקש — הוא יסרב. אין לנו רישיון לייעוץ השקעות ואיננו פועלים
        כיועצים.
      </p>
      <p>
        <b>כל החלטת מסחר היא שלך בלבד, ובאחריותך בלבד.</b> מסחר כרוך בסיכון להפסד, לרבות הפסד
        מלוא הכסף.
      </p>
    </section>

    <section className="legal-section">
      <h2>הנתונים הם שלך</h2>
      <p>
        אתה מעלה את היסטוריית המסחר שלך, והיא נשארת שלך. אתה יכול להוריד אותה או למחוק אותה
        בכל רגע מעמוד <Link to="/account">החשבון שלי</Link>. אנחנו לא מוכרים אותה ולא מעבירים
        אותה לצד שלישי מלבד מה שמתואר ב<Link to="/privacy">מדיניות הפרטיות</Link>.
      </p>
      <p>
        באחריותך לוודא שיש לך זכות להעלות את הקבצים שאתה מעלה.
      </p>
    </section>

    <section className="legal-section">
      <h2>מה שמוצג יכול להיות שגוי</h2>
      <p>
        כל מספר במוצר מחושב מהקבצים שאתה מספק. <b>קובץ חלקי או שגוי מפיק ניתוח שגוי</b>, ואין
        לנו דרך לדעת שהוא כזה. הטקסט שלארסון כותב מנוסח על ידי מודל שפה ועשוי לטעות בניסוח גם
        כשהמספרים נכונים.
      </p>
      <p>
        השירות ניתן "כפי שהוא". אנחנו לא מתחייבים לזמינות רציפה, ולא אחראים להפסדים שנגרמו
        מהסתמכות על מה שהוצג.
      </p>
    </section>

    <section className="legal-section">
      <h2>החשבון שלך</h2>
      <ul>
        <li>חשבון אחד לאדם. אתה אחראי לשמור על הסיסמה שלך.</li>
        <li>אסור להעמיס על השירות באופן אוטומטי או לעקוף את מגבלות הקצב.</li>
        <li>אנחנו רשאים לסגור חשבון שמפר את התנאים האלה.</li>
      </ul>
    </section>

    <section className="legal-section">
      <h2>שינויים</h2>
      <p>
        אם נשנה את התנאים באופן מהותי, נעדכן את התאריך למעלה. המשך שימוש אחרי שינוי מהווה
        הסכמה לו.
      </p>
    </section>

    <p className="legal-footer">
      ראה גם: <Link to="/privacy">מדיניות פרטיות</Link>
    </p>

  </div>
)

export default Terms

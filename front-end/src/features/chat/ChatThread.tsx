import { useEffect, useRef, useState } from 'react'
import { useAppDispatch, useAppSelector } from '../../app/hooks'
import LarsonMark from '../larson/LarsonMark'
import ChatMessage from './ChatMessage'
import { useTypewriter } from './useTypewriter'
import {
  clearJumpTarget, selectIsLoadingThread, selectIsStreaming, selectIsWaiting,
  selectJumpTargetId, selectMessages, selectStreamingText, sendMessageAsync
} from './chatSlice'



/**
 * Sixteen questions, four shown at a time.
 *
 * These are not analysis requests, and the first version of this list was - it asked things
 * a spreadsheet could be asked, and nobody wants to press a spreadsheet. What a trader
 * actually wants to press is a question about himself that he is slightly afraid of: the
 * talent he never noticed, the habit he cannot admit to, the thing that is dangerous
 * precisely because he is proud of it.
 *
 * Three rules produced the list, and each of them costs money if broken:
 *
 * 1. **Nothing here is printed on the profile page.** Win rate, expectancy, profit factor,
 *    the breakdown by hour - all of that is already on screen for free. Spending a model
 *    call to read a number back off a page the trader just left is paying twice.
 *
 * 2. **Every one is answerable from what the model actually receives** - and what that is
 *    changed, so this list changed with it. It used to carry aggregates and nothing else, so
 *    "how did I trend across the months" would only ever have produced an apology. It now
 *    also carries **a time axis** and **named instances on every finding**, and a question
 *    that looks specific pulls the rows themselves. The four questions at the end of this
 *    list exist because of that, and they could not have been asked last week.
 *
 * 3. **Half of them are good news.** A list that only digs for what is broken gets pressed
 *    once. The hidden strength is as much of a secret as the leak, and it is the half that
 *    makes the trader come back.
 *
 * The persona carries the matching instruction: a reading of character has to be anchored in
 * something specific from the data, or an open question like these turns into a horoscope.
 */
const OPENERS = [
  // ------------- what he is good at and does not know it
  'מה הכישרון החבוי שלי במסחר — הדבר שאני טוב בו ואפילו לא שמתי לב?',
  'מה אני עושה טוב יותר מרוב הסוחרים בלי לדעת שזה נדיר?',
  'אם היו לוקחים ממני הכול חוץ מיכולת אחת, איזו הייתי חייב לשמור?',
  'איזה חוזק שלי הפך לחולשה בלי ששמתי לב?',

  // ------------- what he would rather not hear
  'מה הדבר הכי מביך שהנתונים שלי מסגירים עליי?',
  'מה מסוכן אצלי דווקא מפני שאני בטוח שזה היתרון שלי?',
  'מה הדפוס שלי שהכי קשה לי להודות בו?',
  'מה ההרגל שלי שנראה תמים והוא הכי יקר?',
  'מה יחסל לי את החשבון אם לא אשנה כלום?',

  // ------------- who he is, from the outside
  'תאר אותי כמו שסוחר ותיק היה מתאר אותי מאחורי הגב, בלי לרכך.',
  'אם היית הסוחר שיושב מולי בשוק, איפה היית תוקף אותי?',
  'איזה סוג סוחר אני באמת — גם אם אני חושב שאני משהו אחר?',
  'מה הנתונים שלי מסגירים על האופי שלי, לא על המסחר שלי?',
  'מה אני מספר לעצמי על המסחר שלי שהנתונים לא מאשרים?',

  // ------------- the hypotheticals
  'אם היו נותנים לי מחר חשבון של מיליון דולר, מה היה קורה?',
  'אם הייתי מפסיק לסחור מחר — במה הייתי מתגאה, ועל מה הייתי מתחרט?',

  // ------------- what only the time axis can answer
  //
  // **These four are new, and they are the ones a mentor is actually for.** Until the
  // periods engine existed there was no month-over-month comparison anywhere in the prompt,
  // so the single most important question a trader has - am I getting better - had no answer
  // in it at all. The last one asks for an instance by name, which the findings now carry.
  'האם אני משתפר, או שאני פשוט סוחר אותו דבר יותר זמן?',
  'מה השתנה אצלי בחודש האחרון מול החודש שלפניו — ולא לטובה?',
  'מה הפסקתי לעשות בלי לשים לב, ושווה לי לחזור אליו?',
  'תראה לי את שלוש העסקאות שהכי מדממות אצלי, בשמן.',
];

const OPENERS_SHOWN = 4;

/** A different four every time the chat is opened. */
const pickOpeners = () => {
  const pool = [...OPENERS];

  for (let i = pool.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [pool[i], pool[j]] = [pool[j], pool[i]];
  }

  return pool.slice(0, OPENERS_SHOWN);
};


// An invisible mark, not a space: it survives trimming, so the caret has a line to sit on
// before the first token arrives.
const EMPTY_LINE = '‎';


const ChatThread = () => {

  const dispatch = useAppDispatch();

  const messages = useAppSelector(selectMessages);
  const streamingText = useAppSelector(selectStreamingText);
  const isStreaming = useAppSelector(selectIsStreaming);
  const isWaiting = useAppSelector(selectIsWaiting);
  const isLoading = useAppSelector(selectIsLoadingThread);
  const jumpTargetId = useAppSelector(selectJumpTargetId);

  // Drawn once per visit to the page, not on every render - otherwise the chips would
  // reshuffle under the cursor while the trader is reading them.
  const [openers] = useState(pickOpeners);

  // What the model has sent is held in the store; this is what has been let out onto the
  // screen so far.
  const typed = useTypewriter(streamingText, isStreaming);

  const scroller = useRef<HTMLDivElement>(null);

  // Follows the answer down, but only while the trader is already at the bottom. Yanking
  // him back mid-scroll while he re-reads an earlier paragraph is worse than not following.
  const isPinned = useRef(true);

  const onScroll = () => {
    const box = scroller.current;
    if (!box) return;

    isPinned.current = box.scrollHeight - box.scrollTop - box.clientHeight < 80;
  };

  // A saved answer was opened out of the list. Declared before the follow-the-answer effect
  // below, so unpinning here stops that one from yanking the view back down.
  useEffect(() => {
    if (!jumpTargetId) return;

    const node = scroller.current?.querySelector(`[data-message-id="${jumpTargetId}"]`);
    if (!node) return;

    isPinned.current = false;
    node.scrollIntoView({ block: 'center', behavior: 'smooth' });

    // Long enough for the highlight to be seen and to fade, and it is what ends it.
    const timer = setTimeout(() => dispatch(clearJumpTarget()), 2600);
    return () => clearTimeout(timer);
  }, [jumpTargetId, messages, dispatch]);

  useEffect(() => {
    const box = scroller.current;
    if (!box || !isPinned.current) return;

    box.scrollTop = box.scrollHeight;
  }, [messages, typed, isWaiting]);

  const isEmpty = messages.length === 0 && !isStreaming && !isLoading;

  return (
    <div className="chat-thread" ref={scroller} onScroll={onScroll}>

      {isLoading && <p className="chat-thread-loading">טוען את השיחה...</p>}

      {isEmpty && (
        <div className="chat-welcome">
          <span className="chat-welcome-mark">
            <LarsonMark state="idle" />
          </span>

          <h1 className="chat-welcome-title">לארסון כבר קרא את הנתונים שלך</h1>

          <p className="chat-welcome-pitch">
            הוא לא צריך שתסביר לו על מה אתה מדבר. תשאל אותו את מה שבאמת מפריע לך.
          </p>

          <div className="chat-openers">
            {openers.map((question) => (
              <button
                key={question}
                className="chat-opener"
                onClick={() => dispatch(sendMessageAsync(question))}
              >
                {question}
              </button>
            ))}
          </div>

          <p className="chat-welcome-note">
            אפשר גם לגרור לכאן קובץ להשוואה — באקטסט מול ביצוע חי. הוא לא נשמר לרזומה.
          </p>
        </div>
      )}

      {messages.map((message) => (
        <ChatMessage
          key={`${message.role}-${message.id}-${message.created_at}`}
          message={message}
          isFound={message.id === jumpTargetId}
        />
      ))}

      {isStreaming && (
        // While the first token is still on its way there is nothing to read, so the visor
        // carries it: a flat, flickering line is Larson thinking. No spinner - he already
        // has a face for this.
        <ChatMessage
          message={{
            id: -1,
            role: 'assistant',
            content: typed || EMPTY_LINE,
            attachment_name: '',
            is_starred: false,
            created_at: '',
          }}
          isWriting
        />
      )}

      {isWaiting && <p className="chat-waiting">לארסון קורא את השאלה...</p>}

      <div className="chat-thread-floor" />

    </div>
  )
}

export default ChatThread

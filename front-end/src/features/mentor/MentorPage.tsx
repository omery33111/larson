import { useEffect, useRef } from 'react'
import { FiPaperclip, FiSend, FiSquare, FiTarget, FiUploadCloud, FiX } from 'react-icons/fi'
import { useNavigate } from 'react-router-dom'
import { toast } from 'react-toastify'
import { useAppDispatch, useAppSelector } from '../../app/hooks'
import { selectIsLogged } from '../authentication/authenticationSlice'
import ChatMessage from '../chat/ChatMessage'
import SuggestionCard from './SuggestionCard'
import { clearJumpTarget, selectJumpTargetId } from '../chat/chatSlice'
import { useTypewriter } from '../chat/useTypewriter'
import LarsonMark from '../larson/LarsonMark'
import LarsonPresence, { presenceState } from '../larson/LarsonPresence'
import RulesPanel from './RulesPanel'
import UsageNotice from '../usage/UsageNotice'
import { getUsageAsync } from '../usage/usageSlice'
import {
  resetIngestion, selectIsUploading, selectResumeVersion, uploadTradesAsync
} from '../trades/tradesSlice'
import {
  dismissPendingAsync, expectIngestion, getMentorAsync, getRulesAsync, resetMentorMessage, selectPendingFile,
  selectMentorDraft, selectMentorIsDragging, selectMentorIsLoading, selectMentorIsStreaming,
  selectMentorIsWaiting, selectMentorMessage, selectMentorMessages, selectMentorStreamingText,
  selectResumeState, selectRules, selectStreamingVerdict, sendToMentorAsync,
  setMentorDragging, setMentorDraft, stopMentor, openRules
} from './mentorSlice'

// The conversation surface itself - the shell, the aura, the thread, the bubbles - is defined
// once in the chat's stylesheet and used by both screens. Two copies of it would drift, and
// the two screens are meant to feel like the same room.
import '../chat/chat.css'
import './mentor.css'



const EMPTY_LINE = '‎';

// Below this the nudge would be noise: a trader who traded yesterday is not behind.
const STALE_AFTER_DAYS = 2;


const MentorPage = () => {

  const dispatch = useAppDispatch();
  const navigate = useNavigate();

  const isLogged = useAppSelector(selectIsLogged);
  const messages = useAppSelector(selectMentorMessages);
  const resume = useAppSelector(selectResumeState);
  const rules = useAppSelector(selectRules);
  const streamingText = useAppSelector(selectMentorStreamingText);
  const isStreaming = useAppSelector(selectMentorIsStreaming);
  const isWaiting = useAppSelector(selectMentorIsWaiting);
  const isLoading = useAppSelector(selectMentorIsLoading);
  const isDragging = useAppSelector(selectMentorIsDragging);
  const isUploading = useAppSelector(selectIsUploading);
  const resumeVersion = useAppSelector(selectResumeVersion);
  const draft = useAppSelector(selectMentorDraft);
  const pendingFile = useAppSelector(selectPendingFile);
  const message = useAppSelector(selectMentorMessage);
  const streamingVerdict = useAppSelector(selectStreamingVerdict);

  // A saved answer was opened out of the chat's list and it turned out to have been said
  // here. The target lives in the chat's slice because that is where the saved answers are;
  // both screens read the same one, so it cannot go stale in two places at once.
  const jumpTargetId = useAppSelector(selectJumpTargetId);

  // What the model has sent is held in the store; this is what has been let out onto the
  // screen so far.
  const typed = useTypewriter(streamingText, isStreaming);

  const scroller = useRef<HTMLDivElement>(null);
  const isPinned = useRef(true);
  const picker = useRef<HTMLInputElement>(null);
  const box = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!isLogged) {
      navigate('/authentication/login');
      return;
    }
    dispatch(getMentorAsync());

    // **With the page and not on first open**, because the count on the button is the thing
    // that tells him rules exist at all - loading them lazily would show a bare button to a
    // trader who has seven commitments.
    dispatch(getRulesAsync());

    // Read once, here. After this the fresh figure rides the last event of every answer.
    dispatch(getUsageAsync());
    // `resumeVersion` moves whenever the resume actually changed - a file confirmed here, a
    // file added from the dialog, a deletion. Re-reading on it is also what puts the newly
    // confirmed file onto the composer, without this screen having to know who confirmed it.
  }, [isLogged, resumeVersion, dispatch]);

  useEffect(() => {
    if (message) {
      toast.error(message);
      dispatch(resetMentorMessage());
    }
  }, [message, dispatch]);

  useEffect(() => {
    const field = box.current;
    if (!field) return;

    field.style.height = 'auto';
    field.style.height = `${Math.min(field.scrollHeight, 160)}px`;
  }, [draft]);

  // Declared before the follow-the-answer effect below, so unpinning here stops that one
  // from yanking the view straight back to the floor.
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
    const view = scroller.current;
    if (!view || !isPinned.current) return;

    view.scrollTop = view.scrollHeight;
  }, [messages, typed, isWaiting]);

  const onScroll = () => {
    const view = scroller.current;
    if (!view) return;

    isPinned.current = view.scrollHeight - view.scrollTop - view.clientHeight < 80;
  };

  const handleFile = (file: File | undefined) => {
    if (!file || isStreaming) return;

    // Order matters, and getting it wrong was silent: `resetIngestion` also clears the flag,
    // so announcing first and clearing second wiped the very thing that says this page owns
    // the confirmation - and the file landed in the resume while the conversation sat still.
    dispatch(resetIngestion());
    dispatch(expectIngestion());
    dispatch(uploadTradesAsync(file));
  };

  const send = () => {
    if (isStreaming || (!draft.trim() && !pendingFile)) return;

    // File and note travel as one turn. The file waited for this press rather than firing on
    // confirmation, which is what lets him write the line after choosing the file - and what
    // keeps it there if he walks away from the page entirely.
    dispatch(sendToMentorAsync({ fileId: pendingFile?.id, message: draft.trim() }));
    dispatch(resetIngestion());
  };

  const isStale = resume.days_since !== null && resume.days_since >= STALE_AFTER_DAYS;

  // Nothing in the resume means nothing to compare against, and a debrief with no baseline is
  // not a debrief. The conversation is closed until he has seen something; sending a file -
  // the way out - stays open, and the server enforces the same rule.
  const knowsHim = resume.total_trades > 0;

  // Once he has sent something the conversation replaces the onboarding for good, so the
  // panel cannot flash back in the gap between the answer ending and the refreshed resume
  // state arriving.
  const hasSpoken = messages.some((row) => row.role === 'user');

  return (
    <div className="app-container chat-page mentor-page">

      <div className={`chat-aura ${isStreaming ? 'chat-aura-live' : ''}`} aria-hidden="true" />

      <div className="chat-shell mentor-shell">

        <div
          className="chat-main"
          onDragOver={(event) => { event.preventDefault(); dispatch(setMentorDragging(true)); }}
          onDragLeave={(event) => {
            if (!event.currentTarget.contains(event.relatedTarget as Node)) {
              dispatch(setMentorDragging(false));
            }
          }}
          onDrop={(event) => {
            event.preventDefault();
            dispatch(setMentorDragging(false));
            handleFile(event.dataTransfer.files?.[0]);
          }}
        >

          {/* What he knows and how old it is, in the place a chat puts its title. This strip
              is the reason to be here: it names the gap the page exists to close. */}
          <div className="chat-topbar mentor-topbar">
            <div className="chat-topbar-side chat-topbar-side-stack">
              <span className="chat-topbar-title">לארסון המנטור</span>

              {resume.total_trades > 0 ? (
                <span className={`mentor-resume ${isStale ? 'mentor-resume-stale' : ''}`}>
                  <span className="mentor-resume-dot" aria-hidden="true" />
                  לארסון מכיר {resume.total_trades} עסקאות
                  {resume.days_since !== null && (
                    <>
                      {' · '}
                      {resume.days_since === 0 ? 'עודכן היום'
                        : resume.days_since === 1 ? 'העסקה האחרונה שראה: אתמול'
                        : `העסקה האחרונה שראה: לפני ${resume.days_since} ימים`}
                    </>
                  )}
                </span>
              ) : (
                <span className="mentor-resume">עדיין לא ראה אף עסקה שלך</span>
              )}

              {/* **The rules he set for himself**, reachable from the screen that checks
                  them rather than from an account menu. A commitment belongs beside the
                  debrief that judges it - putting it in settings would make it a preference. */}
              <button type="button" className="mentor-rules-open"
                      onClick={() => dispatch(openRules())}>
                <FiTarget aria-hidden="true" />
                הכללים שלי
                {rules.length > 0 &&
                  <span className="mentor-rules-open-count">{rules.length}</span>}
              </button>
            </div>

            {/* This is the screen the presence was built for. The verdict is the whole point
                of a debrief - green when the new trades kept the rules his own history argues
                for, red when one broke - and until now it existed only as the tint of a 46px
                avatar halfway up a scrolling thread. Here it is his face at 76px in the strip
                that never scrolls, with the verdict also said in words.

                It reads off the last answer, so it survives a refresh: the verdict is stored
                on the message row rather than only sent in the stream. */}
            <LarsonPresence
              state={presenceState(isWaiting || isStreaming, messages)}
              idleNote={knowsHim ? 'מוכן לתחקיר הבא' : 'מחכה לקובץ הראשון שלך'}
            />
          </div>

          <div className="chat-thread" ref={scroller} onScroll={onScroll}>

            {isLoading && messages.length === 0 && (
              <p className="chat-thread-loading">פותח את השיחה...</p>
            )}

            {!knowsHim && !hasSpoken && !isLoading && !isStreaming ? (
              <div className="mentor-onboard">
                <span className="mentor-onboard-mark">
                  <LarsonMark state="thinking" />
                </span>

                <h1 className="mentor-onboard-title">לארסון עוד לא מכיר אותך</h1>

                <p className="mentor-onboard-text">
                  כדי שיגיד לך מה השתנה בך, קודם צריך שיהיה לו ממה להשוות.
                  תן לו את היסטוריית המסחר שלך — <b>ומהעדכון הבא, כל קובץ שתשלח יהיה
                  השוואה למה שהוא כבר יודע עליך.</b>
                </p>

                <p className="mentor-onboard-note">
                  קובץ ייצוא מיומן המסחר, מהברוקר או מהפלטפורמה · CSV · XLSX · דוח HTML של MT4/MT5
                </p>
              </div>
            ) : messages.map((row) => (
              <div key={`${row.role}-${row.id}-${row.created_at}`}>
                <ChatMessage message={row} isFound={row.id === jumpTargetId} />

                {/* **Under the finished answer, never beside a streaming one.** Asking him
                    to commit while he is still reading why is asking before he has heard
                    the reason - which is also why it rides the `done` event and not
                    `start`. It is stored on the message, so a refresh does not lose a
                    question he has not answered yet. */}
                {row.suggestion &&
                  <SuggestionCard messageId={row.id} card={row.suggestion} />}
              </div>
            ))}

            {isStreaming && (
              <ChatMessage
                message={{
                  id: -1,
                  role: 'assistant',
                  content: typed || EMPTY_LINE,
                  attachment_name: '',
                  verdict: streamingVerdict,
                  is_starred: false,
                  created_at: '',
                }}
                isWriting
              />
            )}

            {isWaiting && <p className="chat-waiting">לארסון קורא את מה ששלחת...</p>}

            <div className="chat-thread-floor" />
          </div>

          <div className="chat-composer mentor-composer">

            {/* Nothing at all until there is a reason - see UsageNotice.tsx. */}
            <UsageNotice />

            <input
              ref={picker}
              className="chat-file-input"
              type="file"
              accept=".csv,.tsv,.txt,.xlsx,.xlsm,.xls,.html,.htm"
              onChange={(event) => { handleFile(event.target.files?.[0]); event.target.value = ''; }}
            />

            {/* The file is the point of this screen, so it gets the size and the gold. Typing
                is the secondary path, not the other way round. */}
            <button
              className="mentor-dropzone"
              onClick={() => picker.current?.click()}
              disabled={isStreaming || isUploading}
            >
              <FiUploadCloud className="mentor-dropzone-icon" />

              <span className="mentor-dropzone-text">
                <b>
                  {isUploading ? 'קורא את הקובץ...'
                    : pendingFile ? 'להחליף בקובץ אחר'
                    : knowsHim ? 'צרף את העסקאות האחרונות שלך'
                    : 'תן לו את היסטוריית המסחר שלך'}
                </b>
                {/* Said at the moment it becomes true rather than as standing instructions.
                    A permanent line about a combination most uploads do not use is clutter;
                    this one appears the instant there is something in the box to send. */}
                <span className="mentor-dropzone-note">
                  {pendingFile
                    ? 'קובץ אחר יחליף את זה שממתין'
                    : draft.trim()
                      ? 'מה שכתבת יישלח יחד עם הקובץ'
                      : 'גרור לכאן קובץ או לחץ לבחירה · נשמר לרזומה רק אחרי שתאשר'}
                </span>
              </span>
            </button>

            {/* It sits on the composer rather than in the thread, because it has not been
                said yet. The trades are already in the resume - confirming did that - so the
                X drops the debrief and nothing else, and the line underneath says so plainly
                rather than letting him think he is undoing the import. */}
            {pendingFile && (
              <div className="mentor-attached">
                <FiPaperclip className="mentor-attached-icon" />

                <span className="mentor-attached-text">
                  <b>{pendingFile.original_name}</b>
                  <span className="mentor-attached-note">
                    {pendingFile.imported_count} עסקאות כבר נשמרו לרזומה · ממתין לשליחה
                  </span>
                </span>

                <button
                  className="mentor-attached-remove"
                  onClick={() => dispatch(dismissPendingAsync())}
                  disabled={isStreaming}
                  aria-label="הסרת הקובץ מהשליחה"
                  title="לא לשלוח את זה לתחקיר. העסקאות נשארות ברזומה."
                >
                  <FiX />
                </button>
              </div>
            )}

            <div className="chat-input-row">
              <textarea
                ref={box}
                className="chat-input"
                value={draft}
                rows={1}
                placeholder={pendingFile
                  ? 'רוצה להוסיף משהו לפני ששולחים? אפשר גם בלי'
                  : knowsHim
                    ? 'תכתוב לו איך היה — לבד, או יחד עם קובץ'
                    : 'קודם שלח לו קובץ עסקאות — ואז יהיה על מה לדבר'}
                onChange={(event) => dispatch(setMentorDraft(event.target.value))}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                    event.preventDefault();
                    send();
                  }
                }}
                disabled={isStreaming || (!knowsHim && !pendingFile)}
              />

              {isStreaming ? (
                <button className="chat-send chat-stop" onClick={stopMentor} aria-label="עצירת התשובה">
                  <FiSquare />
                </button>
              ) : (
                <button className="chat-send" onClick={send}
                  disabled={(!draft.trim() && !pendingFile) || !knowsHim} aria-label="שליחה">
                  <FiSend />
                </button>
              )}
            </div>

            <p className="chat-disclaimer">
              {knowsHim
                ? 'כל קובץ שתאשר כאן נכנס לרזומה ומצטרף למה שלארסון כבר יודע עליך.'
                : 'הקובץ הראשון שתאשר יהפוך לרזומה שכל השאר יימדד מולה.'}
            </p>
          </div>

          {isDragging && (
            <div className="chat-drop" aria-hidden="true">
              <FiUploadCloud className="chat-drop-icon" />
              <span className="chat-drop-title">שחרר כאן</span>
              <span className="chat-drop-note">תראה בדיוק מה נקרא, ורק אז תאשר</span>
            </div>
          )}

        </div>

      </div>

      {/* Mounted once, driven entirely from the store, no props. Two instances of a modal on
          one page is two stacked overlays - the lesson the ingestion gate already taught. */}
      <RulesPanel />

    </div>
  )
}

export default MentorPage

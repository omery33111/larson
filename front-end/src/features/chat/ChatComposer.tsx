import { useEffect, useRef } from 'react'
import { FiPaperclip, FiSend, FiSquare, FiX } from 'react-icons/fi'
import { useAppDispatch, useAppSelector } from '../../app/hooks'
import { setPendingFile } from './chatAPI'
import {
  selectAttachmentName, selectDraft, selectIsStreaming, sendMessageAsync,
  setAttachmentName, setDraft, stopStreaming
} from './chatSlice'



const MAX_ROWS_HEIGHT = 200;


const ChatComposer = () => {

  const dispatch = useAppDispatch();

  const draft = useAppSelector(selectDraft);
  const attachmentName = useAppSelector(selectAttachmentName);
  const isStreaming = useAppSelector(selectIsStreaming);

  const box = useRef<HTMLTextAreaElement>(null);
  const picker = useRef<HTMLInputElement>(null);

  // The height of a textarea can only be known by measuring the text inside it, which is
  // the one case where the value has to be written from JavaScript.
  useEffect(() => {
    const field = box.current;
    if (!field) return;

    field.style.height = 'auto';
    field.style.height = `${Math.min(field.scrollHeight, MAX_ROWS_HEIGHT)}px`;
  }, [draft]);

  const canSend = (draft.trim().length > 0 || attachmentName.length > 0) && !isStreaming;

  const send = () => {
    if (!canSend) return;

    dispatch(sendMessageAsync(draft.trim()));
  };

  const onKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter sends, Shift+Enter breaks the line. On a phone the on-screen return key has to
    // stay a return key, so it is only bound where there is a real keyboard.
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      send();
    }
  };

  const onPick = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setPendingFile(file);
    dispatch(setAttachmentName(file.name));

    // Cleared so picking the same file twice in a row still fires a change event.
    event.target.value = '';
  };

  const dropAttachment = () => {
    setPendingFile(null);
    dispatch(setAttachmentName(''));
  };

  return (
    <div className="chat-composer">

      {attachmentName && (
        <div className="chat-attachment">
          <FiPaperclip className="chat-attachment-icon" />

          <span className="chat-attachment-name">{attachmentName}</span>

          {/* Said out loud, every time. A trader comparing a backtest against his live
              execution has to know which of the two is becoming part of his record. */}
          <span className="chat-attachment-note">מסמך זמני · לא נשמר לרזומה</span>

          <button className="chat-attachment-drop" onClick={dropAttachment} aria-label="הסרת הקובץ">
            <FiX />
          </button>
        </div>
      )}

      <div className="chat-input-row">

        <input
          ref={picker}
          className="chat-file-input"
          type="file"
          accept=".csv,.tsv,.txt,.xlsx,.xlsm,.xls,.html,.htm"
          onChange={onPick}
        />

        <button
          className="chat-attach"
          onClick={() => picker.current?.click()}
          disabled={isStreaming}
          aria-label="צירוף קובץ להשוואה"
          title="צירוף קובץ להשוואה, או פשוט לגרור אותו לכאן — לא נשמר לרזומה"
        >
          <FiPaperclip />
        </button>

        <textarea
          ref={box}
          className="chat-input"
          value={draft}
          rows={1}
          placeholder="שאל את לארסון על המסחר שלך..."
          onChange={(event) => dispatch(setDraft(event.target.value))}
          onKeyDown={onKeyDown}
          disabled={isStreaming}
        />

        {isStreaming ? (
          <button className="chat-send chat-stop" onClick={stopStreaming} aria-label="עצירת התשובה">
            <FiSquare />
          </button>
        ) : (
          <button className="chat-send" onClick={send} disabled={!canSend} aria-label="שליחה">
            <FiSend />
          </button>
        )}

      </div>

      <p className="chat-disclaimer">
        לארסון מנתח את הביצוע שלך, לא את השוק. הוא לא נותן המלצות קנייה ומכירה.
      </p>

    </div>
  )
}

export default ChatComposer

import { useState } from 'react'
import { FaRegStar, FaStar } from 'react-icons/fa'
import { FiCheck, FiCopy, FiPaperclip } from 'react-icons/fi'
import { useAppDispatch } from '../../app/hooks'
import LarsonMark, { LarsonState } from '../larson/LarsonMark'
import { ChatMessage as Message } from '../../models/Chat'
import { toggleStarAsync } from './chatSlice'



/**
 * A single turn.
 *
 * Larson's answers are set as a block with his mark beside them rather than as a bubble:
 * they are two or three paragraphs of analysis, and a chat bubble that long stops reading
 * like speech. The trader's own questions stay short and keep the bubble.
 */

/** Just enough formatting for what the persona is allowed to write - emphasis, nothing else.
    A markdown dependency would be several hundred kilobytes for one asterisk pair. */
const inline = (text: string) =>
  text.split(/(\*\*[^*]+\*\*)/g).map((part, index) =>
    part.startsWith('**') && part.endsWith('**')
      ? <strong key={index}>{part.slice(2, -2)}</strong>
      : part);


const paragraphs = (text: string) =>
  text.split('\n').map((line) => line.trim()).filter(Boolean);


type Props = {
  message: Message;
  isWriting?: boolean;
  isFound?: boolean;
};


/**
 * Copy and save.
 *
 * The row is always in the flow and only fades in on hover, rather than being positioned on
 * top of the text. An absolute overlay would sit on the last line of an answer, and a row
 * that appears and pushes the layout would move the text under the cursor.
 */
const Actions = ({ message }: { message: Message }) => {

  const dispatch = useAppDispatch();

  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      // A browser that refuses the clipboard is not something to interrupt the user over.
    }
  };

  return (
    <div className={`chat-actions ${message.is_starred ? 'chat-actions-pinned' : ''}`}>
      <button
        className={`chat-action ${copied ? 'chat-action-done' : ''}`}
        onClick={copy}
        aria-label="העתקה"
        title={copied ? 'הועתק' : 'העתקה'}
      >
        {copied ? <FiCheck /> : <FiCopy />}
      </button>

      <button
        className={`chat-action ${message.is_starred ? 'chat-action-starred' : ''}`}
        onClick={() => dispatch(toggleStarAsync(message.id))}
        aria-label={message.is_starred ? 'הסרה מהשמורות' : 'שמירה'}
        title={message.is_starred ? 'הסרה מהשמורות' : 'שמירה למסומנות'}
      >
        {message.is_starred ? <FaStar /> : <FaRegStar />}
      </button>
    </div>
  );
};


/**
 * Green when he found nothing broken, red when he did.
 *
 * The colours are the product's own good and bad, and they collide on purpose with the ones
 * P&L uses: a green visor on a losing day - kept every rule, still lost - is exactly what the
 * mentor exists to say. Process and outcome are two different things, and the text beside the
 * mark says which one is being judged.
 */
const visorFor = (message: Message, isWriting: boolean): LarsonState => {
  if (isWriting) return 'thinking';
  if (message.verdict === 'broken') return 'warning';
  if (message.verdict === 'kept') return 'success';
  return 'idle';
};


const ChatMessage = ({ message, isWriting = false, isFound = false }: Props) => {

  // Nothing is offered on an answer still being written: there is no whole text to copy and
  // no finished thought to save.
  const canAct = !isWriting && message.id > 0;

  if (message.role === 'user') {
    return (
      <div
        className={`chat-turn chat-turn-user ${isFound ? 'chat-turn-found' : ''}`}
        data-message-id={message.id}
      >
        <div className="chat-bubble">
          {message.attachment_name && (
            <span className="chat-bubble-file">
              <FiPaperclip /> {message.attachment_name}
            </span>
          )}

          {paragraphs(message.content).map((line, index) => <p key={index}>{inline(line)}</p>)}

          {canAct && <Actions message={message} />}
        </div>
      </div>
    );
  }

  return (
    <div
      className={`chat-turn chat-turn-larson ${isFound ? 'chat-turn-found' : ''}`}
      data-message-id={message.id}
    >
      {/* The visor is his expression, and a debrief is the one answer that has something to
          express. At this size the shape of the line is lost - what carries is the colour,
          which is exactly why these two states live here and `found` does not. */}
      <span className="chat-avatar larson-disc">
        <LarsonMark state={visorFor(message, isWriting)} />
      </span>

      <div className="chat-answer">
        {paragraphs(message.content).map((line, index, all) => (
          <p key={index}>
            {inline(line)}

            {/* The caret rides the end of the last line, where a cursor belongs. Parked
                under the block instead, it reads as an icon rather than as typing. */}
            {isWriting && index === all.length - 1 &&
              <span className="chat-caret" aria-hidden="true" />}
          </p>
        ))}

        {canAct && <Actions message={message} />}
      </div>
    </div>
  )
}

export default ChatMessage

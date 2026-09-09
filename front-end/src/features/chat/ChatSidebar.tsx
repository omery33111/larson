import { FaStar } from 'react-icons/fa'
import { FiActivity, FiCornerUpLeft, FiEdit, FiEdit2, FiMessageSquare, FiTrash2, FiX } from 'react-icons/fi'
import { useNavigate } from 'react-router-dom'
import { useAppDispatch, useAppSelector } from '../../app/hooks'
import LarsonMark from '../larson/LarsonMark'
import {
  cancelRenaming, closeSidebar, createConversationAsync, openConversationAsync,
  openDeleteDialog, renameConversationAsync, selectActiveId, selectConversations,
  selectIsLoadingConversations, selectIsSidebarOpen, selectIsStreaming, selectRenamingId,
  selectSidebarTab, selectStarred, selectTitleDraft, setJumpTarget, setSidebarTab,
  setTitleDraft, startRenaming
} from './chatSlice'



/**
 * The list beside the conversation, in two halves.
 *
 * The saved answers live here rather than on a page of their own, and rather than squeezed
 * into the trading identity card: a saved answer is not a document, it is a bookmark into a
 * conversation, and the place it belongs is next to the conversations. Clicking one does not
 * open a copy of it - it opens the thread it was said in and lands on it, lit.
 */

/** A saved answer shows its opening line, which is exactly why Larson is told to make that
    line answer the question on its own. */
const PREVIEW_LENGTH = 150;


const ConversationRow = ({ id, title }: { id: number; title: string }) => {

  const dispatch = useAppDispatch();

  const activeId = useAppSelector(selectActiveId);
  const isStreaming = useAppSelector(selectIsStreaming);
  const renamingId = useAppSelector(selectRenamingId);
  const titleDraft = useAppSelector(selectTitleDraft);

  if (renamingId === id) {
    return (
      <form
        className="chat-list-row chat-list-renaming"
        onSubmit={(event) => {
          event.preventDefault();
          if (titleDraft.trim()) dispatch(renameConversationAsync({ id, title: titleDraft.trim() }));
        }}
      >
        <input
          className="chat-rename-input"
          value={titleDraft}
          autoFocus
          maxLength={60}
          onChange={(event) => dispatch(setTitleDraft(event.target.value))}
          onBlur={() => dispatch(cancelRenaming())}
          onKeyDown={(event) => { if (event.key === 'Escape') dispatch(cancelRenaming()); }}
          aria-label="שם השיחה"
        />
      </form>
    );
  }

  return (
    <div className={`chat-list-row ${id === activeId ? 'chat-list-row-active' : ''}`}>
      <button
        className="chat-list-open"
        onClick={() => dispatch(openConversationAsync(id))}
        disabled={isStreaming}
      >
        <FiMessageSquare className="chat-list-icon" />
        <span className="chat-list-label">{title}</span>
      </button>

      <button
        className="chat-list-tool"
        onClick={() => dispatch(startRenaming(id))}
        disabled={isStreaming}
        aria-label={`שינוי שם השיחה ${title}`}
        title="שינוי שם"
      >
        <FiEdit2 />
      </button>

      <button
        className="chat-list-tool chat-list-delete"
        onClick={() => dispatch(openDeleteDialog(id))}
        disabled={isStreaming}
        aria-label={`מחיקת השיחה ${title}`}
        title="מחיקה"
      >
        <FiTrash2 />
      </button>
    </div>
  );
};


const ChatSidebar = () => {

  const dispatch = useAppDispatch();

  const conversations = useAppSelector(selectConversations);
  const starred = useAppSelector(selectStarred);
  const tab = useAppSelector(selectSidebarTab);
  const isLoading = useAppSelector(selectIsLoadingConversations);
  const isStreaming = useAppSelector(selectIsStreaming);
  const isOpen = useAppSelector(selectIsSidebarOpen);

  const navigate = useNavigate();

  // The mentor is one of these conversations in the database and none of them in the
  // product: it has no row in this list, and the endpoint that opens a thread refuses it on
  // purpose. So an answer saved out of it is followed to his page instead - the target is
  // set first either way, and the screen that lands picks it up and scrolls to it.
  const openSaved = (saved: { id: number; conversation_id: number; is_mentor: boolean }) => {
    dispatch(setJumpTarget(saved.id));

    if (saved.is_mentor) {
      navigate('/mentor');
      return;
    }

    dispatch(openConversationAsync(saved.conversation_id));
  };

  return (
    <aside className={`chat-sidebar ${isOpen ? 'chat-sidebar-open' : ''}`}>

      <div className="chat-sidebar-head">
        <div className="chat-tabs" role="tablist">
          <button
            className={`chat-tab ${tab === 'conversations' ? 'chat-tab-active' : ''}`}
            onClick={() => dispatch(setSidebarTab('conversations'))}
            role="tab"
            aria-selected={tab === 'conversations'}
          >
            שיחות
          </button>

          <button
            className={`chat-tab ${tab === 'starred' ? 'chat-tab-active' : ''}`}
            onClick={() => dispatch(setSidebarTab('starred'))}
            role="tab"
            aria-selected={tab === 'starred'}
          >
            <FaStar className="chat-tab-star" /> שמורות
            {starred.length > 0 && <span className="chat-tab-count">{starred.length}</span>}
          </button>
        </div>

        <button
          className="chat-sidebar-close"
          onClick={() => dispatch(closeSidebar())}
          aria-label="סגירת התפריט"
        >
          <FiX />
        </button>
      </div>

      {tab === 'conversations' ? (
        <>
          <button
            className="chat-new"
            onClick={() => dispatch(createConversationAsync())}
            disabled={isStreaming}
          >
            <FiEdit /> שיחה חדשה
          </button>

          <div className="chat-list">
            {isLoading && conversations.length === 0 && (
              <p className="chat-list-empty">טוען...</p>
            )}

            {!isLoading && conversations.length === 0 && (
              <p className="chat-list-empty">עוד לא דיברתם. השאלה הראשונה תיפתח כאן.</p>
            )}

            {conversations.map((conversation) => (
              <ConversationRow key={conversation.id} id={conversation.id} title={conversation.title} />
            ))}
          </div>
        </>
      ) : (
        <div className="chat-list chat-list-saved">
          {starred.length === 0 ? (
            <p className="chat-list-empty">
              כוכב על תשובה שומר אותה כאן, ולחיצה עליה מחזירה אותך בדיוק למקום שבו היא נאמרה.
            </p>
          ) : (
            starred.map((saved) => (
              <button
                key={saved.id}
                className="chat-saved"
                onClick={() => openSaved(saved)}
                disabled={isStreaming}
              >
                <span className="chat-saved-head">
                  {saved.role === 'assistant'
                    ? <span className="chat-saved-mark"><LarsonMark state="idle" /></span>
                    : <span className="chat-saved-mine">השאלה שלך</span>}

                  <FiCornerUpLeft className="chat-saved-go" />
                </span>

                <span className="chat-saved-text">
                  {saved.content.slice(0, PREVIEW_LENGTH)}
                  {saved.content.length > PREVIEW_LENGTH && '…'}
                </span>

                {/* Where it came from, and - when that is the mentor - a mark saying so.
                    Following this one leaves the chat entirely, and a row that looked
                    identical to its neighbours would make that feel like a misfire. */}
                <span className="chat-saved-origin">
                  {saved.is_mentor && <FiActivity className="chat-saved-origin-icon" />}
                  {saved.conversation_title}
                </span>
              </button>
            ))
          )}
        </div>
      )}

    </aside>
  )
}

export default ChatSidebar

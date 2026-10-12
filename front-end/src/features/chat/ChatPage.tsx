import { useEffect } from 'react'
import Dialog from '@mui/material/Dialog'
import { FiAlertTriangle, FiMenu, FiUploadCloud } from 'react-icons/fi'
import { useNavigate } from 'react-router-dom'
import { useAppDispatch, useAppSelector } from '../../app/hooks'
import { selectIsLogged } from '../authentication/authenticationSlice'
import LarsonPresence, { presenceState } from '../larson/LarsonPresence'
import { getUsageAsync } from '../usage/usageSlice'
import Problem from '../base/Problem'
import ChatComposer from './ChatComposer'
import ChatSidebar from './ChatSidebar'
import ChatThread from './ChatThread'
import { setPendingFile } from './chatAPI'
import {
  closeDeleteDialog, closeSidebar, deleteConversationAsync, getConversationsAsync,
  getStarredAsync, resetChatMessage, selectActiveId, selectChatMessage, selectConversations,
  selectDeleteTargetId, selectIsDragging, selectIsSidebarOpen, selectIsStreaming,
  selectIsWaiting, selectMessages, setAttachmentName, setDragging, toggleSidebar
} from './chatSlice'
import './chat.css'



/**
 * The chat with Larson.
 *
 * The page is one lit object on a dark ground: an aura around the shell in the product's
 * gold, and the same hairline the written profile carries. It is the same treatment for the
 * same reason - this is a place where something is said, not a place where numbers are
 * listed.
 *
 * The glow answers to state rather than decorating: it lifts while Larson is writing and
 * settles when he stops.
 */
const ChatPage = () => {

  const dispatch = useAppDispatch();
  const navigate = useNavigate();

  const isLogged = useAppSelector(selectIsLogged);
  const isStreaming = useAppSelector(selectIsStreaming);
  const isSidebarOpen = useAppSelector(selectIsSidebarOpen);
  const isDragging = useAppSelector(selectIsDragging);
  const conversations = useAppSelector(selectConversations);
  const activeId = useAppSelector(selectActiveId);
  const deleteTargetId = useAppSelector(selectDeleteTargetId);
  const message = useAppSelector(selectChatMessage);
  const messages = useAppSelector(selectMessages);
  const isWaiting = useAppSelector(selectIsWaiting);

  useEffect(() => {
    if (!isLogged) {
      navigate('/authentication/login');
      return;
    }
    dispatch(getConversationsAsync());
    dispatch(getStarredAsync());

    // Read once, here. After this the fresh figure rides the last event of every answer.
    dispatch(getUsageAsync());
  }, [isLogged, dispatch]);

  // **Not cleared on arrival.** It used to be read, toasted and wiped in the same breath,
  // which is why it had to be a toast: nothing held it. It stays in the store until he
  // closes it or sends again, and renders above the composer - next to the thing that
  // failed rather than in a corner.
  const dismiss = () => dispatch(resetChatMessage());

  // Dropping a file anywhere over the conversation attaches it, the same gesture the upload
  // screen already teaches. It only stages the file - nothing is sent until the trader says
  // what he wants compared.
  const onDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    dispatch(setDragging(false));

    if (isStreaming) return;

    const file = event.dataTransfer.files?.[0];
    if (!file) return;

    setPendingFile(file);
    dispatch(setAttachmentName(file.name));
  };

  const doomed = conversations.find((c) => c.id === deleteTargetId);

  return (
    <div className="app-container chat-page">

      {/* Sits behind everything and outside the shell, which is what makes it read as light
          around the chat rather than a background inside it. */}
      <div className={`chat-aura ${isStreaming ? 'chat-aura-live' : ''}`} aria-hidden="true" />

      <div className="chat-shell">

        <ChatSidebar />

        {/* On a phone the sidebar slides over the thread; tapping the thread behind it is
            the gesture everyone already expects to close it. */}
        {isSidebarOpen && (
          <div className="chat-scrim" onClick={() => dispatch(closeSidebar())} aria-hidden="true" />
        )}

        <div
          className="chat-main"
          onDragOver={(event) => { event.preventDefault(); dispatch(setDragging(true)); }}
          onDragLeave={(event) => {
            // Only when the pointer has actually left the column. Without this check, moving
            // over any child fires a leave and the overlay strobes.
            if (!event.currentTarget.contains(event.relatedTarget as Node)) {
              dispatch(setDragging(false));
            }
          }}
          onDrop={onDrop}
        >

          <div className="chat-topbar">
            <div className="chat-topbar-side">
              {/* The button only on a phone, where the list is a drawer. On anything wider it
                  would be a button to something already on screen. */}
              <button
                className="chat-topbar-menu"
                onClick={() => dispatch(toggleSidebar())}
                aria-label="השיחות שלך"
              >
                <FiMenu />
              </button>

              {/* **An `h1` and not a `span`, and it costs nothing visually.** Measured on
                  the live site: with a conversation open this screen had **zero headings**,
                  so a screen reader navigating by heading - which is how it is navigated -
                  got nothing at all, on the one element that says which conversation this
                  is. `.chat-topbar-title` already sets its own size and weight, so the tag
                  change moves no pixels. The empty state has its own `h1`, which is why this
                  was invisible until the thread was not empty. */}
              <h1 className="chat-topbar-title">
                {conversations.find((c) => c.id === activeId)?.title || 'שיחה עם לארסון'}
              </h1>
            </div>

            {/* Him, at a size the state can be read at, in the fixed strip that never
                scrolls away. The badge sets `display: contents` inside this bar, so the disc
                lands on the bar's centre line by itself and the words take the track beside
                it - centring the pair would have left the disc off to one side. The gold pill that used to sit at the end of this bar said the
                same thing in 0.74rem text beside a 6px dot - which is exactly the version
                that was easy to miss.

                The resting line still says what the pill said, because it is the honest
                promise of this screen: he answers out of the trader's own numbers.

                A verdict is only ever computed for a mentor debrief, so here he moves
                between thinking and resting. Handing the chat a green or a red would mean
                inventing one, and a colour that means nothing is worse than no colour. */}
            <LarsonPresence
              state={presenceState(isWaiting || isStreaming, messages)}
              idleNote="מחובר לרזומה שלך"
            />
          </div>

          <ChatThread />

          {message && <Problem onClose={dismiss}>{message}</Problem>}

          <ChatComposer />

          {isDragging && (
            <div className="chat-drop" aria-hidden="true">
              <FiUploadCloud className="chat-drop-icon" />
              <span className="chat-drop-title">שחרר כאן</span>
              <span className="chat-drop-note">מסמך זמני להשוואה · לא נשמר לרזומה</span>
            </div>
          )}

        </div>

      </div>

      {/* MUI for the behaviour only - focus trap, escape, backdrop. Writing that by hand is
          the kind of accessibility work the rule about importing a component exists for. */}
      <Dialog
        open={Boolean(deleteTargetId)}
        onClose={() => dispatch(closeDeleteDialog())}
        /* MUI locks body scroll while a dialog is open and compensates with padding. The
           gutter is reserved on every page, so it measures a width to compensate for and
           shifts the whole layout sideways as the dialog appears. */
        disableScrollLock
        aria-labelledby="chat-delete-title"
      >
        <div className="chat-confirm">
          <span className="chat-confirm-icon"><FiAlertTriangle /></span>

          <h2 className="chat-confirm-title" id="chat-delete-title">למחוק את השיחה?</h2>

          <p className="chat-confirm-body">
            {doomed && <b className="chat-confirm-name">{doomed.title}</b>}
            כל ההודעות בשיחה הזו יימחקו מיד, יחד עם כל מה ששמרת בכוכב מתוכה.
            אי אפשר לשחזר.
          </p>

          <div className="chat-confirm-actions">
            <button
              className="app-btn app-btn-dark"
              onClick={() => dispatch(closeDeleteDialog())}
            >
              ביטול
            </button>

            <button
              className="app-btn chat-confirm-delete"
              onClick={() => deleteTargetId && dispatch(deleteConversationAsync(deleteTargetId))}
            >
              מחיקה
            </button>
          </div>
        </div>
      </Dialog>

    </div>
  )
}

export default ChatPage

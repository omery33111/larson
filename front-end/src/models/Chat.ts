export interface ChatMessage {
    id: number;
    role: 'user' | 'assistant';
    content: string;
    attachment_name: string;

    // Only a debrief carries one: whether the new trades kept the rules his own history
    // argues for, or broke one. It is what turns the visor green or red.
    verdict?: 'kept' | 'broken' | '';

    is_starred: boolean;
    created_at: string;
}


/** A saved message, carrying the way back to the conversation it was said in. */
export interface StarredMessage {
    id: number;
    role: 'user' | 'assistant';
    content: string;
    conversation_id: number;
    conversation_title: string;

    // Which screen it was said on. The mentor is a conversation like any other in the
    // database but not in the product, so following a saved answer out of it means going to
    // his page rather than opening a thread in the chat.
    is_mentor: boolean;

    starred_at: string;
    created_at: string;
}


export interface Conversation {
    id: number;
    title: string;
    created_at: string;
    updated_at: string;
    message_count: number;
}


export interface ChatState {
    conversations: Conversation[];
    activeId: number | null;
    messages: ChatMessage[];

    starred: StarredMessage[];

    // Which half of the sidebar is showing.
    sidebarTab: 'conversations' | 'starred';

    // A saved answer was opened from the list, and the thread has to scroll to it and say
    // which one it was.
    jumpTargetId: number | null;

    // The conversation whose delete is waiting on a yes, and the one being renamed.
    deleteTargetId: number | null;
    renamingId: number | null;
    titleDraft: string;

    isDragging: boolean;

    // The answer as it arrives, kept apart from `messages` so a token does not rewrite the
    // whole thread on every frame.
    streamingText: string;
    isStreaming: boolean;

    // The row the server opened for this answer. Kept so the finished message lands in the
    // thread under its real id - a placeholder id would make its star button point at
    // nothing.
    streamingMessageId: number | null;

    // Between sending and the first token. This is the window Larson's visor covers.
    isWaiting: boolean;

    draft: string;

    // Only the name lives here. The File itself is held outside the store, because a File
    // is not serializable and Redux is not the right place for one.
    attachmentName: string;

    isSidebarOpen: boolean;
    isLoadingConversations: boolean;
    isLoadingThread: boolean;
    isLoadingStarred: boolean;

    message: string;
}

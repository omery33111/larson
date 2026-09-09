import { createSlice, createAsyncThunk } from "@reduxjs/toolkit"
import { RootState } from "../../app/store";
import { sessionExpired } from "../authentication/authenticationSlice";
import { ChatState } from "../../models/Chat";
import chatService, { StreamEvent, takePendingFile } from "./chatAPI";


const initialState: ChatState =
{
    conversations: [],
    activeId: null,
    messages: [],

    starred: [],
    sidebarTab: "conversations",
    jumpTargetId: null,

    deleteTargetId: null,
    renamingId: null,
    titleDraft: "",

    isDragging: false,

    streamingText: "",
    isStreaming: false,
    streamingMessageId: null,
    isWaiting: false,

    draft: "",
    attachmentName: "",

    isSidebarOpen: false,
    isLoadingConversations: false,
    isLoadingThread: false,
    isLoadingStarred: false,

    message: "",
};



// The one running answer. It is a module variable and not state because nothing renders it -
// the only thing anyone does with it is call abort().
let controller: AbortController | null = null;



export const getConversationsAsync = createAsyncThunk("chat/conversations", async (_, thunkAPI) => {
    try {
        return await chatService.getConversations();
    } catch (error: any) {
        if (error.response?.status === 401) {
            return thunkAPI.rejectWithValue("");
        }
        return thunkAPI.rejectWithValue("שגיאה בטעינת השיחות.");
    }
});



export const createConversationAsync = createAsyncThunk("chat/create", async (_, thunkAPI) => {
    try {
        return await chatService.createConversation();
    } catch (error: any) {
        if (error.response?.status === 401) {
            return thunkAPI.rejectWithValue("");
        }
        return thunkAPI.rejectWithValue("לא הצלחנו לפתוח שיחה חדשה.");
    }
});



export const openConversationAsync = createAsyncThunk("chat/open", async (id: number, thunkAPI) => {
    try {
        return await chatService.getConversation(id);
    } catch (error: any) {
        if (error.response?.status === 401) {
            return thunkAPI.rejectWithValue("");
        }
        return thunkAPI.rejectWithValue("שגיאה בטעינת השיחה.");
    }
});



export const deleteConversationAsync = createAsyncThunk("chat/delete", async (id: number, thunkAPI) => {
    try {
        const deleted = await chatService.deleteConversation(id);

        // Its messages went with it, and so did anything saved out of them.
        thunkAPI.dispatch(getStarredAsync());

        return deleted;
    } catch (error: any) {
        if (error.response?.status === 401) {
            return thunkAPI.rejectWithValue("");
        }
        return thunkAPI.rejectWithValue("מחיקת השיחה נכשלה.");
    }
});



export const renameConversationAsync = createAsyncThunk(
    "chat/rename", async (payload: { id: number; title: string }, thunkAPI) => {
    try {
        return await chatService.renameConversation(payload.id, payload.title);
    } catch (error: any) {
        if (error.response?.status === 401) {
            return thunkAPI.rejectWithValue("");
        }
        return thunkAPI.rejectWithValue(error.response?.data?.error || "שינוי השם נכשל.");
    }
});



export const getStarredAsync = createAsyncThunk("chat/starred", async (_, thunkAPI) => {
    try {
        return await chatService.getStarred();
    } catch (error: any) {
        if (error.response?.status === 401) {
            return thunkAPI.rejectWithValue("");
        }
        return thunkAPI.rejectWithValue("שגיאה בטעינת ההודעות השמורות.");
    }
});



export const toggleStarAsync = createAsyncThunk("chat/star", async (id: number, thunkAPI) => {
    try {
        const result = await chatService.toggleStar(id);

        // The list is re-read rather than patched in place: it is ordered by when things were
        // saved, and the server is the one holding that clock.
        thunkAPI.dispatch(getStarredAsync());

        return result;
    } catch (error: any) {
        if (error.response?.status === 401) {
            return thunkAPI.rejectWithValue("");
        }
        return thunkAPI.rejectWithValue("לא הצלחנו לשמור את ההודעה.");
    }
});



// ------------------------- THE STREAMED ANSWER -------------------------
//
// Every token dispatches. That sounds expensive and is not: the running text lives in one
// field of its own, so a delta re-renders the bubble being written and nothing else.

export const sendMessageAsync = createAsyncThunk("chat/send", async (text: string, thunkAPI) => {
    const state = thunkAPI.getState() as RootState;

    let id = state.chat.activeId;

    // Typing on the empty screen opens a conversation. Asking the user to press "new chat"
    // before he is allowed to ask anything is a step that exists only for the database.
    if (!id) {
        const created: any = await thunkAPI.dispatch(createConversationAsync()).unwrap()
            .catch(() => null);

        if (!created) return thunkAPI.rejectWithValue("לא הצלחנו לפתוח שיחה חדשה.");

        id = created.id;
    }

    const file = takePendingFile();

    controller = new AbortController();

    let failure = "";

    try {
        await chatService.streamMessage(id!, text, file, (event: StreamEvent) => {
            if (event.type === 'start') {
                thunkAPI.dispatch(streamOpened(event));
            }
            else if (event.type === 'delta') {
                thunkAPI.dispatch(streamDelta(event.text));
            }
            else if (event.type === 'error') {
                failure = event.error;
            }
        }, controller.signal);
    } catch (error: any) {
        // Stopping the answer is a decision, not a failure. Whatever arrived stays on
        // screen, and the server has already stored the same partial text.
        if (error?.name !== 'AbortError') {
            if (error?.status === 401) {
                thunkAPI.dispatch(sessionExpired());
                return thunkAPI.rejectWithValue("");
            }
            failure = "החיבור לשרת נקטע.";
        }
    } finally {
        controller = null;
    }

    if (failure) {
        // The partial answer is kept even so - it is already in the thread on the server,
        // and blanking it here would make the two disagree.
        return thunkAPI.rejectWithValue(failure);
    }

    return true;
});


export const stopStreaming = () => {
    controller?.abort();
};



export const chatSlice = createSlice({
    name: "chat",
    initialState,
    reducers: {
        resetChatMessage: (state) =>
        {
            state.message = ""
        },

        setDraft: (state, action) =>
        {
            state.draft = action.payload
        },

        setAttachmentName: (state, action) =>
        {
            state.attachmentName = action.payload
        },

        toggleSidebar: (state) =>
        {
            state.isSidebarOpen = !state.isSidebarOpen
        },

        setSidebarTab: (state, action) =>
        {
            state.sidebarTab = action.payload
        },

        setDragging: (state, action) =>
        {
            state.isDragging = action.payload
        },

        // ------------- DELETING A CONVERSATION:
        openDeleteDialog: (state, action) =>
        {
            state.deleteTargetId = action.payload
        },

        closeDeleteDialog: (state) =>
        {
            state.deleteTargetId = null
        },

        // ------------- RENAMING:
        startRenaming: (state, action) =>
        {
            state.renamingId = action.payload
            state.titleDraft = state.conversations.find((c) => c.id === action.payload)?.title || ""
        },

        setTitleDraft: (state, action) =>
        {
            state.titleDraft = action.payload
        },

        cancelRenaming: (state) =>
        {
            state.renamingId = null
            state.titleDraft = ""
        },

        // ------------- JUMPING TO A SAVED ANSWER:
        setJumpTarget: (state, action) =>
        {
            state.jumpTargetId = action.payload
            state.isSidebarOpen = false
        },

        clearJumpTarget: (state) =>
        {
            state.jumpTargetId = null
        },

        closeSidebar: (state) =>
        {
            state.isSidebarOpen = false
        },

        // ------------- STREAMING:
        streamOpened: (state, action) =>
        {
            state.isWaiting = true
            state.streamingMessageId = action.payload.message_id

            // The question was shown the moment it was sent, under a placeholder id. This is
            // where it gets the real one.
            const pending = state.messages[state.messages.length - 1]

            if (pending && pending.id === 0) {
                pending.id = action.payload.question_id
            }

            const conversation = state.conversations.find((c) => c.id === state.activeId)

            if (conversation) {
                conversation.title = action.payload.title
            }
        },

        streamDelta: (state, action) =>
        {
            // The first token is the end of waiting. From here the text itself is the
            // evidence that something is happening.
            state.isWaiting = false
            state.streamingText += action.payload
        },
    },
    extraReducers: (builder) => {
        builder
        .addCase(getConversationsAsync.pending, (state) =>
        {
            state.isLoadingConversations = true
        })
        .addCase(getConversationsAsync.fulfilled, (state, action) =>
        {
            state.isLoadingConversations = false
            state.conversations = action.payload
        })
        .addCase(getConversationsAsync.rejected, (state, action) =>
        {
            state.isLoadingConversations = false
            state.message = action.payload as string
        })


        .addCase(createConversationAsync.fulfilled, (state, action) =>
        {
            state.conversations.unshift(action.payload)
            state.activeId = action.payload.id
            state.isSidebarOpen = false

            // Typing the first question on the empty screen opens a conversation from inside
            // the send, and by then that question is already on screen - it was put there by
            // `sendMessageAsync.pending`, before this ran. Clearing unconditionally made it
            // vanish the instant the conversation it belongs to was created.
            if (!state.isStreaming) {
                state.messages = []
            }
        })
        .addCase(createConversationAsync.rejected, (state, action) =>
        {
            state.message = action.payload as string
        })


        .addCase(openConversationAsync.pending, (state, action) =>
        {
            state.isLoadingThread = true
            state.activeId = action.meta.arg
            state.messages = []
            state.streamingText = ""
            state.isSidebarOpen = false
        })
        .addCase(openConversationAsync.fulfilled, (state, action) =>
        {
            state.isLoadingThread = false
            state.messages = action.payload.messages
        })
        .addCase(openConversationAsync.rejected, (state, action) =>
        {
            state.isLoadingThread = false
            state.message = action.payload as string
        })


        .addCase(renameConversationAsync.fulfilled, (state, action) =>
        {
            const row = state.conversations.find((c) => c.id === action.payload.id)

            if (row) {
                row.title = action.payload.title
            }

            state.renamingId = null
            state.titleDraft = ""
        })
        .addCase(renameConversationAsync.rejected, (state, action) =>
        {
            state.renamingId = null
            state.message = action.payload as string
        })


        .addCase(getStarredAsync.pending, (state) =>
        {
            state.isLoadingStarred = true
        })
        .addCase(getStarredAsync.fulfilled, (state, action) =>
        {
            state.isLoadingStarred = false
            state.starred = action.payload
        })
        .addCase(getStarredAsync.rejected, (state, action) =>
        {
            state.isLoadingStarred = false
            state.message = action.payload as string
        })


        .addCase(toggleStarAsync.fulfilled, (state, action) =>
        {
            // The star on the message itself is what the thread renders; the list beside it
            // is refreshed separately by the thunk.
            const row = state.messages.find((m) => m.id === action.payload.id)

            if (row) {
                row.is_starred = action.payload.is_starred
            }
        })
        .addCase(toggleStarAsync.rejected, (state, action) =>
        {
            state.message = action.payload as string
        })


        .addCase(deleteConversationAsync.fulfilled, (state, action) =>
        {
            state.conversations = state.conversations.filter((c) => c.id !== action.payload)
            state.deleteTargetId = null

            // Deleting the thread you are reading leaves the screen on the empty state
            // rather than on a conversation that no longer exists.
            if (state.activeId === action.payload) {
                state.activeId = null
                state.messages = []
                state.streamingText = ""
            }
        })
        .addCase(deleteConversationAsync.rejected, (state, action) =>
        {
            state.deleteTargetId = null
            state.message = action.payload as string
        })


        .addCase(sendMessageAsync.pending, (state, action) =>
        {
            state.isStreaming = true
            state.isWaiting = true
            state.streamingText = ""
            state.message = ""

            // Shown immediately, under a placeholder id that `streamOpened` replaces. The
            // question must not wait for the server to acknowledge it.
            state.messages.push({
                id: 0,
                role: 'user',
                content: action.meta.arg,
                attachment_name: state.attachmentName,
                is_starred: false,
                created_at: new Date().toISOString(),
            })

            state.draft = ""
            state.attachmentName = ""
        })
        .addCase(sendMessageAsync.fulfilled, (state) =>
        {
            settle(state)
        })
        .addCase(sendMessageAsync.rejected, (state, action) =>
        {
            settle(state)
            state.message = action.payload as string
        });
    }

})


/** Moves the answer that was being written into the thread itself. */
function settle(state: ChatState) {
    state.isStreaming = false
    state.isWaiting = false

    if (state.streamingText.trim()) {
        state.messages.push({
            // The real row id, handed over in the `start` event. Anything invented here would
            // give the answer a star button that saves a message the server does not have.
            id: state.streamingMessageId ?? 0,
            role: 'assistant',
            content: state.streamingText,
            attachment_name: "",
            is_starred: false,
            created_at: new Date().toISOString(),
        })
    }

    state.streamingText = ""
    state.streamingMessageId = null
}


export const selectConversations = (state: RootState) => state.chat.conversations;
export const selectActiveId = (state: RootState) => state.chat.activeId;
export const selectMessages = (state: RootState) => state.chat.messages;
export const selectStreamingText = (state: RootState) => state.chat.streamingText;
export const selectIsStreaming = (state: RootState) => state.chat.isStreaming;
export const selectIsWaiting = (state: RootState) => state.chat.isWaiting;
export const selectDraft = (state: RootState) => state.chat.draft;
export const selectAttachmentName = (state: RootState) => state.chat.attachmentName;
export const selectIsSidebarOpen = (state: RootState) => state.chat.isSidebarOpen;
export const selectIsLoadingConversations = (state: RootState) => state.chat.isLoadingConversations;
export const selectIsLoadingThread = (state: RootState) => state.chat.isLoadingThread;
export const selectChatMessage = (state: RootState) => state.chat.message;
export const selectStarred = (state: RootState) => state.chat.starred;
export const selectSidebarTab = (state: RootState) => state.chat.sidebarTab;
export const selectJumpTargetId = (state: RootState) => state.chat.jumpTargetId;
export const selectDeleteTargetId = (state: RootState) => state.chat.deleteTargetId;
export const selectRenamingId = (state: RootState) => state.chat.renamingId;
export const selectTitleDraft = (state: RootState) => state.chat.titleDraft;
export const selectIsDragging = (state: RootState) => state.chat.isDragging;
export const selectIsLoadingStarred = (state: RootState) => state.chat.isLoadingStarred;

export const {
    resetChatMessage, setDraft, setAttachmentName,
    toggleSidebar, closeSidebar, setSidebarTab, setDragging,
    openDeleteDialog, closeDeleteDialog,
    startRenaming, setTitleDraft, cancelRenaming,
    setJumpTarget, clearJumpTarget,
    streamOpened, streamDelta,
} = chatSlice.actions;

export default chatSlice.reducer;

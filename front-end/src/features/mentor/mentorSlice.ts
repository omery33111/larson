import { createSlice, createAsyncThunk } from "@reduxjs/toolkit"
import { RootState } from "../../app/store";
import { usageReported } from "../usage/usageSlice";
import { sessionExpired } from "../authentication/authenticationSlice";
import { confirmTradesAsync, resetIngestion, uploadTradesAsync } from "../trades/tradesSlice";
import { MentorState } from "../../models/Mentor";
import { StreamEvent } from "../chat/chatAPI";
import { toggleStarAsync } from "../chat/chatSlice";
import mentorService from "./mentorAPI";


const initialState: MentorState =
{
    messages: [],
    resume: { total_trades: 0, last_trade: null, days_since: null },

    streamingText: "",
    streamingMessageId: null,
    streamingVerdict: "",
    isStreaming: false,
    isWaiting: false,

    draft: "",

    isAwaitingConfirm: false,
    pendingFile: null,

    isDragging: false,
    isLoading: false,

    message: "",

    rules: [],
    ruleCoverage: null,
    hasLabels: true,
    ruleKinds: [],
    isRulesOpen: false,
    isRulesLoading: false,
};



let controller: AbortController | null = null;



// Takes the waiting file off the composer. Nothing leaves the resume - those trades were
// saved the moment he confirmed them - so this only drops a debrief he decided against.
export const dismissPendingAsync = createAsyncThunk("mentor/dismissPending", async (_, thunkAPI) => {
    try {
        return await mentorService.dismissPending();
    } catch (error: any) {
        if (error.response?.status === 401) {
            return thunkAPI.rejectWithValue("");
        }
        return thunkAPI.rejectWithValue("לא הצלחנו להסיר את הקובץ.");
    }
});


export const getMentorAsync = createAsyncThunk("mentor/get", async (_, thunkAPI) => {
    try {
        return await mentorService.getMentor();
    } catch (error: any) {
        if (error.response?.status === 401) {
            return thunkAPI.rejectWithValue("");
        }
        return thunkAPI.rejectWithValue("שגיאה בטעינת המנטור.");
    }
});



/**
 * One thunk for both kinds of turn.
 *
 * A debrief carries a `trade_file_id`, a plain question carries text, and a debrief may carry
 * both: writing a line to go with the file is the natural thing to do, and it is the one
 * chance the trader has to say what the numbers cannot - that he was tired, that he was
 * testing something, that he already knows what went wrong. The server decides what any of
 * it means; it is the only side that can, because only it knows the file was really
 * confirmed.
 */
export const sendToMentorAsync = createAsyncThunk(
    "mentor/send", async (payload: { message?: string; fileId?: number }, thunkAPI) => {

    controller = new AbortController();

    let failure = "";

    const body = payload.fileId
        ? { trade_file_id: payload.fileId, message: payload.message || "" }
        : { message: payload.message || "" };

    try {
        await mentorService.streamDebrief(body, (event: StreamEvent) => {
            if (event.type === 'start') {
                thunkAPI.dispatch(debriefOpened(event));
            }
            else if (event.type === 'delta') {
                thunkAPI.dispatch(debriefDelta(event.text));
            }
            else if (event.type === 'done') {
            // The quota rides the last event of every answer - and the refusal too, which is
            // the one time the client most needs the fresh figure. Nothing polls for it.
                thunkAPI.dispatch(usageReported(event.usage));
            }
            else if (event.type === 'error') {
                failure = event.error;
                thunkAPI.dispatch(usageReported(event.usage));
            }
        }, controller.signal);
    } catch (error: any) {
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
        return thunkAPI.rejectWithValue(failure);
    }

    // The resume grew, so the staleness the page reports has to be re-read rather than
    // guessed at from the client's clock.
    thunkAPI.dispatch(getMentorAsync());

    return true;
});


export const stopMentor = () => {
    controller?.abort();
};



// ------------------------- THE RULES HE SETS FOR HIMSELF -------------------------
//
// **What separates a mentor from an auditor.** The debrief has always derived rules from the
// record - the losing buckets, each with the evidence behind it - and that finds what is
// broken. What it could not do was hold him to something **he decided**, because nothing
// stored that he had decided it.

export const getRulesAsync = createAsyncThunk("mentor/getRules", async (_, thunkAPI) => {
    try {
        return await mentorService.getRules();
    } catch (error: any) {
        if (error.response?.status === 401) {
            thunkAPI.dispatch(sessionExpired());
            return thunkAPI.rejectWithValue("");
        }
        return thunkAPI.rejectWithValue(error.response?.data?.error || "לא הצלחנו לטעון את הכללים.");
    }
});


export const saveRuleAsync = createAsyncThunk(
    "mentor/saveRule",
    async (payload: Record<string, unknown>, thunkAPI) => {
        try {
            return await mentorService.saveRule(payload);
        } catch (error: any) {
            if (error.response?.status === 401) {
                thunkAPI.dispatch(sessionExpired());
                return thunkAPI.rejectWithValue("");
            }
            return thunkAPI.rejectWithValue(error.response?.data?.error || "לא הצלחנו לשמור את הכלל.");
        }
    });


export const deleteRuleAsync = createAsyncThunk(
    "mentor/deleteRule",
    async (id: number, thunkAPI) => {
        try {
            return await mentorService.deleteRule(id);
        } catch (error: any) {
            if (error.response?.status === 401) {
                thunkAPI.dispatch(sessionExpired());
                return thunkAPI.rejectWithValue("");
            }
            return thunkAPI.rejectWithValue(error.response?.data?.error || "לא הצלחנו למחוק את הכלל.");
        }
    });



export const mentorSlice = createSlice({
    name: "mentor",
    initialState,
    reducers: {
        resetMentorMessage: (state) =>
        {
            state.message = ""
        },

        // The panel opens on a dispatch and renders itself from the store, with no props and
        // no useState in the parent - the same pattern every other modal in this project uses.
        openRules: (state) =>
        {
            state.isRulesOpen = true
        },

        closeRules: (state) =>
        {
            state.isRulesOpen = false;
            state.ruleCoverage = null
        },

        setMentorDraft: (state, action) =>
        {
            state.draft = action.payload
        },

        setMentorDragging: (state, action) =>
        {
            state.isDragging = action.payload
        },

        // The mentor is the one who opened the ingestion dialog, so the confirmation that
        // follows belongs to him.
        expectIngestion: (state) =>
        {
            state.isAwaitingConfirm = true
        },

        debriefOpened: (state, action) =>
        {
            state.isWaiting = true
            state.streamingMessageId = action.payload.message_id
            state.streamingVerdict = action.payload.verdict || ""
        },

        debriefDelta: (state, action) =>
        {
            state.isWaiting = false
            state.streamingText += action.payload
        },
    },
    extraReducers: (builder) => {
        builder
        .addCase(getMentorAsync.pending, (state) =>
        {
            state.isLoading = true
        })
        .addCase(getMentorAsync.fulfilled, (state, action) =>
        {
            state.isLoading = false
            state.resume = action.payload.resume
            state.pendingFile = action.payload.pending_file || null

            // Never while an answer is arriving: this also runs right after a debrief, to
            // refresh the resume state, and replacing the thread mid-stream would drop the
            // bubble being written into.
            if (!state.isStreaming) {
                state.messages = action.payload.messages
            }
        })
        .addCase(getMentorAsync.rejected, (state, action) =>
        {
            state.isLoading = false
            state.message = action.payload as string
        })


        .addCase(sendToMentorAsync.pending, (state, action) =>
        {
            state.isStreaming = true
            state.isWaiting = true
            state.streamingText = ""
            state.streamingVerdict = ""
            state.message = ""

            // A debrief sent with no typed text has to say what was actually sent. Without
            // it the thread showed an answer to a question nobody could see being asked.
            const name = state.pendingFile?.original_name || ""
            const sentFile = Boolean(action.meta.arg.fileId)

            state.messages.push({
                id: 0,
                role: 'user',
                content: action.meta.arg.message || `עדכון: ${name || 'העסקאות האחרונות שלי'}`,
                attachment_name: sentFile ? name : "",
                is_starred: false,
                created_at: new Date().toISOString(),
            })

            state.draft = ""

            // The slot empties the moment it is sent, so a second press cannot send it twice.
            // The server does the same on its side rather than trusting this.
            if (sentFile) {
                state.pendingFile = null
            }
        })
        .addCase(sendToMentorAsync.fulfilled, (state) =>
        {
            settle(state)
        })
        .addCase(sendToMentorAsync.rejected, (state, action) =>
        {
            settle(state)
            state.message = action.payload as string
        })


        // ------------- LISTENING TO THE INGESTION:
        // The confirmation dialog belongs to the trades feature, and reusing it whole is the
        // point - it is the same gate, and the trader already knows it from the upload
        // screen. What is left is knowing when it was this page that opened it.
        .addCase(confirmTradesAsync.fulfilled, (state) =>
        {
            // The file does not go anywhere yet. Confirming it saved the trades; sending it
            // is a separate decision, and the trader may well want to write the line that
            // goes with it only after he has chosen the file. The slot itself is filled from
            // the server on the refresh that follows, so it survives him leaving the page.
            state.isAwaitingConfirm = false
        })
        .addCase(uploadTradesAsync.rejected, (state) =>
        {
            state.isAwaitingConfirm = false
        })
        .addCase(resetIngestion, (state) =>
        {
            state.isAwaitingConfirm = false
        })


        // ------------- SAVING AN ANSWER:
        // The star itself is the chat's machinery and stays there - one endpoint, one list.
        // What this screen owns is its own copy of the message, which has to light up the
        // moment it is saved rather than on the next reload.
        .addCase(toggleStarAsync.fulfilled, (state, action) =>
        {
            const row = state.messages.find((m) => m.id === action.payload.id)

            if (row) {
                row.is_starred = action.payload.is_starred
            }
        })


        .addCase(getRulesAsync.pending, (state) =>
        {
            state.isRulesLoading = true;
        })
        .addCase(getRulesAsync.fulfilled, (state, action) =>
        {
            state.isRulesLoading = false;
            state.rules = action.payload.rules;
            state.hasLabels = action.payload.has_labels ?? true;
            state.ruleKinds = action.payload.kinds;
        })
        .addCase(getRulesAsync.rejected, (state, action) =>
        {
            state.isRulesLoading = false;
            state.message = action.payload as string;
        })

        .addCase(saveRuleAsync.fulfilled, (state, action) =>
        {
            // **Replaced by id for the free-text kind and by kind for the rest**, because
            // that is exactly what the database enforces: one of each structured kind, and
            // as many of his own as he writes. Filtering by kind alone would have each new
            // sentence swallow the one before it.
            const saved = action.payload;

            state.rules = [
                ...state.rules.filter((rule) => saved.kind === "custom"
                    ? rule.id !== saved.id
                    : rule.kind !== saved.kind),
                saved,
            ];

            // How many of his trades can answer it, shown once beside the rule he just wrote.
            state.ruleCoverage = saved.coverage
                ? { id: saved.id, lookingFor: saved.looking_for || "", ...saved.coverage }
                : null;
        })
        .addCase(saveRuleAsync.rejected, (state, action) =>
        {
            state.message = action.payload as string;
        })

        .addCase(deleteRuleAsync.fulfilled, (state, action) =>
        {
            state.rules = state.rules.filter((rule) => rule.id !== action.payload);
        })
        .addCase(deleteRuleAsync.rejected, (state, action) =>
        {
            state.message = action.payload as string;
        })

        .addCase(dismissPendingAsync.fulfilled, (state) =>
        {
            state.pendingFile = null
        })
        .addCase(dismissPendingAsync.rejected, (state, action) =>
        {
            state.message = action.payload as string
        });
    }

})


function settle(state: MentorState) {
    state.isStreaming = false
    state.isWaiting = false

    if (state.streamingText.trim()) {
        state.messages.push({
            id: state.streamingMessageId ?? 0,
            role: 'assistant',
            content: state.streamingText,
            attachment_name: "",
            verdict: state.streamingVerdict,
            is_starred: false,
            created_at: new Date().toISOString(),
        })
    }

    state.streamingText = ""
    state.streamingMessageId = null
    state.streamingVerdict = ""
}


export const selectRules = (state: RootState) => state.mentor.rules;

export const selectRuleCoverage = (state: RootState) => state.mentor.ruleCoverage;

export const selectHasLabels = (state: RootState) => state.mentor.hasLabels;
export const selectRuleKinds = (state: RootState) => state.mentor.ruleKinds;
export const selectIsRulesOpen = (state: RootState) => state.mentor.isRulesOpen;
export const selectIsRulesLoading = (state: RootState) => state.mentor.isRulesLoading;

export const selectMentorMessages = (state: RootState) => state.mentor.messages;
export const selectResumeState = (state: RootState) => state.mentor.resume;
export const selectMentorStreamingText = (state: RootState) => state.mentor.streamingText;
export const selectMentorIsStreaming = (state: RootState) => state.mentor.isStreaming;
export const selectMentorIsWaiting = (state: RootState) => state.mentor.isWaiting;
export const selectStreamingVerdict = (state: RootState) => state.mentor.streamingVerdict;
export const selectMentorDraft = (state: RootState) => state.mentor.draft;
export const selectMentorIsDragging = (state: RootState) => state.mentor.isDragging;
export const selectMentorIsLoading = (state: RootState) => state.mentor.isLoading;
export const selectPendingFile = (state: RootState) => state.mentor.pendingFile;
export const selectMentorMessage = (state: RootState) => state.mentor.message;

export const {
    resetMentorMessage, setMentorDraft, setMentorDragging,
    expectIngestion,
    debriefOpened, debriefDelta, openRules, closeRules,
} = mentorSlice.actions;

export default mentorSlice.reducer;

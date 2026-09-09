import { createSlice, createAsyncThunk } from "@reduxjs/toolkit"
import { RootState } from "../../app/store";
import { TradesState } from "../../models/Trade";
import tradesService from "./tradesAPI";


const initialState: TradesState =
{
    preview: null,
    confirmResult: null,
    summary: { total_trades: 0 },
    trades: [],

    isUploading: false,
    isConfirming: false,
    isLoading: false,

    isConfirmOpen: false,

    resumeVersion: 0,

    isResumeOpen: false,
    isArmed: false,
    isDeleting: false,

    message: "",
};



export const uploadTradesAsync = createAsyncThunk("trades/upload", async (file: File, thunkAPI) => {
    try {
        return await tradesService.uploadTrades(file);
    } catch (error: any) {
        if (error.response?.status === 401) {
            return thunkAPI.rejectWithValue("");
        }
        return thunkAPI.rejectWithValue(error.response?.data?.error || "שגיאה בהעלאת הקובץ.");
    }
});



export const confirmTradesAsync = createAsyncThunk("trades/confirm", async (tradeFileId: number, thunkAPI) => {
    try {
        // Which screen opened this gate decides what happens after it: a file confirmed from
        // the mentor waits there to be sent, one filed through "my resume" simply lands.
        const forMentor = (thunkAPI.getState() as RootState).mentor.isAwaitingConfirm;

        return await tradesService.confirmTrades(tradeFileId, forMentor);
    } catch (error: any) {
        if (error.response?.status === 401) {
            return thunkAPI.rejectWithValue("");
        }
        return thunkAPI.rejectWithValue(error.response?.data?.error || "שגיאה בשמירת העסקאות.");
    }
});



export const getSummaryAsync = createAsyncThunk("trades/summary", async () => {
    return await tradesService.getSummary();
});



export const getTradesAsync = createAsyncThunk("trades/list", async () => {
    return await tradesService.getTrades();
});



export const deleteResumeAsync = createAsyncThunk("trades/deleteResume", async (_, thunkAPI) => {
    try {
        return await tradesService.deleteResume();
    } catch (error: any) {
        if (error.response?.status === 401) {
            return thunkAPI.rejectWithValue("");
        }
        return thunkAPI.rejectWithValue("מחיקת הרזומה נכשלה.");
    }
});



export const tradesSlice = createSlice({
    name: "trades",
    initialState,
    reducers: {
        openConfirm: (state) =>
        {
            state.isConfirmOpen = true
        },

        closeConfirm: (state) =>
        {
            state.isConfirmOpen = false
        },

        // ------------- THE RESUME DIALOG:
        openResume: (state) =>
        {
            state.isResumeOpen = true
            state.isArmed = false
        },

        closeResume: (state) =>
        {
            state.isResumeOpen = false
            state.isArmed = false
        },

        armDeletion: (state) =>
        {
            state.isArmed = true
        },

        disarmDeletion: (state) =>
        {
            state.isArmed = false
        },

        resetIngestion: (state) =>
        {
            state.preview = null
            state.confirmResult = null
            state.isConfirmOpen = false
            state.message = ""
        },
    },
    extraReducers: (builder) => {
        builder
        .addCase(uploadTradesAsync.pending, (state) =>
        {
            state.isUploading = true
            state.message = ""
            state.confirmResult = null
        })
        .addCase(uploadTradesAsync.fulfilled, (state, action) =>
        {
            state.isUploading = false
            state.preview = action.payload
            state.isConfirmOpen = true
        })
        .addCase(uploadTradesAsync.rejected, (state, action) =>
        {
            state.isUploading = false
            state.preview = null
            state.message = action.payload as string
        })


        .addCase(confirmTradesAsync.pending, (state) =>
        {
            state.isConfirming = true
        })
        .addCase(confirmTradesAsync.fulfilled, (state, action) =>
        {
            state.isConfirming = false
            state.confirmResult = action.payload
            state.preview = null
            state.isConfirmOpen = false

            // The resume grew, and every screen computed from it is now describing the
            // version before this one.
            state.resumeVersion += 1
        })
        .addCase(confirmTradesAsync.rejected, (state, action) =>
        {
            state.isConfirming = false
            state.message = action.payload as string
        })


        .addCase(deleteResumeAsync.pending, (state) =>
        {
            state.isDeleting = true
        })
        .addCase(deleteResumeAsync.fulfilled, (state) =>
        {
            state.isDeleting = false
            state.isArmed = false
            state.isResumeOpen = false
            state.resumeVersion += 1

            // Everything the resume produced goes with it, on screen as well as on the
            // server - a summary left behind would describe trades that no longer exist.
            state.summary = { total_trades: 0 }
            state.trades = []
            state.preview = null
            state.confirmResult = null
        })
        .addCase(deleteResumeAsync.rejected, (state, action) =>
        {
            state.isDeleting = false
            state.isArmed = false
            state.message = action.payload as string
        })


        .addCase(getSummaryAsync.pending, (state) =>
        {
            state.isLoading = true
        })
        .addCase(getSummaryAsync.fulfilled, (state, action) =>
        {
            state.isLoading = false
            state.summary = action.payload
        })
        .addCase(getSummaryAsync.rejected, (state) =>
        {
            state.isLoading = false
        })


        .addCase(getTradesAsync.pending, (state) =>
        {
            state.isLoading = true
        })
        .addCase(getTradesAsync.fulfilled, (state, action) =>
        {
            state.isLoading = false
            state.trades = action.payload.results
        })
        .addCase(getTradesAsync.rejected, (state) =>
        {
            state.isLoading = false
        });
    }

})


export const selectPreview = (state: RootState) => state.trades.preview;
export const selectConfirmResult = (state: RootState) => state.trades.confirmResult;
export const selectSummary = (state: RootState) => state.trades.summary;
export const selectTrades = (state: RootState) => state.trades.trades;
export const selectIsUploading = (state: RootState) => state.trades.isUploading;
export const selectIsConfirming = (state: RootState) => state.trades.isConfirming;
export const selectTradesIsLoading = (state: RootState) => state.trades.isLoading;
export const selectIsConfirmOpen = (state: RootState) => state.trades.isConfirmOpen;
export const selectTradesMessage = (state: RootState) => state.trades.message;

export const selectResumeVersion = (state: RootState) => state.trades.resumeVersion;
export const selectIsResumeOpen = (state: RootState) => state.trades.isResumeOpen;
export const selectIsArmed = (state: RootState) => state.trades.isArmed;
export const selectIsDeleting = (state: RootState) => state.trades.isDeleting;

export const {
    openConfirm, closeConfirm, resetIngestion,
    openResume, closeResume, armDeletion, disarmDeletion,
} = tradesSlice.actions;

export default tradesSlice.reducer;

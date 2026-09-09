import { createSlice, createAsyncThunk } from "@reduxjs/toolkit"
import { RootState } from "../../app/store";
import { AnalyticsState } from "../../models/Analytics";
import analyticsService from "./analyticsAPI";


const initialState: AnalyticsState =
{
    overview: { total_trades: 0, has_enough_data: false },

    isLoading: false,
    isGenerating: false,

    // The secondary metrics start collapsed so the first screen stays focused on the
    // profile, the score and the three headline cards.
    isMetricsOpen: false,

    // null is "every account". The selector fills this in once the user narrows it.
    selectedAccounts: null,

    message: "",
};



export const getOverviewAsync = createAsyncThunk("analytics/overview", async (_, thunkAPI) => {
    try {
        const state = thunkAPI.getState() as RootState;
        return await analyticsService.getOverview(state.analytics.selectedAccounts);
    } catch (error: any) {
        // A 401 means the session died, and the interceptor already handled it by signing
        // the user out. Showing a feature-level error on top of that would blame the wrong
        // thing - the user is not looking at a broken profile page, they are logged out.
        if (error.response?.status === 401) {
            return thunkAPI.rejectWithValue("");
        }
        return thunkAPI.rejectWithValue(error.response?.data?.error || "שגיאה בטעינת הנתונים.");
    }
});



export const generateProfileAsync = createAsyncThunk("analytics/generateProfile", async (_, thunkAPI) => {
    try {
        const state = thunkAPI.getState() as RootState;
        return await analyticsService.generateProfile(state.analytics.selectedAccounts);
    } catch (error: any) {
        if (error.response?.status === 401) {
            return thunkAPI.rejectWithValue("");
        }
        return thunkAPI.rejectWithValue(error.response?.data?.error || "יצירת הפרופיל נכשלה.");
    }
});



export const analyticsSlice = createSlice({
    name: "analytics",
    initialState,
    reducers: {
        resetAnalyticsMessage: (state) =>
        {
            state.message = ""
        },

        toggleMetrics: (state) =>
        {
            state.isMetricsOpen = !state.isMetricsOpen
        },

        // ------------- ACCOUNT SELECTION:
        toggleAccount: (state, action) =>
        {
            const available = (state.overview.available_accounts || []).map((a) => a.account_id)
            const current = state.selectedAccounts ?? available

            const next = current.includes(action.payload)
                ? current.filter((id) => id !== action.payload)
                : [...current, action.payload]

            // Unticking the last one would leave a page with nothing to show, so the
            // selection is never allowed to empty out.
            state.selectedAccounts = next.length ? next : current
        },

        selectAllAccounts: (state) =>
        {
            state.selectedAccounts = null
        },

        selectOnlyAccount: (state, action) =>
        {
            state.selectedAccounts = [action.payload]
        },
    },
    extraReducers: (builder) => {
        builder
        .addCase(getOverviewAsync.pending, (state) =>
        {
            state.isLoading = true
        })
        .addCase(getOverviewAsync.fulfilled, (state, action) =>
        {
            state.isLoading = false
            state.overview = action.payload
        })
        .addCase(getOverviewAsync.rejected, (state, action) =>
        {
            state.isLoading = false
            state.message = action.payload as string
        })


        .addCase(generateProfileAsync.pending, (state) =>
        {
            state.isGenerating = true
            state.message = ""
        })
        .addCase(generateProfileAsync.fulfilled, (state, action) =>
        {
            state.isGenerating = false
            state.overview.profile = action.payload
        })
        .addCase(generateProfileAsync.rejected, (state, action) =>
        {
            state.isGenerating = false
            state.message = action.payload as string
        });
    }

})


export const selectOverview = (state: RootState) => state.analytics.overview;
export const selectScore = (state: RootState) => state.analytics.overview.score;
export const selectCore = (state: RootState) => state.analytics.overview.core;
export const selectDaily = (state: RootState) => state.analytics.overview.daily;
export const selectBreakdowns = (state: RootState) => state.analytics.overview.breakdowns;
export const selectStrengths = (state: RootState) => state.analytics.overview.strengths;
export const selectLeaks = (state: RootState) => state.analytics.overview.leaks;
export const selectWrittenProfile = (state: RootState) => state.analytics.overview.profile;
export const selectAnalyticsIsLoading = (state: RootState) => state.analytics.isLoading;
export const selectIsGenerating = (state: RootState) => state.analytics.isGenerating;
export const selectAnalyticsMessage = (state: RootState) => state.analytics.message;
export const selectIsMetricsOpen = (state: RootState) => state.analytics.isMetricsOpen;
export const selectAvailableAccounts = (state: RootState) => state.analytics.overview.available_accounts || [];
export const selectSelectedAccounts = (state: RootState) => state.analytics.selectedAccounts;

export const {
    resetAnalyticsMessage, toggleMetrics,
    toggleAccount, selectAllAccounts, selectOnlyAccount,
} = analyticsSlice.actions;

export default analyticsSlice.reducer;

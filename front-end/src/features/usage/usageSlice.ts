import { createAsyncThunk, createSlice } from "@reduxjs/toolkit"

import { RootState } from "../../app/store";
import usageService from "./usageAPI";



export interface UsageState {
    usedPercent: number;
    remainingPercent: number;

    // Two separate thresholds, and the difference matters: `shouldWarn` is "worth mentioning",
    // `exhausted` is "the next question will be refused".
    shouldWarn: boolean;
    exhausted: boolean;

    renewsAt: string | null;
    windowHours: number;

    isLoaded: boolean;
}


const initialState: UsageState = {
    usedPercent: 0,
    remainingPercent: 100,
    shouldWarn: false,
    exhausted: false,
    renewsAt: null,
    windowHours: 24,
    isLoaded: false,
};


/** The shape the server sends, on the endpoint and on every `done` event alike. */
export interface UsagePayload {
    used_percent: number;
    remaining_percent: number;
    should_warn: boolean;
    exhausted: boolean;
    renews_at: string | null;
    window_hours: number;
}


export const getUsageAsync = createAsyncThunk("usage/get", async () => {
    return await usageService.getUsage();
});



export const usageSlice = createSlice({
    name: "usage",
    initialState,
    reducers: {
        /**
         * The state that came back with an answer.
         *
         * **This is why nothing polls.** Every stream ends with a `done` event carrying the
         * fresh figure, and a refusal carries it too - so the only moment the client has to
         * ask is before it has heard anything at all. A meter that polled would itself be a
         * reason to look at the meter.
         */
        usageReported: (state, action: { payload: UsagePayload | undefined }) => {
            const body = action.payload;
            if (!body) return;

            state.usedPercent = body.used_percent;
            state.remainingPercent = body.remaining_percent;
            state.shouldWarn = body.should_warn;
            state.exhausted = body.exhausted;
            state.renewsAt = body.renews_at;
            state.windowHours = body.window_hours;
            state.isLoaded = true;
        },
    },

    extraReducers: (builder) => {
        builder.addCase(getUsageAsync.fulfilled, (state, action) => {
            const body = action.payload as UsagePayload;

            state.usedPercent = body.used_percent;
            state.remainingPercent = body.remaining_percent;
            state.shouldWarn = body.should_warn;
            state.exhausted = body.exhausted;
            state.renewsAt = body.renews_at;
            state.windowHours = body.window_hours;
            state.isLoaded = true;
        });
    },
})


export const selectUsedPercent = (state: RootState) => state.usage.usedPercent;
export const selectRemainingPercent = (state: RootState) => state.usage.remainingPercent;
export const selectShouldWarn = (state: RootState) => state.usage.shouldWarn;
export const selectIsExhausted = (state: RootState) => state.usage.exhausted;
export const selectRenewsAt = (state: RootState) => state.usage.renewsAt;

export const { usageReported } = usageSlice.actions;

export default usageSlice.reducer;

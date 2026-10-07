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
    fullyRenewsAt: string | null;
    windowHours: number;

    // The three the screen says a sentence out of. A percentage is a fraction of a number
    // he has never seen; **an answer count and one moment are the only units he can act on.**
    answersLeft: number;
    nextAnswerAt: string | null;
    scope: 'day' | 'week';

    isLoaded: boolean;
}


const initialState: UsageState = {
    usedPercent: 0,
    remainingPercent: 100,
    shouldWarn: false,
    exhausted: false,
    renewsAt: null,
    fullyRenewsAt: null,
    windowHours: 24,
    answersLeft: 0,
    nextAnswerAt: null,
    scope: 'day',
    isLoaded: false,
};


/** The shape the server sends, on the endpoint and on every `done` event alike. */
export interface UsagePayload {
    used_percent: number;
    remaining_percent: number;
    should_warn: boolean;
    exhausted: boolean;
    renews_at: string | null;
    fully_renews_at?: string | null;
    window_hours: number;
    answers_left?: number;
    next_answer_at?: string | null;
    scope?: 'day' | 'week';
}


/**
 * **One place that absorbs the payload, because there are two callers and they drifted.**
 * The endpoint and the `done` event carry the same body, and each had its own copy of this
 * assignment - so a field added to one reached the screen only on some of the paths that
 * set it, which is the kind of gap nothing reports.
 */
const absorb = (state: UsageState, body: UsagePayload) => {
    state.usedPercent = body.used_percent;
    state.remainingPercent = body.remaining_percent;
    state.shouldWarn = body.should_warn;
    state.exhausted = body.exhausted;
    state.renewsAt = body.renews_at;
    state.fullyRenewsAt = body.fully_renews_at ?? null;
    state.windowHours = body.window_hours;
    state.answersLeft = body.answers_left ?? 0;
    state.nextAnswerAt = body.next_answer_at ?? null;
    state.scope = body.scope ?? 'day';
    state.isLoaded = true;
};


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

            absorb(state, body);
        },
    },

    extraReducers: (builder) => {
        builder.addCase(getUsageAsync.fulfilled, (state, action) => {
            absorb(state, action.payload as UsagePayload);
        });
    },
})


export const selectUsedPercent = (state: RootState) => state.usage.usedPercent;
export const selectRemainingPercent = (state: RootState) => state.usage.remainingPercent;
export const selectShouldWarn = (state: RootState) => state.usage.shouldWarn;
export const selectIsExhausted = (state: RootState) => state.usage.exhausted;
export const selectRenewsAt = (state: RootState) => state.usage.renewsAt;

export const selectFullyRenewsAt = (state: RootState) => state.usage.fullyRenewsAt;
export const selectAnswersLeft = (state: RootState) => state.usage.answersLeft;
export const selectNextAnswerAt = (state: RootState) => state.usage.nextAnswerAt;
export const selectScope = (state: RootState) => state.usage.scope;

export const { usageReported } = usageSlice.actions;

export default usageSlice.reducer;

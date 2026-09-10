import { configureStore, ThunkAction, Action } from '@reduxjs/toolkit';
import authenticationReducer from '../features/authentication/authenticationSlice';
import tradesReducer from '../features/trades/tradesSlice';
import analyticsReducer from '../features/analytics/analyticsSlice';
import chatReducer from '../features/chat/chatSlice';
import mentorReducer from '../features/mentor/mentorSlice';
import usageReducer from '../features/usage/usageSlice';

export const store = configureStore({
  reducer: {
    authentication: authenticationReducer,
    trades: tradesReducer,
    analytics: analyticsReducer,
    chat: chatReducer,
    mentor: mentorReducer,
    usage: usageReducer,
  },
});

export type AppDispatch = typeof store.dispatch;
export type RootState = ReturnType<typeof store.getState>;
export type AppThunk<ReturnType = void> = ThunkAction<
  ReturnType,
  RootState,
  unknown,
  Action<string>
>;

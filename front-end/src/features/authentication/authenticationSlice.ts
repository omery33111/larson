import {  createSlice, createAsyncThunk } from "@reduxjs/toolkit"
import { RootState } from "../../app/store";
import { Login, MyToken, Register } from "../../models/Authentication";
import authenticationService, { getIndex } from "./authenticationAPI";
import { clearSession, readItem, readTokens, writeItem } from "../../app/session";
import { jwtDecode } from 'jwt-decode';


export interface AuthenticationState
{
    userName: string | null,
    isSuccess: boolean,
    isError: boolean,
    isLoading: boolean,
    isLogged: boolean,
    access: string | null,
    refresh: string | null,
    is_staff: Boolean,
    message: string,

    // The one login failure that is not a wrong password: the address was never confirmed.
    // Kept so the login screen can offer to send the mail again instead of leaving the
    // trader typing the same correct password a third time.
    needsVerification: boolean,
    unverifiedEmail: string,

    // How this account gets in. An account opened with Google has no password at all, and the
    // screens that ask for the current one have to know that before they draw a field nobody
    // can fill. Filled by getIndex, which every logged-in screen already calls.
    hasPassword: boolean,
    googleEmail: string,
}


// The store is the single source of truth for the session. Storage is read once, here, so
// that a hard refresh restores the session without any component reading it on its own.
//
// **Which storage is not decided here.** `app/session.ts` owns that: it is `localStorage` when
// the trader ticked "stay signed in" and `sessionStorage` when he did not, and reading through
// it is what makes the tick box mean something on every screen rather than only on the first.
const storedToken = readTokens()

const initialState: AuthenticationState =
{
    userName: readItem("userName") || "",
    isSuccess: false,
    isError: false,
    isLoading: false,
    isLogged: storedToken ? true : false,
    access: storedToken ? storedToken.access : "",
    refresh: storedToken ? storedToken.refresh : "",
    is_staff: readItem("is_staff") === "true",
    message: "",
    needsVerification: false,
    unverifiedEmail: "",
    hasPassword: true,
    googleEmail: "",
};



export const getIndexAsync = createAsyncThunk(
    "authentication/getIndex",
    async () => {
      const response = await getIndex();
      return response;
    }
  );



export const registerAsync = createAsyncThunk("authentication/register", async (user: Register, thunkAPI) => {
    try {
        const response = await authenticationService.register(user);
        return response.data;
    } catch (error: any) {
        return thunkAPI.rejectWithValue(error.response.data);
    }
});



export const loginAsync = createAsyncThunk("authentication/login", async (user: Login, thunkAPI) =>
{
    try {
        return await authenticationService.login(user)
    } catch (error: any) {
        // The body is carried through rather than swallowed: a 403 here means the password
        // was right and the address was never confirmed, and that is a different screen.
        return thunkAPI.rejectWithValue(error.response?.data || {})
    }
})


/**
 * The Google button, which both registers and signs in.
 *
 * It carries the same `remember` choice as the password form: the tick box is about this
 * browser, not about which way the trader got in.
 */
export const googleLoginAsync = createAsyncThunk("authentication/googleLogin",
    async ({ credential, remember }: { credential: string; remember: boolean }, thunkAPI) => {
        try {
            return await authenticationService.googleLogin(credential, remember)
        } catch (error: any) {
            return thunkAPI.rejectWithValue(
                error.response?.data?.error || "לא הצלחנו להתחבר עם גוגל. נסה שוב.")
        }
    })


export const endSessionsAsync = createAsyncThunk("authentication/endSessions",
    async (_, thunkAPI) => {
        try {
            return await authenticationService.endSessions()
        } catch (error: any) {
            return thunkAPI.rejectWithValue(
                error.response?.data?.error || "לא הצלחנו לנתק את שאר החיבורים.")
        }
    })


export const verifyEmailAsync = createAsyncThunk("authentication/verifyEmail",
    async ({ uid, token }: { uid: string; token: string }, thunkAPI) => {
        try {
            return await authenticationService.verifyEmail(uid, token)
        } catch (error: any) {
            return thunkAPI.rejectWithValue(error.response?.data?.error || "הקישור אינו תקף.")
        }
    })


export const resendVerificationAsync = createAsyncThunk("authentication/resendVerification",
    async (email: string, thunkAPI) => {
        try {
            return await authenticationService.resendVerification(email)
        } catch (error: any) {
            return thunkAPI.rejectWithValue(error.response?.data?.error || "לא הצלחנו לשלוח את המייל.")
        }
    })


export const forgotPasswordAsync = createAsyncThunk("authentication/forgotPassword",
    async (email: string, thunkAPI) => {
        try {
            return await authenticationService.forgotPassword(email)
        } catch (error: any) {
            return thunkAPI.rejectWithValue(error.response?.data?.error || "לא הצלחנו לשלוח את המייל.")
        }
    })


export const resetPasswordAsync = createAsyncThunk("authentication/resetPassword",
    async ({ uid, token, password }: { uid: string; token: string; password: string }, thunkAPI) => {
        try {
            return await authenticationService.resetPassword(uid, token, password)
        } catch (error: any) {
            return thunkAPI.rejectWithValue(error.response?.data?.error || "הקישור אינו תקף.")
        }
    })


export const changePasswordAsync = createAsyncThunk("authentication/changePassword",
    async ({ currentPassword, password }: { currentPassword: string; password: string }, thunkAPI) => {
        try {
            return await authenticationService.changePassword(currentPassword, password)
        } catch (error: any) {
            return thunkAPI.rejectWithValue(error.response?.data?.error || "לא הצלחנו להחליף את הסיסמה.")
        }
    })


export const exportDataAsync = createAsyncThunk("authentication/exportData",
    async (_, thunkAPI) => {
        try {
            return await authenticationService.exportData()
        } catch (error: any) {
            return thunkAPI.rejectWithValue("לא הצלחנו להוריד את הנתונים. נסה שוב.")
        }
    })


/**
 * Exactly one of the two proves it, and which one depends on how the account is opened.
 * An account created with Google has no password to give, and the typed confirmation alone
 * would leave a stolen access token able to finish this on its own.
 */
export const deleteAccountAsync = createAsyncThunk("authentication/deleteAccount",
    async ({ password = "", googleCredential = "" }:
           { password?: string; googleCredential?: string }, thunkAPI) => {
        try {
            return await authenticationService.deleteAccount(password, googleCredential)
        } catch (error: any) {
            return thunkAPI.rejectWithValue(error.response?.data?.error || "לא הצלחנו למחוק את החשבון.")
        }
    })


export const logoutAsync = createAsyncThunk('auth/logout',
 async () =>
 {
    // Awaited on purpose. Firing and forgetting leaves the request rejecting into nothing,
    // which is what produced the "Uncaught (in promise) AxiosError" in the console.
    await authenticationService.logout()
 })



export const authenticationSlice = createSlice({
    name: "authentication",
    initialState,
    reducers: {
        reset: (state) =>
        {
        state.isSuccess = false;
        state.isLoading = false;
        state.isError = false;
        },

        LoggedOff: (state) =>
        {
            state.isLogged = false
        },

        LoggedOn: (state) => {
            state.isLogged = true
            state.userName = readItem('userName') as string
        },

        staffCheck: (state) =>
        {
            if (readItem("is_staff") === "true") {
              state.is_staff = true
            }
        },

        // Fired by the axios interceptor whenever the server answers 401. The token is dead,
        // so the session is torn down locally without another round trip - asking a server
        // that just rejected us to also process a logout is what produced the second 401.
        clearVerificationPrompt: (state) =>
        {
            state.needsVerification = false
            state.unverifiedEmail = ""
        },

        sessionExpired: (state) =>
        {
            state.isLogged = false
            state.userName = ""
            state.access = ""
            state.refresh = ""
            state.is_staff = false
            state.isSuccess = false
            state.isError = false
            state.isLoading = false

            clearSession();
        },

    },
    extraReducers: (builder) => {
        builder
        .addCase(registerAsync.rejected, (state, action) =>
        {
            state.isLoading = false
            state.isError = true
            state.message = action.payload as string
        })
        .addCase(registerAsync.pending, (state) =>
        {
            state.isLoading = true
        })
        .addCase(registerAsync.fulfilled, (state) =>
        {
            state.isLoading = false
            state.isSuccess = true
        })


        .addCase(loginAsync.pending, (state) =>
        {
            state.isLoading = true
        })
        .addCase(loginAsync.fulfilled, (state, action) => {
            const decoded: MyToken = jwtDecode(action.payload.access)

            state.userName = decoded.username
            state.is_staff = decoded.is_staff
            writeItem('userName', decoded.username)
            writeItem('is_staff', JSON.stringify(decoded.is_staff))
            state.access = action.payload.access
            state.isLoading = false;
            state.isSuccess = true;
            state.isLogged = true;
            state.isError = false;
        })

        // The same landing for both doors: whichever way the pair was obtained, the session
        // that follows it is identical.
        .addCase(googleLoginAsync.pending, (state) => {
            state.isLoading = true
        })
        .addCase(googleLoginAsync.fulfilled, (state, action) => {
            const decoded: MyToken = jwtDecode(action.payload.access)

            state.userName = decoded.username
            state.is_staff = decoded.is_staff
            writeItem('userName', decoded.username)
            writeItem('is_staff', JSON.stringify(decoded.is_staff))
            state.access = action.payload.access
            state.refresh = action.payload.refresh
            state.isLoading = false;
            state.isSuccess = true;
            state.isLogged = true;
            state.isError = false;
            state.needsVerification = false;
        })
        .addCase(googleLoginAsync.rejected, (state, action) => {
            state.isLoading = false;
            state.isError = true;
            state.message = action.payload as string;
        })

        .addCase(endSessionsAsync.fulfilled, (state, action) => {
            // A fresh pair comes back, because this call blacklists the caller's own token
            // too - otherwise closing the other doors would close this one.
            const pair = action.payload as { access?: string; refresh?: string };
            if (pair?.access) state.access = pair.access;
            if (pair?.refresh) state.refresh = pair.refresh;
        })

        .addCase(loginAsync.rejected, (state, action) => {
            const body = (action.payload || {}) as { needs_verification?: boolean; email?: string };

            state.isLoading = false;
            state.isError = true;
            state.needsVerification = Boolean(body.needs_verification);
            state.unverifiedEmail = body.email || "";
        })


        .addCase(logoutAsync.pending, (state) => {
            state.isLoading = true;
        })
        .addCase(logoutAsync.fulfilled, (state) => {
            state.isLoading = false;
            state.isLogged = false;
            state.userName = "";
            state.access = "";
            state.isError = false;
            state.isSuccess = false;

            clearSession();
        })
        .addCase(logoutAsync.rejected, (state, action) => {
            state.isLoading = false;
            state.isError = true;
            state.message = action.payload as string;
        })


        .addCase(changePasswordAsync.fulfilled, (state, action) => {
            // The server rotated the pair, so the store follows storage rather than holding
            // the access token that was just blacklisted.
            const pair = action.payload as { access?: string; refresh?: string };
            if (pair?.access) state.access = pair.access;
            if (pair?.refresh) state.refresh = pair.refresh;
        })

        .addCase(deleteAccountAsync.fulfilled, (state) => {
            // Nothing is left to be logged into. The API already cleared storage; this
            // is the store catching up, and it is what routes the screen back to the front.
            state.isLoading = false;
            state.isLogged = false;
            state.userName = "";
            state.access = "";
            state.refresh = "";
            state.is_staff = false;
        })
        .addCase(deleteAccountAsync.pending, (state) => {
            state.isLoading = true;
        })
        .addCase(deleteAccountAsync.rejected, (state, action) => {
            state.isLoading = false;
            state.message = action.payload as string;
        })

        .addCase(getIndexAsync.fulfilled, (state, action) => {
            state.userName = action.payload.data.username
            state.isLogged = true
            state.hasPassword = action.payload.data.has_password !== false
            state.googleEmail = action.payload.data.google_email || ""
        })
        .addCase(getIndexAsync.rejected, (state) => {
            state.isLogged = false
        });
    }

})


export const selectAccess = (state: RootState) => state.authentication.access;
export const selectUser = (state: RootState) => state.authentication.userName;
export const selectIsLogged = (state: RootState) => state.authentication.isLogged;
export const selectIsLoading = (state: RootState) => state.authentication.isLoading;
export const selectIsError = (state: RootState) => state.authentication.isError;
export const selectIsSuccess = (state: RootState) => state.authentication.isSuccess;
export const selectIsStaff = (state: RootState) => state.authentication.is_staff;

export const selectNeedsVerification = (state: RootState) => state.authentication.needsVerification;
export const selectUnverifiedEmail = (state: RootState) => state.authentication.unverifiedEmail;
export const selectAuthMessage = (state: RootState) => state.authentication.message;

export const selectHasPassword = (state: RootState) => state.authentication.hasPassword;
export const selectGoogleEmail = (state: RootState) => state.authentication.googleEmail;

export const {
    reset, LoggedOff, LoggedOn, staffCheck, sessionExpired, clearVerificationPrompt
} = authenticationSlice.actions;

export default authenticationSlice.reducer;

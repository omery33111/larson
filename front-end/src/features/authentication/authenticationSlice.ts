import {  createSlice, createAsyncThunk } from "@reduxjs/toolkit"
import { RootState } from "../../app/store";
import { Login, MyToken, Register } from "../../models/Authentication";
import authenticationService, { getIndex } from "./authenticationAPI";
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
}


// The store is the single source of truth for the session. localStorage is read once, here,
// so that a hard refresh restores the session without any component reading it on its own.
const storedToken = JSON.parse(localStorage.getItem("token") as string)

const initialState: AuthenticationState =
{
    userName: localStorage.getItem("userName") || "",
    isSuccess: false,
    isError: false,
    isLoading: false,
    isLogged: storedToken ? true : false,
    access: storedToken ? storedToken.access : "",
    refresh: storedToken ? storedToken.refresh : "",
    is_staff: localStorage.getItem("is_staff") === "true",
    message: "",
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



export const loginAsync = createAsyncThunk("authentication/login", async (user: Login) =>
{
        return await authenticationService.login(user)
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
            state.userName = localStorage.getItem('userName') as string
        },

        staffCheck: (state) =>
        {
            if (localStorage.getItem("is_staff") === "true") {
              state.is_staff = true
            }
        },

        // Fired by the axios interceptor whenever the server answers 401. The token is dead,
        // so the session is torn down locally without another round trip - asking a server
        // that just rejected us to also process a logout is what produced the second 401.
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

            localStorage.removeItem('is_staff');
            localStorage.removeItem('userName');
            localStorage.removeItem('loginTime');
            localStorage.removeItem('token');
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
            localStorage.setItem('userName', decoded.username)
            localStorage.setItem('is_staff', JSON.stringify(decoded.is_staff))
            state.access = action.payload.access
            state.isLoading = false;
            state.isSuccess = true;
            state.isLogged = true;
            state.isError = false;
        })

        .addCase(loginAsync.rejected, (state) => {
            state.isLoading = false;
            state.isError = true;
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

            localStorage.removeItem('is_staff');
            localStorage.removeItem('userName');
            localStorage.removeItem('loginTime');
            localStorage.removeItem('token');
        })
        .addCase(logoutAsync.rejected, (state, action) => {
            state.isLoading = false;
            state.isError = true;
            state.message = action.payload as string;
        })


        .addCase(getIndexAsync.fulfilled, (state, action) => {
            state.userName = action.payload.data.username
            state.isLogged = true
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

export const { reset, LoggedOff, LoggedOn, staffCheck, sessionExpired } = authenticationSlice.actions;

export default authenticationSlice.reducer;

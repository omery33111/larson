import axios from "axios";
import {
  accountURL, authenticationURL, changePasswordURL, endSessionsURL, exportDataURL,
  forgotPasswordURL, googleLoginURL, loginURL, logoutURL,
  registerURL, resendVerificationURL, resetPasswordURL, verifyEmailURL, emailPreferencesURL
} from "../../endpoints/endpoints";
import {
  accessToken, clearSession, rememberSession, readTokens, writeItem, writeTokens
} from "../../app/session";
import { forgetGoogleSession } from "./GoogleSignIn";
import { Login, Register } from "../../models/Authentication";



export function getIndex() {
    let config = {
        headers: { 'Authorization': `Bearer ${accessToken()}` }
      }
    return new Promise<{ data: any }>((resolve =>
      axios.get(`${authenticationURL}/`, config)
        .then(res => resolve({ data: res.data }))));
  }



/**
 * **It throws, and says nothing.**
 *
 * It used to raise three different toasts itself and then return `{ error }` instead of
 * failing - so the thunk's `catch` never ran, `registerAsync` resolved as a success, and the
 * screen had no idea anything had gone wrong. The message reached the trader only because
 * this layer put it in a corner on its own initiative.
 *
 * **An API module has no business knowing where an error is displayed.** It reports failure
 * the way every other one here does, the thunk turns it into a string, and the form renders
 * it under the fields it is about.
 */
const register = async (userData: Register) => {
  const response = await axios.post(registerURL, userData);
  return response.data;
};


const login = async (userData: Login) => {
    const { remember, ...credentials } = userData;

    const response = await axios.post(loginURL, credentials);

    if (response.data) {
        // **Before the write, not after.** This is what decides which storage the pair lands
        // in, and writing first would put it in the previous session's store.
        rememberSession(Boolean(remember));
        writeTokens(response.data);
        writeItem('loginTime', new Date().toISOString());
    }

    return response.data;
};


/**
 * Signing in with Google.
 *
 * The browser has already got an ID token from Google; all that travels here is that token,
 * and the server checks its signature against Google's own keys before it means anything.
 * **No password is involved anywhere in this path**, in either direction.
 */
const googleLogin = async (credential: string, remember: boolean) => {
    const response = await axios.post(googleLoginURL, { credential });

    if (response.data) {
        rememberSession(Boolean(remember));
        writeTokens(response.data);
        writeItem('loginTime', new Date().toISOString());
    }

    return response.data;
};


/**
 * Sign out of every other session, keeping this one.
 *
 * The server blacklists every refresh token the account has out - this caller's included -
 * and hands back a fresh pair, which is stored here. Without that, the safe action would log
 * you out of the device you took it from.
 */
const endSessions = async () => {
    const response = await axios.post(endSessionsURL, {},
      { headers: { Authorization: `Bearer ${accessToken()}` } });

    if (response.data?.access) writeTokens(response.data);

    return response.data;
};


const logout = async () => {
  // Told to Google as well, or its library keeps treating this as the chosen account and One
  // Tap offers to put him straight back into the session he just left.
  forgetGoogleSession();

  const pair = readTokens();
  let config = {
      headers: { 'Authorization': `Bearer ${pair?.access || ""}` }
  }

    try {
      const response = await axios.post(logoutURL, { refresh_token: pair?.refresh || "" }, config);

      return response.data;
    } catch (error) {
      // Blacklisting the refresh token is a courtesy to the server. If it fails - because
      // the access token already expired, or the user was deleted - the local session must
      // still be torn down, otherwise the user is stuck logged in with a dead token.
      console.warn("Logout request failed, clearing the local session anyway.");
      return null;
    }
  };



// ------------------------- THE ADDRESS -------------------------

const verifyEmail = async (uid: string, token: string) => {
  const response = await axios.post(verifyEmailURL, { uid, token });
  return response.data;
};


const resendVerification = async (email: string) => {
  const response = await axios.post(resendVerificationURL, { email });
  return response.data;
};



/**
 * Changing it from inside the account.
 *
 * The server ends every other session and hands back a new pair for this one, which is
 * stored here - **without that, changing your own password would log you out**, and a
 * product that punishes people for rotating a password teaches them not to.
 */
const changePassword = async (currentPassword: string, password: string) => {
  const response = await axios.post(changePasswordURL,
    { current_password: currentPassword, password },
    { headers: { Authorization: `Bearer ${accessToken()}` } });

  if (response.data?.access) writeTokens(response.data);

  return response.data;
};


// ------------------------- A FORGOTTEN PASSWORD -------------------------

const forgotPassword = async (email: string) => {
  const response = await axios.post(forgotPasswordURL, { email });
  return response.data;
};


const resetPassword = async (uid: string, token: string, password: string) => {
  const response = await axios.post(resetPasswordURL, { uid, token, password });
  return response.data;
};



// ------------------------- THE ACCOUNT ITSELF -------------------------

/**
 * Fetched as JSON and handed to the browser as a file, rather than opened as a link.
 *
 * A plain `<a href>` to the endpoint cannot carry the Authorization header, and putting the
 * token in the query string would write it into browser history and any server log on the
 * way - for a download whose whole content is the trader's private record.
 */
const exportData = async () => {
  const response = await axios.get(exportDataURL, {
    headers: { Authorization: `Bearer ${accessToken()}` },
  });

  const blob = new Blob([JSON.stringify(response.data, null, 2)],
                        { type: "application/json" });
  const url = URL.createObjectURL(blob);

  const link = document.createElement("a");
  link.href = url;
  link.download = `larson-${response.data?.account?.username || "data"}.json`;
  link.click();

  URL.revokeObjectURL(url);
  return response.data;
};


/**
 * `googleCredential` rather than a password, for an account that never had one.
 *
 * Exactly one of the two is sent and the server decides which it needs. **Neither is a
 * formality**: this is the only irreversible action in the product that a stolen access token
 * could otherwise finish on its own, and unlike deleting the resume there is no account left
 * afterwards to notice that it happened.
 */
const deleteAccount = async (password: string, googleCredential = "") => {
  const response = await axios.delete(accountURL, {
    headers: { Authorization: `Bearer ${accessToken()}` },
    data: { password, google_credential: googleCredential },
  });

  // There is no account left to be logged into, so the local session goes with it rather
  // than waiting for the next request to be rejected.
  clearSession();

  return response.data;
};


// ------------------------- WHAT MAY BE SENT TO HIM -------------------------
//
// Two flags and not one: the weekly summary is a service message about his own record and is
// opt-out, while anything promotional is the other thing under Israeli law and starts off.

const emailPreferences = async () => {
    const response = await axios.get(emailPreferencesURL, {
        headers: { 'Authorization': `Bearer ${accessToken()}` }
    });

    return response.data;
};


const saveEmailPreferences = async (changes: Record<string, boolean>) => {
    const response = await axios.post(emailPreferencesURL, changes, {
        headers: { 'Authorization': `Bearer ${accessToken()}` }
    });

    return response.data;
};



const authenticationService = {
    emailPreferences,
    saveEmailPreferences,
    register,
    login,
    googleLogin,
    endSessions,
    logout,
    verifyEmail,
    resendVerification,
    changePassword,
    forgotPassword,
    resetPassword,
    exportData,
    deleteAccount,
};

export default authenticationService;

import axios from "axios";
import {
  accountURL, authenticationURL, changePasswordURL, exportDataURL, forgotPasswordURL,
  loginURL, logoutURL,
  registerURL, resendVerificationURL, resetPasswordURL, verifyEmailURL
} from "../../endpoints/endpoints";
import { accessToken, clearTokens, writeTokens } from "../../app/session";
import { Login, Register } from "../../models/Authentication";
import { toast } from 'react-toastify';



export function getIndex() {
    const myToken = JSON.parse(localStorage.getItem("token") as string)
    const accessToken = myToken ? myToken.access : "";
    let config = {
        headers: { 'Authorization': `Bearer ${accessToken}` }
      }
    return new Promise<{ data: any }>((resolve =>
      axios.get(`${authenticationURL}/`, config)
        .then(res => resolve({ data: res.data }))));
  }



const register = async (userData: Register) => {
  try {
      const response = await axios.post(registerURL, userData);
      return response.data;
  } catch (error: any) {
      if (error.response) {
          if (error.response.status === 400) {
              toast.error(error.response.data.error, {
                  position: toast.POSITION.TOP_RIGHT,
              });
              return { error: error.response.data.error };
          } else {
              toast.error("שגיאה בהרשמה.", {
                  position: toast.POSITION.TOP_RIGHT,
              });
              return { error: "שגיאה בהרשמה." };
          }
      } else {
          toast.error("שגיאת רשת או במהלך הבקשה.", {
              position: toast.POSITION.TOP_RIGHT,
          });
          return { error: "שגיאת רשת או במהלך הבקשה." };
      }
  }
};


const login = async (userData: Login) => {
    const response = await axios.post(loginURL, userData);

    if (response.data) {
        writeTokens(response.data);
    }

    return response.data;
};


const logout = async () => {
  const myToken = JSON.parse(localStorage.getItem("token") as string)
  const accessToken = myToken ? myToken.access : "";
  let config = {
      headers: { 'Authorization': `Bearer ${accessToken}` }
  }

    try {
      const refreshToken = myToken ? myToken.refresh : "";

      const response = await axios.post(logoutURL, { refresh_token: refreshToken }, config);

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


const deleteAccount = async (password: string) => {
  const response = await axios.delete(accountURL, {
    headers: { Authorization: `Bearer ${accessToken()}` },
    data: { password },
  });

  // There is no account left to be logged into, so the local session goes with it rather
  // than waiting for the next request to be rejected.
  clearTokens();
  localStorage.removeItem("userName");
  localStorage.removeItem("is_staff");
  localStorage.removeItem("loginTime");

  return response.data;
};


const authenticationService = {
    register,
    login,
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

import axios from "axios";
import { authenticationURL, loginURL, logoutURL, registerURL } from "../../endpoints/endpoints";
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
        localStorage.setItem("token", JSON.stringify(response.data));
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


const authenticationService = {
    register,
    login,
    logout,
};

export default authenticationService;

import axios from 'axios';

import { sessionExpired } from '../features/authentication/authenticationSlice';
import { store } from './store';



// ------------------------- AUTH INTERCEPTOR -------------------------
//
// A single place that decides what an expired or invalid token means.
//
// Without this, every feature had to interpret 401 on its own, so a dead token surfaced as
// whatever generic message that feature happened to have ("שגיאה בטעינת הנתונים") while the
// user stayed nominally logged in with a token the server refuses.

export function registerAuthInterceptor() {
  axios.interceptors.response.use(
    (response) => response,
    (error) => {
      const status = error.response?.status;
      const url: string = error.config?.url || '';

      // A failed login is a wrong password, not an expired session - it must keep its own
      // error message and stay on the form.
      const isLoginAttempt = url.includes('/authentication/login');

      if (status === 401 && !isLoginAttempt) {
        // Only act when we believed we were logged in, so an anonymous probe stays quiet.
        if (store.getState().authentication.isLogged) {
          store.dispatch(sessionExpired());
        }
      }

      return Promise.reject(error);
    },
  );
}

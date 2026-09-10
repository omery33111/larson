import axios from 'axios';

import { sessionExpired } from '../features/authentication/authenticationSlice';
import { refreshSession } from './session';
import { store } from './store';



// ------------------------- AUTH INTERCEPTOR -------------------------
//
// A single place that decides what an expired or invalid token means.
//
// Without this, every feature had to interpret 401 on its own, so a dead token surfaced as
// whatever generic message that feature happened to have ("שגיאה בטעינת הנתונים") while the
// user stayed nominally logged in with a token the server refuses.
//
// **It now tries to renew before it gives up.** A 401 has two quite different causes - a
// token that has simply aged out, and a session that is genuinely over - and treating the
// first as the second is what turned a one-day access token into a one-day session.

// Endpoints where a 401 is the answer rather than a symptom, and must not trigger a renewal:
// a failed login is a wrong password, and a failed refresh is the very thing that would
// recurse.
const NEVER_RETRIED = ['/authentication/login', '/authentication/refresh'];


export function registerAuthInterceptor() {
  axios.interceptors.response.use(
    (response) => response,
    async (error) => {
      const status = error.response?.status;
      const request = error.config;
      const url: string = request?.url || '';

      if (status !== 401 || !request || NEVER_RETRIED.some((path) => url.includes(path))) {
        return Promise.reject(error);
      }

      // Only ever one retry. Without this flag a token the server keeps rejecting - a user
      // that was deleted, say - would loop between the retry and the interceptor forever.
      if (request._retried) {
        if (store.getState().authentication.isLogged) store.dispatch(sessionExpired());
        return Promise.reject(error);
      }

      request._retried = true;

      const token = await refreshSession();

      if (!token) {
        // The refresh token is gone, expired or blacklisted: the session really is over, and
        // the components already route to the login screen when `isLogged` goes false.
        if (store.getState().authentication.isLogged) store.dispatch(sessionExpired());
        return Promise.reject(error);
      }

      request.headers = { ...request.headers, Authorization: `Bearer ${token}` };
      return axios(request);
    },
  );
}

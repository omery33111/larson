import React from 'react';
import { createRoot } from 'react-dom/client';
import { ThemeProvider } from '@mui/material/styles';
import { Provider } from 'react-redux';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import App from './App';
import { store } from './app/store';
import { registerAuthInterceptor } from './app/interceptors';
import { muiTheme } from './app/muiTheme';
import AccountPage from './features/authentication/AccountPage';
import ForgotPassword from './features/authentication/ForgotPassword';
import Login from './features/authentication/Login';
import Register from './features/authentication/Register';
import ResetPassword from './features/authentication/ResetPassword';
import VerifyEmail from './features/authentication/VerifyEmail';
import Privacy from './features/base/Privacy';
import Terms from './features/base/Terms';
import ErrorPage from './features/base/ErrorPage';
import HomePage from './features/base/HomePage';
import TraderProfilePage from './features/analytics/TraderProfilePage';
import ChatPage from './features/chat/ChatPage';
import MentorPage from './features/mentor/MentorPage';
import './index.css';



registerAuthInterceptor();

const container = document.getElementById('root')!;
const root = createRoot(container);

root.render(
  <React.StrictMode>
    <Provider store={store}>

<ThemeProvider theme={muiTheme}>

<BrowserRouter>

  <Routes>

      <Route path = "/" element={<App />}>

      <Route path = "/" element={<HomePage />} />

      <Route path = "/authentication/login" element={<Login />} />
      <Route path = "/authentication/register" element={<Register />} />

      {/* The uid and the token travel in the path rather than the query string, so they are
          not written into a referrer header on the way to any third-party asset. */}
      <Route path = "/authentication/verify/:uid/:token" element={<VerifyEmail />} />
      <Route path = "/authentication/forgot" element={<ForgotPassword />} />
      <Route path = "/authentication/reset/:uid/:token" element={<ResetPassword />} />

      <Route path = "/account" element={<AccountPage />} />

      <Route path = "/terms" element={<Terms />} />
      <Route path = "/privacy" element={<Privacy />} />

      <Route path = "/profile" element={<TraderProfilePage />} />

      <Route path = "/mentor" element={<MentorPage />} />

      <Route path = "/chat" element={<ChatPage />} />

      </Route>

      <Route path="/*" element={<ErrorPage />} />

      </Routes>

</BrowserRouter>

</ThemeProvider>

</Provider>
  </React.StrictMode>
);

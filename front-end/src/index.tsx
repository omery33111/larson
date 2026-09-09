import React from 'react';
import { createRoot } from 'react-dom/client';
import { ThemeProvider } from '@mui/material/styles';
import { Provider } from 'react-redux';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import App from './App';
import { store } from './app/store';
import { registerAuthInterceptor } from './app/interceptors';
import { muiTheme } from './app/muiTheme';
import Login from './features/authentication/Login';
import Register from './features/authentication/Register';
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

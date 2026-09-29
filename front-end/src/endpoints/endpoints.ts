



// ------------------------- MYSERVER ENDPOINTS:
// Still one constant, and still the only place an address is written - but read from the
// environment rather than edited by hand before a build.
//
// **It was a hardcoded `127.0.0.1` with the production address commented out above it.** A
// build that forgot the swap would go live pointing every request at the developer's own
// machine, and nothing would say so: the site loads, and every screen fails to fetch.
//
// Vite bakes this in at build time, so it has to be set **before** `npm run build`. The
// default is the local server, which is what development wants and what the suite wants.
export const myServer = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";





// ------------------------- AUTHENTICATION ENDPOINTS:
export const authenticationURL = `${myServer}/authentication`;

export const loginURL = `${myServer}/authentication/login/`;

export const googleLoginURL = `${myServer}/authentication/login/google/`;

export const registerURL = `${myServer}/authentication/register/`;

export const logoutURL = `${myServer}/authentication/logout/`;

// The one that was missing: without it the refresh token issued at login was never spent,
// and the real session length was the access token's single day.
export const refreshURL = `${myServer}/authentication/refresh/`;

export const verifyEmailURL = `${myServer}/authentication/verify/`;

export const resendVerificationURL = `${myServer}/authentication/verify/resend/`;

export const changePasswordURL = `${myServer}/authentication/password/change/`;

export const forgotPasswordURL = `${myServer}/authentication/password/forgot/`;

export const resetPasswordURL = `${myServer}/authentication/password/reset/`;

export const endSessionsURL = `${myServer}/authentication/sessions/end/`;

export const exportDataURL = `${myServer}/authentication/export/`;

export const accountURL = `${myServer}/authentication/account/`;





// ------------------------- TRADES ENDPOINTS:
export const tradesURL = `${myServer}/trades`;

export const uploadTradesURL = `${myServer}/trades/upload/`;

export const confirmTradesURL = `${myServer}/trades/confirm/`;

export const tradesSummaryURL = `${myServer}/trades/summary/`;

export const resumeURL = `${myServer}/trades/resume/`;





// ------------------------- ANALYTICS ENDPOINTS:
export const analyticsURL = `${myServer}/analytics`;

export const analyticsOverviewURL = `${myServer}/analytics/`;

export const traderProfileURL = `${myServer}/analytics/profile/`;

export const generateProfileURL = `${myServer}/analytics/profile/generate/`;




// ------------------------- CHAT ENDPOINTS:
export const chatURL = `${myServer}/chat`;

export const conversationsURL = `${myServer}/chat/conversations/`;

export const conversationURL = (id: number) => `${myServer}/chat/conversations/${id}/`;

export const streamMessageURL = (id: number) => `${myServer}/chat/conversations/${id}/stream/`;

export const starredMessagesURL = `${myServer}/chat/starred/`;

export const starMessageURL = (id: number) => `${myServer}/chat/messages/${id}/star/`;





// ------------------------- USAGE ENDPOINTS:
// Read once when a screen opens. After that the fresh state rides the `done` event at the
// end of every answer, so nothing polls this.
export const usageURL = `${myServer}/usage/`;




// ------------------------- MENTOR ENDPOINTS:
export const mentorURL = `${myServer}/mentor/`;

export const mentorStreamURL = `${myServer}/mentor/stream/`;

export const mentorPendingURL = `${myServer}/mentor/pending/`;

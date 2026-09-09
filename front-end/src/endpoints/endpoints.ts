



// ------------------------- MYSERVER ENDPOINTS:
export const myServer = "http://127.0.0.1:8000";

// export const myServer = "https://larson-backend.onrender.com";





// ------------------------- AUTHENTICATION ENDPOINTS:
export const authenticationURL = `${myServer}/authentication`;

export const loginURL = `${myServer}/authentication/login/`;

export const registerURL = `${myServer}/authentication/register/`;

export const logoutURL = `${myServer}/authentication/logout/`;





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




// ------------------------- MENTOR ENDPOINTS:
export const mentorURL = `${myServer}/mentor/`;

export const mentorStreamURL = `${myServer}/mentor/stream/`;

export const mentorPendingURL = `${myServer}/mentor/pending/`;

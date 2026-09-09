import axios from "axios";
import {
    conversationURL, conversationsURL, starMessageURL, starredMessagesURL, streamMessageURL
} from "../../endpoints/endpoints";



function accessToken() {
    const myToken = JSON.parse(localStorage.getItem("token") as string)
    return myToken ? myToken.access : "";
}

function authConfig() {
    return {
        headers: { 'Authorization': `Bearer ${accessToken()}` }
    }
}



// ------------------------- CONVERSATIONS -------------------------

const getConversations = async () => {
    const response = await axios.get(conversationsURL, authConfig());

    return response.data;
};


const createConversation = async () => {
    const response = await axios.post(conversationsURL, {}, authConfig());

    return response.data;
};


const getConversation = async (id: number) => {
    const response = await axios.get(conversationURL(id), authConfig());

    return response.data;
};


const renameConversation = async (id: number, title: string) => {
    const response = await axios.patch(conversationURL(id), { title }, authConfig());

    return response.data;
};


const deleteConversation = async (id: number) => {
    await axios.delete(conversationURL(id), authConfig());

    return id;
};



// ------------------------- SAVED ANSWERS -------------------------

const getStarred = async () => {
    const response = await axios.get(starredMessagesURL, authConfig());

    return response.data;
};


const toggleStar = async (id: number) => {
    const response = await axios.post(starMessageURL(id), {}, authConfig());

    return response.data;
};



// ------------------------- THE ATTACHED FILE -------------------------
//
// A File cannot live in the store - it is not serializable, and RTK is right to complain
// about it. The store keeps the name, which is all the screen renders; the file itself waits
// here until the message it belongs to is sent.

let pendingFile: File | null = null;

export const setPendingFile = (file: File | null) => { pendingFile = file };

export const takePendingFile = () => {
    const file = pendingFile;
    pendingFile = null;
    return file;
};



// ------------------------- STREAMING -------------------------
//
// fetch rather than axios, because axios has no way to read a response while it is still
// arriving. The pattern is the one from mockGPT: read the body as a stream, pull each delta
// out as it lands, and hand it straight on.
//
// EventSource would have been the obvious tool for SSE and cannot be used: it sends no
// headers, so there is nowhere to put the token, and it cannot POST a file.

export type StreamEvent =
    | { type: 'start'; message_id: number; question_id: number; title: string }
    | { type: 'delta'; text: string }
    | { type: 'done'; message_id: number }
    | { type: 'error'; error: string };


const streamMessage = async (
    id: number,
    text: string,
    file: File | null,
    onEvent: (event: StreamEvent) => void,
    signal: AbortSignal,
) => {
    const body = new FormData();
    body.append('message', text);
    if (file) body.append('file', file);

    const response = await fetch(streamMessageURL(id), {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${accessToken()}` },
        body,
        signal,
    });

    if (!response.ok || !response.body) {
        // fetch never passes through the axios interceptor, so the status is handed back for
        // the thunk to interpret rather than being swallowed here.
        throw { status: response.status };
    }

    await readEventStream(response, onEvent);
};


/**
 * The SSE reader, shared by the chat and the mentor.
 *
 * It lives in one place because the buffering is the part that is easy to get subtly wrong: a
 * chunk boundary lands in the middle of an event, and sometimes in the middle of a Hebrew
 * character. This loop was verified against the real bytes the server writes at every chunk
 * size from 1 to 120 bytes, and a second copy of it would be a second chance to break that.
 */
export const readEventStream = async (
    response: Response,
    onEvent: (event: StreamEvent) => void,
) => {
    const reader = response.body!.getReader();
    const decoder = new TextDecoder();

    // Whatever is left over after the last blank line is carried into the next read instead
    // of being parsed as garbage.
    let buffer = '';

    while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';

        for (const part of parts) {
            const line = part.trim();
            if (!line.startsWith('data: ')) continue;

            onEvent(JSON.parse(line.slice(6)) as StreamEvent);
        }
    }
};



const chatService = {
    getConversations,
    createConversation,
    getConversation,
    renameConversation,
    deleteConversation,
    getStarred,
    toggleStar,
    streamMessage,
};

export default chatService;

import axios from "axios";
import { mentorPendingURL, mentorStreamURL, mentorURL } from "../../endpoints/endpoints";
import { StreamEvent, readEventStream } from "../chat/chatAPI";



function accessToken() {
    const myToken = JSON.parse(localStorage.getItem("token") as string)
    return myToken ? myToken.access : "";
}



const getMentor = async () => {
    const response = await axios.get(mentorURL, {
        headers: { 'Authorization': `Bearer ${accessToken()}` }
    });

    return response.data;
};



// ------------------------- THE DEBRIEF -------------------------
//
// Same transport as the chat, different meaning. `trade_file_id` is only ever a file the
// trader has already confirmed into his resume - the server refuses an unconfirmed one - so
// by the time this is called the decision has already been made and recorded.

const streamDebrief = async (
    body: { message?: string; trade_file_id?: number },
    onEvent: (event: StreamEvent) => void,
    signal: AbortSignal,
) => {
    const response = await fetch(mentorStreamURL, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${accessToken()}`,
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
        signal,
    });

    if (!response.ok || !response.body) {
        // fetch never passes through the axios interceptor, so the status is handed back for
        // the thunk to interpret rather than being swallowed here.
        throw { status: response.status };
    }

    await readEventStream(response, onEvent);
};



// Takes the waiting file off the composer. It removes nothing from the resume - those trades
// were saved the moment he confirmed them - so all this drops is a debrief he decided against.
const dismissPending = async () => {
    const response = await axios.delete(mentorPendingURL, {
        headers: { 'Authorization': `Bearer ${accessToken()}` }
    });

    return response.data;
};



const mentorService = {
    getMentor,
    streamDebrief,
    dismissPending,
};

export default mentorService;

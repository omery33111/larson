import axios from "axios";
import { accessToken } from "../../app/session";
import {
    confirmTradesURL, resumeURL, tradesSummaryURL, tradesURL, uploadTradesURL
} from "../../endpoints/endpoints";



function authConfig(extra: any = {}) {
    const token = accessToken();
    return {
        headers: { 'Authorization': `Bearer ${token}`, ...extra }
    }
}



const uploadTrades = async (file: File) => {
    const formData = new FormData();
    formData.append("file", file);

    const response = await axios.post(uploadTradesURL, formData,
        authConfig({ 'Content-Type': 'multipart/form-data' }));

    return response.data;
};


const confirmTrades = async (tradeFileId: number, forMentor = false) => {
    const response = await axios.post(confirmTradesURL,
        { trade_file_id: tradeFileId, for_mentor: forMentor }, authConfig());

    return response.data;
};


const getSummary = async () => {
    const response = await axios.get(tradesSummaryURL, authConfig());

    return response.data;
};


const getTrades = async (limit: number = 50, offset: number = 0) => {
    const response = await axios.get(`${tradesURL}/?limit=${limit}&offset=${offset}`, authConfig());

    return response.data;
};


// ------------------------- DELETING THE RESUME -------------------------
//
// Every component at once: the source files on disk, the trades table and the written
// profile. The aggregates are computed at request time and never stored, so they go with the
// trades without a line of their own.

const deleteResume = async () => {
    const response = await axios.delete(resumeURL, authConfig());

    return response.data;
};



const tradesService = {
    deleteResume,
    uploadTrades,
    confirmTrades,
    getSummary,
    getTrades,
};

export default tradesService;

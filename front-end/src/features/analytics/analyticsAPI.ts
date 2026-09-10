import axios from "axios";
import { accessToken } from "../../app/session";
import { analyticsOverviewURL, generateProfileURL } from "../../endpoints/endpoints";



function authConfig() {
    const token = accessToken();
    return {
        headers: { 'Authorization': `Bearer ${token}` }
    }
}



const getOverview = async (accounts: string[] | null) => {
    // No parameter at all means every account, which is what the server treats as the default.
    const query = accounts && accounts.length ? `?accounts=${encodeURIComponent(accounts.join(','))}` : '';

    const response = await axios.get(`${analyticsOverviewURL}${query}`, authConfig());

    return response.data;
};


const generateProfile = async (accounts: string[] | null) => {
    // The written profile is generated for exactly the accounts ticked at that moment.
    const body = accounts && accounts.length ? { accounts: accounts.join(',') } : {};

    // The model call runs long enough that the default axios timeout is not enough.
    const response = await axios.post(generateProfileURL, body, { ...authConfig(), timeout: 180000 });

    return response.data;
};


const analyticsService = {
    getOverview,
    generateProfile,
};

export default analyticsService;

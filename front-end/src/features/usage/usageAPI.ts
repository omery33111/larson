import axios from "axios";
import { accessToken } from "../../app/session";
import { usageURL } from "../../endpoints/endpoints";



const getUsage = async () => {
    const response = await axios.get(usageURL, {
        headers: { 'Authorization': `Bearer ${accessToken()}` }
    });

    return response.data;
};


const usageService = {
    getUsage,
};

export default usageService;

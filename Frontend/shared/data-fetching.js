import { getCookie, getToken } from "./utils.js";
import { processIdAPI } from "./url.js";

const csrfToken = getCookie('csrftoken');
const token = getToken();

export let processList = [];

export async function fetcProcesses() {
    try {   
        const res = await fetch(processIdAPI, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'X-CSRFToken': csrfToken
            }
        });

        if (!res.ok) {
            const errorText = await res.text();
            console.error('HTTP Error', res.status, errorText);
            throw new Error('Unable to fetch processes.')
        }

        processList = await res.json();
        return processList;
    } catch (err) {
        console.error('Failed to fetchn processes.');
        throw err;
    }
}
import { getCookie, getToken } from "../shared/utils.js";
const csrftoken = getCookie('csrftoken');
const token = getToken();

import { imageData } from "./fileHandler2.js";
/**
 * Uploads imageData (selected files and associated u_ids) to the backend
 */

export async function uploadImage() {
    //const processID = document.getElementById('processInput').value;
    const data = new FormData();
    console.log('Image Data', imageData);

    imageData.forEach(img => {
        data.append('u_ids', img.id);
        data.append('process_ids', img.process_id);
        data.append('image_files', img.file);
    });

    console.log('Data sent to the backend', Object.fromEntries(data));

    try {
        const res = await fetch('http://127.0.0.1:8000/batch-encoder/image-upload/', {
            method: 'POST',
            headers: {
                'Authorization': `Token ${token}`,
                'X-CSRFToken': csrftoken
            },
            body: data
        });

        if (!res.ok) {
            const errorText = await res.text();
            console.error('Upload error:', errorText);
            throw new Error('Upload failed.');
        }

        alert('Upload successful!');
        window.location.reload();
    } catch(error) {
        console.error('Upload error:', error);
        alert('Upload failed. Please try again.');
    }
}


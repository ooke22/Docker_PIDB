import { processUploadAPI } from "C:/PI Local Tests/Frontend/url.js";
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

const csrftoken = getCookie('csrftoken');

async function uploadProcess() {
    var process_id = document.getElementById('process_id').value;
    var scope = document.getElementById('scope').value;
    var description = document.getElementById('description').value;
    var source = document.getElementById('source').files[0];

    var data = new FormData();
    data.append('process_id', process_id);
    data.append('scope', scope);
    data.append('description', description);
    data.append('source', source, source.name);

    try {
        console.log('Data to be sent: ', Array.from(data.entries()));

        const token = localStorage.getItem('token');
        const response = await fetch(processUploadAPI, {
            method: 'POST',
            headers: {
                'Authorization': `${token}`,
                'X-CSRFToken': csrftoken
            },
            body: data,
        });
        if (!response.ok) {
            const errorText = await response.text();
            console.error('HTTP error details: ', response.status, errorText)
        }

        const responseData = await response.json();
		console.log('Data posted successfully:', responseData);
		
		// Check if the callback function exists in the Batch Encoder Window
		if(window.opener && window.opener.handleDropDownUpdate) {
			// Call the callback function to update the dropdown
			winow.opener.handleDropDownUpdate(responseData.process_list);
		}
		alert('Process uploaded successfully!');
		window.location.reload(); // Reload page after upload.
    } catch (error) {
        console.error('Error posting data:', error);
		alert('Error uploading process. Please try again.');
    }
}

document.getElementById('uploadButton').addEventListener('click', uploadProcess);



import { processIdAPI, testBatchEncoderAPI2, } from "C:/PI Local Tests/Frontend/url.js";

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


// Function to update the dropdown with Process IDs
function handleCheckboxUpdate(processList) {
    var checkboxContainer = document.getElementById('wafer_process_checkbox_list');

    if (checkboxContainer) {
        checkboxContainer.innerHTML = ''; // Clear previous options

        processList.forEach(function (process) {
            var checkboxLabel = document.createElement('label');
            var checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.value = process.process_id; // Value set to process_id
            checkbox.name = 'wafer_process_id';

            // Create timestamp input field
            var timestampInput = document.createElement('input');
            timestampInput.type = 'datetime-local';
            timestampInput.name = 'wafer_process_timestamp';

            checkboxLabel.appendChild(checkbox);
            checkboxLabel.appendChild(document.createTextNode(process.process_id));
            checkboxLabel.appendChild(timestampInput); // Append timestamp input next to checkbox
            checkboxContainer.appendChild(checkboxLabel);
        });
    }
}

// Function to populate the checkbox with process IDs on page load
async function onPageLoad() {
    try {
        const token = localStorage.getItem('token');
        const response = await fetch(processIdAPI, {
            method: 'GET',
            headers: {
                'Authorization': `Token ${token}`,
                'X-CSRFToken': csrftoken,
            }
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error('HTTP error details:', response.status, errorText);
            throw new Error('Unable to fetch processes.');
        }

        const processList = await response.json();
        handleCheckboxUpdate(processList); // Populate checkbox
    } catch (error) {
        console.error('Error fetching processes:', error);
        alert('Error fetching processes. Please try again');
    }
}

function showProcessInfo() {
    const processInforUrl = "https://pidb-bucket.s3.ap-southeast-4.amazonaws.com/frontend/process_views.html"; 
    window.open(processInforUrl, "_blank");
}

// Function to handle POST request to batch_encoder
// Function to handle POST request to batch_encoder
async function postBatchData() {
    var fields = ["batch_location", "batch_id", "batch_label", "batch_description", "total_wafers", "total_sensors", "wafer_label", "wafer_description", 
                  "wafer_design_id", "wafer_build_time", "sensor_label", "sensor_description"];
    
    var elem = {};  // Object to collect form field values

    // Loop through each field and collect values
    fields.forEach(field => {
        var element = document.getElementById(field);
        if (element) {
            elem[field] = field === "wafer_build_time" ? new Date(element.value).toISOString() : element.value;
        }
    });

    // Get selected wafer process IDs and timestamps
    var selectedProcesses = [];
    document.querySelectorAll('input[name="wafer_process_id"]:checked').forEach((checkbox, index) => {
        const timestampField = checkbox.parentNode.querySelector('input[name="wafer_process_timestamp"]');
        selectedProcesses.push({
            process_id: checkbox.value,
            timestamp: timestampField ? new Date(timestampField.value).toISOString() : null
        });
    });

    elem['sensor_processes'] = selectedProcesses;

    console.log('Batch Data', JSON.stringify(elem));

    // POST request
    try {
        const token = localStorage.getItem('token');
        const response = await fetch(testBatchEncoderAPI2, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Token ${token}`,
                'X-CSRFToken': csrftoken,
            },
            body: JSON.stringify(elem)
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error('HTTP error details:', response.status, errorText);
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        const responseData = await response.json();
        console.log('Response Data:', responseData);
        if (response.status === 201) {
            document.getElementById('error-output').innerText = 'Batch Created Successfully!';
            alert('Batch created successfully!');
            window.location.reload();
        }
    } catch (error) {
        console.error('Error posting data', error);
        document.getElementById('error-output').innerText = `Error: ${error.message}`;
        throw error;
    }
}



window.onload = function() {
    //fetchUserInfo();
    //startLogoutTimer();
    onPageLoad();
}

document.querySelector('.info-icon').addEventListener('click', showProcessInfo);

document.getElementById('postBatchData').addEventListener('click', postBatchData);

//document.getElementById('logoutBtn').addEventListener('click', logout);





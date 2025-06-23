import { retrieveElectrodeAPI, electrodeUpdateUrl } from "https://pidb-bucket.s3.ap-southeast-4.amazonaws.com/frontend/url.js";

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

function createUpdateTable() {
    var table = document.getElementById('updateTable');

    const fieldsToUpdate = [
        'batch_label', 'batch_description', 'wafer_label', 'wafer_description', 'wafer_design_id',
        'wafer_process_id', 'wafer_build_time', 'sensor_label', 'sensor_description', 'electrode_type',
        'electrode_label', 'electrode_description'
    ];

    for (var i = 0; i < fieldsToUpdate.length; i++) {
        var row = table.insertRow(i + 1);

        // Field cell
        var fieldCell = row.insertCell(0);
        fieldCell.innerHTML = fieldsToUpdate[i].replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());

        // Checkbox cell
        var checkboxCell = row.insertCell(1);
        var checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.id = `update_${fieldsToUpdate[i]}`;
        checkbox.name = `update_${fieldsToUpdate[i]}`;
        checkboxCell.appendChild(checkbox);

        // New Value cell
        var newValueCell = row.insertCell(2);
        var newValueInput = document.createElement('input');
        newValueInput.type = 'text';
        newValueInput.id = `new_${fieldsToUpdate[i]}`;
        newValueInput.name = `new_${fieldsToUpdate[i]}`;
        newValueCell.appendChild(newValueInput);

        // Attach event listener to the 'New Values' input element
        newValueInput.addEventListener('input', createInputListener(checkbox));
    }
}

// Helper function to create an input listener with closure
function createInputListener(checkbox) {
    return function () {
        // Automatically select the corresponding checkbox when a user enters a new value
        checkbox.checked = this.value !== '';
    };
}

async function retrieveData() {
    var batchLocation = document.getElementById('batch_location').value;
    var batchId = document.getElementById('batch_id').value;

    try {
        const token = localStorage.getItem('token');
        const url = retrieveElectrodeAPI(batchLocation, batchId); // Generate the full API
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Authorization': `Token ${token}`,
                'X-CSRFToken': csrftoken,
            }
        });
        if (!response.ok) {
            throw new Error(`HTTP error: Status: ${response.status}`);
        }

        const data = await response.json();
        console.log('Retrieved Data: ', data);

        // Display electrode Details
        document.getElementById('batchLocation').innerText = 'Batch Location: ' + data.batch_location;
        document.getElementById('batchId').innerText = 'Batch ID: ' + data.batch_id;
        document.getElementById('waferIds').innerText = 'Total Wafers: ' + data.total_wafers;
        document.getElementById('sensorIds').innerText = 'Total Sensors: ' + data.total_sensors;
        document.getElementById('electrodeIds').innerText = 'Total Electrodes: ' + data.total_electrodes;

        document.getElementById('electrodeDetails').style.display = 'block';

        // Call createUpdateTable after data has been retrieved
        createUpdateTable();
        
    } catch (error) {
        console.error('Error retrieving batch details: ', error);
    }
}

async function updateElectrode() {
    var batchLocation = document.getElementById('batch_location').value;
    var batchId = document.getElementById('batch_id').value;

    try {
        const fieldsToUpdate = Array.from(document.querySelectorAll('input[id^="update_"]:checked')).map(checkbox => checkbox.name.replace('update_', ''));

        const newData = {};
        fieldsToUpdate.forEach(field => {
            const newValue = document.getElementById(`new_${field}`).value;
            newData[field] = newValue;
        })

        const waferIds = document.getElementById('update_wafer_ids').value;
        const sensorIds = document.getElementById('update_sensor_ids').value;
        const electrodeIds = document.getElementById('update_electrode_ids').value;

        const token = localStorage.getItem('token');
        const url = electrodeUpdateUrl(batchLocation, batchId);
        const response = await fetch(url, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Token ${token}`,
                'X-CSRFToken': csrftoken,
            },
            body: JSON.stringify({
                wafer_ids: waferIds,
                sensor_ids: sensorIds,
                electrode_ids: electrodeIds,
                update_data: newData,
            }),
        });

        if(!response.ok) {
            const errorText = await response.text();
            console.error('HTTP error details: ', response.status, errorText);
            throw new Error('HTTP error! Status: ' + response.status)
        }

        const data = await response.json();
        alert('Update Successful!');
    } catch (error) {
        console.error('Error updating electrodes: ', error);
        alert('Error updating electrodes.');
    }

}

document.getElementById('retrieveButton').addEventListener('click', retrieveData);

document.getElementById('updateButton').addEventListener('click', updateElectrode);


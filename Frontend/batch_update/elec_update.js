import { retrieveBatchDetailURL, batchUpdateUrl } from "../shared/url.js";
import { getCookie, getToken } from "../shared/utils.js";
import { fetcProcesses } from "../shared/data-fetching.js";
import { createUpdateTable, renderWaferProcessesTable } from "../shared/table-utils.js";
import { populateProcessDropdown, selectedProcessList } from "../shared/process-utils.js";

const csrftoken = getCookie('csrftoken');
const token = getToken();

const fieldsToUpdate = [
    'batch_label', 'batch_description', 'wafer_label',
    'wafer_description', 'wafer_design_id', 'sensor_label', 'sensor_description'
];

let deleteList = [];

async function retrieveData() {
    const loader = document.getElementById('loader');
    loader.style.display = 'block';

    const batchLocation = document.getElementById('batch_location').value;
    const batchID = document.getElementById('batch_id').value;

    try {
        const url = retrieveBatchDetailURL(batchLocation, batchID);
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Authorization': `Token ${token}`,
                'X-CSRFToken': csrftoken,
            }
        });

        if (!response.ok) throw new Error(`HTTP error: Status: ${response.status}`);

        const data = await response.json();
        console.log('Retrieved Data:', data);

        document.getElementById('batchLocation').innerText = `Batch Location: ${data.batch_location}`;
        document.getElementById('batchId').innerText = `Batch ID: ${data.batch_id}`;
        document.getElementById('waferIds').innerText = `Total Wafers: ${data.total_wafers}`;
        document.getElementById('sensorIds').innerText = `Total Sensors: ${data.total_sensors}`;

        renderWaferProcessesTable(data.sensor_processes, deleteList);
        document.getElementById('electrodeDetails').style.display = 'block';
        createUpdateTable([], fieldsToUpdate);

    } catch (error) {
        console.error('Error retrieving batch details:', error);
    } finally {
        loader.style.display = 'none';
    }
}

let processes = [];

async function retrieveProcesses() {
    try {
        processes = await fetcProcesses();
        populateProcessDropdown(processes);
    } catch (error) {
        console.error('Error retrieving processes: ', error);
    }    
}

async function updateElectrode() {
    const loader = document.getElementById('loader');
    const overlay = document.getElementById('overlay');
    loader.style.display = 'block';
    overlay.style.display = 'block';

    const newProcessData = selectedProcessList;
    console.log('New Process Data:', newProcessData);

    const batchLocation = document.getElementById('batch_location').value;
    const batchID = document.getElementById('batch_id').value;

    const updateData = {};
    fieldsToUpdate.forEach(field => {
        const checkbox = document.getElementById(`update_${field}`);
        const newValue = document.getElementById(`new_${field}`).value;
        if (checkbox.checked && newValue) {
            updateData[field] = newValue;
        }
    });

    const requestBody = JSON.stringify({
        wafer_ids: document.getElementById('wafer_ids').value,
        sensor_ids: document.getElementById('sensor_ids').value,
        new_process_data: newProcessData,
        updates: updateData,
        delete_list: deleteList
    });

    console.log('Data sent to the backend:', JSON.parse(requestBody));
    try {
        //const updateURL = batchUpdateUrl(batchLocation, batchID);
        const response = await fetch(`http://127.0.0.1/batch-encoder/update-batch/${batchLocation}/${batchID}/`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Token ${token}`,
                'X-CSRFToken': csrftoken,
            },
            body: JSON.stringify({
                wafer_ids: document.getElementById('wafer_ids').value,
                sensor_ids: document.getElementById('sensor_ids').value,
                new_process_data: newProcessData,
                updates: updateData,
                delete_list: deleteList
            }),
        });

        if(!response.ok) {
            const errorText = await response.text();
            console.error('HTTP error details: ', response.status, errorText);
            throw new Error('HTTP error! Status: ' + response.status)
        } else {
            const data = await response.json();
            console.log('Update response:', data);
            alert(`Update Successful!`);
            deleteList = [];
            window.location.reload();
        }
    } catch (error) {
        console.error('Error updating sensors: ', error);
        alert('Error updating sensors.');
    } finally {
        loader.style.display = 'none';
        overlay.style.display = 'none';
    }
}

document.getElementById('loader').style.display = 'none';
document.getElementById('retrieveButton').addEventListener('click', retrieveData);
document.getElementById('updateButton').addEventListener('click', updateElectrode);

retrieveProcesses();

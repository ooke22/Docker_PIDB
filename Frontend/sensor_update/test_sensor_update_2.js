// main.js
import {
    //normalizeSensorId,
    //createInputListener,
    //formatDate,
    saveSensorCache,
    loadSensorCache,
    mergeValidatedSensors,
    mergeOriginalSensorIds,
    parseNormalizedSensorIds,
    validationMessaages
} from './utils.js';

import {
    renderResults,
    createUpdateTable,
    populateProcessDropdown,
    selectedProcessList,
    //highlightSelectedProcess,
    //handleProcessSelection,
    //addProcesstoTable,
    //populateProcessDetails
} from './render.js';

let labelOptions = [];
let allValidatedSensors = [];
let allOriginalSensorIds = [];
let deleteList = [];
let processes = [];
//let selectedProcessList = [];

document.addEventListener('DOMContentLoaded', async () => {
    await fetchLabels();
    await retrieveProcesses();
    loadCachedSensors();
    document.getElementById('loader').style.display = 'none';
});

async function fetchLabels() {
    try {
        const token = localStorage.getItem('token');
        const response = await fetch('http://127.0.0.1:8000/test/s_l/', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        labelOptions = await response.json();
    } catch (error) {
        console.error('Error loading labels:', error);
    }
}

async function retrieveProcesses() {
    const token = localStorage.getItem('token');
    try {
        const response = await fetch('http://127.0.0.1:8000/process-test/get_processes/', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        processes = await response.json();
        populateProcessDropdown(processes);
    } catch (err) {
        console.error('Failed to fetch processes:', err);
    }
}

function loadCachedSensors() {
    const cache = loadSensorCache();
    if (cache && cache.validated.length > 0) {
        allValidatedSensors = cache.validated;
        allOriginalSensorIds = cache.original;
        renderResults(allValidatedSensors);
        createUpdateTable(labelOptions);
        document.getElementById('updateFields').style.display = 'block';
    }
}

function saveCurrentSensorStateToLocalStorage() {
    saveSensorCache(allValidatedSensors, allOriginalSensorIds);
}

async function validateSensors() {
    const loader = document.getElementById('loader');
    loader.style.display = 'block';

    const rawInput = document.getElementById('u_id').value;
    const { normalizedIds, failed, normalizedMap } = parseNormalizedSensorIds(rawInput);
    
    if (!normalizedIds.length) {
        alert("No valid sensor IDs provided.");
        loader.style.display = 'none';
        return;
    }

    try {
        const res = await fetch('http://127.0.0.1:8000/test/verify_sensors_3/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            },
            body: JSON.stringify({ sensors: normalizedIds })
        });

        const result = await res.json();
        const verifiedSensors = Array.isArray(result) ? result : (result.validated_sensors || []);
        const verifiedIds = verifiedSensors.map(s => s.unique_identifier);

        const notFound = normalizedIds.filter(id => !verifiedIds.includes(id));
        const alreadyAdded = verifiedIds.filter(id => allOriginalSensorIds.includes(id));

        allValidatedSensors = mergeValidatedSensors(allValidatedSensors, verifiedSensors);
        allOriginalSensorIds = mergeOriginalSensorIds(allOriginalSensorIds, Object.keys(normalizedMap));

        renderResults(allValidatedSensors);
        createUpdateTable(labelOptions);
        document.getElementById('updateFields').style.display = 'block';

        const feedback = validationMessaages({
            failed, notFound, alreadyAdded
        });
        if (feedback) alert("Some sensors were not added:\n\n" + feedback);

        // Optional: save state
        saveCurrentSensorStateToLocalStorage();
    } catch (err) {
        console.error('Verification failed', err);
        alert('Sensor verification failed due to an unexpected error.');
    } finally {
        loader.style.display = 'none';
    }
}

function navigatetoWaferForm() {
    saveCurrentSensorStateToLocalStorage();
    window.location.href = 'wafer_form.html';
}

async function submitUpdates() {
    const loader = document.getElementById('loader');
    const overlay = document.getElementById('overlay');
    loader.style.display = 'block';
    overlay.style.display = 'block';
    const token = localStorage.getItem('token');

    const labelCheckbox = document.getElementById('update_label');
    const descCheckbox = document.getElementById('update_sensor_description');

    const payload = {
        u_ids: allValidatedSensors.map(s => s.unique_identifier),
        updates: {},
        new_process_data: selectedProcessList || [],
        delete_list: deleteList || []
    };

    if (labelCheckbox && labelCheckbox.checked) {
        const labelSelect = document.getElementById('new_label');
        if (labelSelect && labelSelect.value) {
            payload.updates.label = labelSelect.value;
        }
    }

    if (descCheckbox && descCheckbox.checked) {
        const descInput = document.getElementById('new_sensor_description');
        if (descInput && descInput.value) {
            payload.updates.sensor_description = descInput.value;
        }
    }
    console.log("Submitting payload to the backed", payload);

    try {
        const res = await fetch('http://127.0.0.1:8000/test/sensor/bulk-update/', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(payload)
        });

        if (res.status === 404) {
            const errorMsg = await res.text();
            console.error('Sensor not found:', errorMsg);
            alert('Sensor not found');
            return;
        }

        if (!res.ok) {
            const errorText = await res.text();
            console.error('HTTP error details:', res.status, errorText);
            throw new Error('HTTP error! Status: ' + res.status);
            //alert("An error occured while updating sensors.");
        }

        const result = await res.json();
        console.log('Update result:', result);
        alert("Sensor update successful");

        selectedProcessList.length = 0;
        deleteList.length = 0;

        document.getElementById('addedProcessTableBody').innerHTML = '';
        document.getElementById('processTableBody').innerHTML = '';
        window.location.reload();
    } catch (err) {
        console.error('Update failed', err);
    } finally {
        loader.style.display = 'none';
        overlay.style.display = 'none';
    }
    
}

function resetSensorState() {
    localStorage.removeItem('wafer_validated_sensors_cache');
    allValidatedSensors = [];
    allOriginalSensorIds = [];
    deleteList = [];
    renderResults([]);
    document.getElementById('u_id').value = '';
    document.getElementById('updateFields').style.display = 'none';
}

// Handle reload cache clearing
if (performance.getEntriesByType("navigation")[0]?.type === "reload") {
    localStorage.removeItem('wafer_validated_sensors_cache');
}

document.getElementById('resetBtn').addEventListener('click', resetSensorState);
document.getElementById('navtoWF').addEventListener('click', navigatetoWaferForm);
document.getElementById('updateButton').addEventListener('click', submitUpdates);
document.getElementById('sensorForm').addEventListener('submit', function (e) {
    e.preventDefault();
    validateSensors();
});

// unified_sensor_batch_update.js
import {
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
    selectedProcessList
} from './render.js';

let labelOptions = [];
let allValidatedSensors = [];
let allOriginalSensorIds = [];
let deleteList = [];
let processes = [];

// ====== DOM References ======
const loader = document.getElementById('loader');
const overlay = document.getElementById('overlay');
const uIdInput = document.getElementById('u_id');
const sensorForm = document.getElementById('sensorForm');
const updateButton = document.getElementById('updateButton');
const resetBtn = document.getElementById('resetBtn');
const navToWaferBtn = document.getElementById('navtoWF');
const toggleBatchFormBtn = document.getElementById('toggleBatchForm');
const batchFormContainer = document.getElementById('batchFormContainer');
const retrieveBatchBtn = document.getElementById('retrieveBatchBtn');
const batchLocationInput = document.getElementById('batch_location');
const batchIdInput = document.getElementById('batch_id');
const batchMetadataDiv = document.getElementById('batchMetadata');
const batchDescriptionSpan = document.getElementById('batchDescription');
const batchLabelSpan = document.getElementById('batchLabel');
const totalWafersSpan = document.getElementById('totalWafers');
const totalSensorsSpan = document.getElementById('totalSensors');

// ====== Initialization ======
document.addEventListener('DOMContentLoaded', async () => {
    loader.style.display = 'block';
    await fetchLabels();
    await retrieveProcesses();
    loadCachedSensors();
    loader.style.display = 'none';
});

// ====== Fetch labels & processes ======
async function fetchLabels() {
    try {
        const token = localStorage.getItem('token');
        const response = await fetch('http://127.0.0.1:8000/batch-encoder/s-l/', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        labelOptions = await response.json();
    } catch (err) {
        console.error('Error fetching labels:', err);
    }
}

async function retrieveProcesses() {
    try {
        const token = localStorage.getItem('token');
        const response = await fetch('http://127.0.0.1:8000/process-test/get_processes/', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        processes = await response.json();
        populateProcessDropdown(processes);
    } catch (err) {
        console.error('Error fetching processes:', err);
    }
}

// ====== Cache Management ======
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

// ====== Sensor & Batch Verification ======
async function verifySensorsFrontend({ u_ids = [], batch_location, batch_id }) {
    loader.style.display = 'block';
    try {
        const payload = {};
        if (u_ids.length) payload.sensors = u_ids;
        if (batch_location && batch_id) {
            payload.batch_location = batch_location;
            payload.batch_id = batch_id;
        }

        const res = await fetch('http://127.0.0.1:8000/batch-encoder/verify-sensors/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        console.log('res', data);

        if (res.status !== 200 || (!data.validated_sensors || data.validated_sensors.length === 0 || !data.batch_meta)) {
            alert('No valid sensors found.');
            return null;
        }

        return data;
    } catch (err) {
        console.error('Verification failed:', err);
        alert('Sensor/batch verification failed.');
        return null;
    } finally {
        loader.style.display = 'none';
    }
}

// ====== Validate Sensors via U_ID Input ======
async function validateSensors() {
    const rawInput = uIdInput.value.trim();
    const { normalizedIds, failed, normalizedMap } = parseNormalizedSensorIds(rawInput);
    
    if (!normalizedIds.length) {
        alert("No valid sensor IDs provided.");
        return;
    }

    const result = await verifySensorsFrontend({ u_ids: normalizedIds });
    if (!result) return;

    const verifiedSensors = result.validated_sensors;
    const verifiedIds = verifiedSensors.map(s => s.unique_identifier);
    const notFound = normalizedIds.filter(id => !verifiedIds.includes(id));
    const alreadyAdded = verifiedIds.filter(id => allOriginalSensorIds.includes(id));

    allValidatedSensors = mergeValidatedSensors(allValidatedSensors, verifiedSensors);
    allOriginalSensorIds = mergeOriginalSensorIds(allOriginalSensorIds, Object.keys(normalizedMap));

    renderResults(allValidatedSensors);
    createUpdateTable(labelOptions);
    document.getElementById('updateFields').style.display = 'block';

    const feedback = validationMessaages({ failed, notFound, alreadyAdded });
    if (feedback) alert("Some sensors were not added:\n\n" + feedback);

    saveCurrentSensorStateToLocalStorage();
}

// ====== Validate Sensors via Batch Input ======
async function validateBatch() {
    const batch_location = batchLocationInput.value.trim();
    const batch_id = batchIdInput.value.trim();
    if (!batch_location || !batch_id) {
        alert('Please provide both batch location and batch ID.');
        return;
    }

    const result = await verifySensorsFrontend({ batch_location, batch_id });
    if (!result) return;

    const verifiedSensors = result.validated_sensors;
    allValidatedSensors = mergeValidatedSensors(allValidatedSensors, verifiedSensors);
    allOriginalSensorIds = mergeOriginalSensorIds(allOriginalSensorIds, verifiedSensors.map(s => s.unique_identifier));

    renderResults(allValidatedSensors);
    createUpdateTable(labelOptions);
    document.getElementById('updateFields').style.display = 'block';

    // Populate batch metadata
    const meta = result.batch_meta;
    if (meta) {
        batchDescriptionSpan.textContent = meta.batch_description;
        batchLabelSpan.textContent = meta.batch_label || '-';
        totalWafersSpan.textContent = meta.total_wafers;
        totalSensorsSpan.textContent = meta.total_sensors;
        batchMetadataDiv.style.display = 'block';
    }

    saveCurrentSensorStateToLocalStorage();
}

// ====== Update Submission ======
async function submitUpdates() {
    loader.style.display = 'block';
    overlay.style.display = 'block';

    const payload = {
        u_ids: allValidatedSensors.map(s => s.unique_identifier),
        updates: {},
        new_process_data: selectedProcessList || [],
        delete_list: deleteList || []
    };

    // Optional label/description update
    const labelCheckbox = document.getElementById('update_label');
    const descCheckbox = document.getElementById('update_sensor_description');
    if (labelCheckbox?.checked) {
        const labelSelect = document.getElementById('new_label');
        if (labelSelect?.value) payload.updates.label = labelSelect.value;
    }
    if (descCheckbox?.checked) {
        const descInput = document.getElementById('new_sensor_description');
        if (descInput?.value) payload.updates.sensor_description = descInput.value;
    }

    try {
        const res = await fetch('http://127.0.0.1:8000/batch-encoder/update/', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const errText = await res.text();
            throw new Error(`HTTP ${res.status}: ${errText}`);
        }

        alert('Update successful');
        selectedProcessList.length = 0;
        deleteList.length = 0;
        document.getElementById('addedProcessTableBody').innerHTML = '';
        document.getElementById('processTableBody').innerHTML = '';
        saveCurrentSensorStateToLocalStorage();
        window.location.reload();
    } catch (err) {
        console.error('Update failed:', err);
        alert('Update failed. See console for details.');
    } finally {
        loader.style.display = 'none';
        overlay.style.display = 'none';
    }
}

// ====== Reset State ======
function resetSensorState() {
    localStorage.removeItem('wafer_validated_sensors_cache');
    allValidatedSensors = [];
    allOriginalSensorIds = [];
    deleteList = [];
    renderResults([]);
    uIdInput.value = '';
    document.getElementById('updateFields').style.display = 'none';
    batchMetadataDiv.style.display = 'none';
}

// ====== Navigation ======
function navigateToWaferForm() {
    saveCurrentSensorStateToLocalStorage();
    window.location.href = 'wafer_form.html';
}

// ====== Event Listeners ======
sensorForm.addEventListener('submit', e => { e.preventDefault(); validateSensors(); });
updateButton.addEventListener('click', submitUpdates);
resetBtn.addEventListener('click', resetSensorState);
navToWaferBtn.addEventListener('click', navigateToWaferForm);
toggleBatchFormBtn.addEventListener('click', () => {
    batchFormContainer.style.display = batchFormContainer.style.display === 'none' ? 'block' : 'none';
});
retrieveBatchBtn.addEventListener('click', validateBatch);

// ====== Clear cache on reload ======
if (performance.getEntriesByType("navigation")[0]?.type === "reload") {
    localStorage.removeItem('wafer_validated_sensors_cache');
}

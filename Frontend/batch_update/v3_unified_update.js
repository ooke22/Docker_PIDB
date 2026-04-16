// sensor_update_unified.js
// Reworked to call your unified backend endpoint supporting both 'batch' and 'individual' strategies.
// Assumes this file runs as a module (type="module") in the page.

import { fetcProcesses } from "../shared/data-fetching.js";
import { createUpdateTable, renderWaferProcessesTable } from "../shared/table-utils.js";
import { populateProcessDropdown, selectedProcessList } from "../shared/process-utils.js";
import { getCookie, getToken } from "../shared/utils.js";

const csrftoken = getCookie('csrftoken');
const token = getToken();

// ----- Config / endpoints -----
// Adjust API_BASE if your backend is not at the same host/port
const API_BASE = window.API_BASE || 'http://127.0.0.1:8000';

// unified endpoint (your unified_sensor_update_endpoint)
const UNIFIED_UPDATE_URL = `${API_BASE}/api/unified_sensor_update/`;

// batch detail retrieval (unchanged)
const BATCH_DETAIL = (batchLocation, batchID) =>
  `${API_BASE}/batch-encoder/batch-detail/${encodeURIComponent(batchLocation)}/${encodeURIComponent(batchID)}/`;

// Optional task status endpoint (implement server-side for polling)
const TASK_STATUS = (taskId) => `${API_BASE}/api/task-status/${encodeURIComponent(taskId)}/`;

// Fields allowed on UI to toggle/update (keeps parity with your backend allowed fields)
const fieldsToUpdate = [
    'batch_label', 'batch_description', 'wafer_label',
    'wafer_description', 'wafer_design_id', 'sensor_label', 'sensor_description'
];

let deleteList = []; // filled by renderWaferProcessesTable / UI interactions
let processes = [];

// ------- Helper UI functions -------
function showLoader() {
    const loader = document.getElementById('loader');
    if (loader) loader.style.display = 'block';
}
function hideLoader() {
    const loader = document.getElementById('loader');
    if (loader) loader.style.display = 'none';
}
function showOverlay() {
    const overlay = document.getElementById('overlay');
    if (overlay) overlay.style.display = 'block';
}
function hideOverlay() {
    const overlay = document.getElementById('overlay');
    if (overlay) overlay.style.display = 'none';
}

function safeJsonResponse(resp) {
    // Try to parse json, otherwise return raw text
    return resp.text().then(txt => {
        try { return JSON.parse(txt); }
        catch(e) { return { text: txt }; }
    });
}

// ------- Fetch / render data for a batch -------
async function retrieveData() {
    showLoader();

    const batchLocationEl = document.getElementById('batch_location');
    const batchIdEl = document.getElementById('batch_id');
    if (!batchLocationEl || !batchIdEl) {
        console.error('Missing batch_location or batch_id inputs in DOM');
        hideLoader();
        return;
    }

    const batchLocation = batchLocationEl.value.trim();
    const batchID = batchIdEl.value.trim();

    if (!batchLocation || !batchID) {
        alert('Please provide both Batch Location and Batch ID.');
        hideLoader();
        return;
    }

    try {
        const url = BATCH_DETAIL(batchLocation, batchID);
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Authorization': token ? `Token ${token}` : '',
                'X-CSRFToken': csrftoken,
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status} retrieving batch detail`);
        }

        const data = await response.json();
        console.log('Retrieved Data:', data);

        // Render summary info
        const elBatchLocation = document.getElementById('batchLocation');
        const elBatchId = document.getElementById('batchId');
        const elWaferIds = document.getElementById('waferIds');
        const elSensorIds = document.getElementById('sensorIds');

        if (elBatchLocation) elBatchLocation.innerText = `Batch Location: ${data.batch_location ?? ''}`;
        if (elBatchId) elBatchId.innerText = `Batch ID: ${data.batch_id ?? ''}`;
        if (elWaferIds) elWaferIds.innerText = `Total Wafers: ${data.total_wafers ?? ''}`;
        if (elSensorIds) elSensorIds.innerText = `Total Sensors: ${data.total_sensors ?? ''}`;

        // Render wafer/processes table (existing util)
        renderWaferProcessesTable(data.sensor_processes ?? [], deleteList);

        // Reveal UI
        const electrodeDetails = document.getElementById('electrodeDetails');
        if (electrodeDetails) electrodeDetails.style.display = 'block';

        // Build Update table (createUpdateTable can accept preselected fields)
        createUpdateTable([], fieldsToUpdate);

    } catch (err) {
        console.error('Error retrieving batch details:', err);
        alert('Error retrieving batch details. See console for more info.');
    } finally {
        hideLoader();
    }
}

// ------- Processes list (dropdown) -------
async function retrieveProcesses() {
    try {
        processes = await fetcProcesses();
        populateProcessDropdown(processes);
    } catch (error) {
        console.error('Error retrieving processes: ', error);
    }    
}

// ------- Poll task status (optional) -------
// Tries to poll TASK_STATUS(task_id) if your backend implements it. If not available, it fails gracefully.
async function pollTaskStatus(taskId, onUpdate = null, opts = {}) {
    if (!taskId) return null;
    const maxAttempts = opts.maxAttempts || 18;
    let attempt = 0;
    let delay = 1000; // start 1s

    while (attempt < maxAttempts) {
        attempt++;
        try {
            const resp = await fetch(TASK_STATUS(taskId), {
                method: 'GET',
                headers: {
                    'Authorization': token ? `Token ${token}` : '',
                    'X-CSRFToken': csrftoken,
                }
            });

            if (resp.status === 404) {
                // No task-status endpoint implemented; bail out
                console.warn('Task status endpoint returned 404 - skipping polling.');
                return null;
            }

            if (!resp.ok) {
                console.warn('Task status polling got non-OK status:', resp.status);
                // treat as transient and continue retrying
            } else {
                const json = await resp.json();
                // Typical expected response: { state: 'PENDING'|'PROGRESS'|'SUCCESS'|'FAILURE', meta: {...} }
                if (onUpdate) onUpdate(json);

                if (json.state === 'SUCCESS' || json.state === 'FAILURE') {
                    return json;
                }
            }

        } catch (e) {
            console.warn('Task status polling error:', e);
            // swallow and retry
        }

        // exponential backoff (bounded)
        await new Promise(r => setTimeout(r, delay));
        delay = Math.min(delay * 1.5, 8000);
    }

    // timeout - return null (task may still be running)
    return null;
}

// ------- Send a batch update using the unified API -------
async function updateElectrodeBatch() {
    showLoader();
    showOverlay();

    try {
        // collect update fields
        const updateData = {};
        fieldsToUpdate.forEach(field => {
            const checkbox = document.getElementById(`update_${field}`);
            const newValueEl = document.getElementById(`new_${field}`);
            const newValue = newValueEl ? newValueEl.value : '';
            if (checkbox && checkbox.checked && newValue) {
                updateData[field] = newValue;
            }
        });

        const newProcessData = selectedProcessList || [];

        const batchLocation = document.getElementById('batch_location')?.value?.trim();
        const batchID = document.getElementById('batch_id')?.value?.trim();

        if (!batchLocation || !batchID) {
            alert('Please provide both Batch Location and Batch ID before updating.');
            return;
        }

        // Payload matches unified endpoint expectations
        const payload = {
            selection_strategy: 'batch',
            batch_location: batchLocation,
            batch_id: isNaN(Number(batchID)) ? batchID : Number(batchID),
            wafer_ids: document.getElementById('wafer_ids')?.value || '',
            sensor_ids: document.getElementById('sensor_ids')?.value || '',
            updates: updateData,
            new_process_data: newProcessData,
            delete_list: deleteList
        };

        console.debug('Sending batch update payload:', payload);

        const resp = await fetch(UNIFIED_UPDATE_URL, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': token ? `Token ${token}` : '',
                'X-CSRFToken': csrftoken,
            },
            body: JSON.stringify(payload),
        });

        if (!resp.ok) {
            const body = await safeJsonResponse(resp);
            console.error('Update failed:', resp.status, body);
            const errMsg = (body && body.error) ? body.error : `HTTP ${resp.status}`;
            alert(`Update failed: ${errMsg}`);
            return;
        }

        const json = await resp.json();
        console.log('Update response:', json);

        const taskId = json.task_id;
        if (taskId) {
            // Inform the user and poll status if endpoint exists
            console.info(`Task started: ${taskId}`);
            // Try polling (optional): if your backend doesn't expose /api/task-status/<id>/ this will no-op gracefully
            const statusResult = await pollTaskStatus(taskId, (update) => {
                // Called on every poll; update overlay or progress display if you build one.
                console.debug('Task update:', update);
            }, { maxAttempts: 25 });

            if (statusResult) {
                if (statusResult.state === 'SUCCESS') {
                    alert('Update completed successfully.');
                } else if (statusResult.state === 'FAILURE') {
                    alert('Update failed. Check server logs for details.');
                } else {
                    // had some status but not success/failure: show summary
                    alert(`Task finished with state: ${statusResult.state}`);
                }
            } else {
                // Polling not available or timed out — show task id so user can check later
                alert(`Update started (task id: ${taskId}). You can check status later.`);
            }

        } else {
            // Backend didn't return a task id — maybe synchronous response
            alert('Update request completed (no task id returned).');
        }

        // reset deleteList & refresh page (optional)
        deleteList = [];
        // reload to reflect changes (you can replace this with a more targeted refresh)
        window.location.reload();

    } catch (err) {
        console.error('Error updating sensors (batch):', err);
        alert('Error updating sensors. See console for details.');
    } finally {
        hideLoader();
        hideOverlay();
    }
}

// ------- Send an individual update using the unified API -------
// This function attempts to collect validated unique identifiers from the DOM.
// It supports a couple of common render patterns:
//  - checkboxes inside #validated-sensors-container with class .validated-sensor-checkbox (value = uid)
//  - elements with data-uid attribute inside #validated-sensors-container
function collectValidatedUniqueIdentifiers() {
    const container = document.getElementById('validated-sensors-container');
    if (!container) return [];

    // 1) checkbox pattern
    const checkboxes = container.querySelectorAll('input.validated-sensor-checkbox[type="checkbox"]:checked');
    if (checkboxes && checkboxes.length > 0) {
        return Array.from(checkboxes).map(cb => cb.value).filter(Boolean);
    }

    // 2) data-uid elements
    const elementsWithUid = container.querySelectorAll('[data-uid]');
    if (elementsWithUid && elementsWithUid.length > 0) {
        return Array.from(elementsWithUid).map(el => el.getAttribute('data-uid')).filter(Boolean);
    }

    // 3) fallback: inputs named u_id (comma-separated in a single field)
    const singleInput = document.getElementById('u_id');
    if (singleInput && singleInput.value.trim()) {
        // normalize into array by commas
        return singleInput.value.split(',').map(s => s.trim()).filter(Boolean);
    }

    return [];
}

async function updateSensorsIndividual() {
    showLoader();
    showOverlay();

    try {
        const uIds = collectValidatedUniqueIdentifiers();
        if (!uIds || uIds.length === 0) {
            alert('No validated sensors found. Please validate sensors first.');
            return;
        }

        // Collect updates identical to batch flow
        const updateData = {};
        fieldsToUpdate.forEach(field => {
            const checkbox = document.getElementById(`update_${field}`);
            const newValueEl = document.getElementById(`new_${field}`);
            const newValue = newValueEl ? newValueEl.value : '';
            if (checkbox && checkbox.checked && newValue) {
                updateData[field] = newValue;
            }
        });

        const payload = {
            selection_strategy: 'individual',
            u_ids: uIds,
            updates: updateData,
            new_process_data: selectedProcessList || [],
            delete_list: deleteList
        };

        console.debug('Sending individual update payload:', payload);

        const resp = await fetch(UNIFIED_UPDATE_URL, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': token ? `Token ${token}` : '',
                'X-CSRFToken': csrftoken,
            },
            body: JSON.stringify(payload)
        });

        if (!resp.ok) {
            const body = await safeJsonResponse(resp);
            console.error('Individual update failed', resp.status, body);
            const errMsg = (body && body.error) ? body.error : `HTTP ${resp.status}`;
            alert(`Update failed: ${errMsg}`);
            return;
        }

        const json = await resp.json();
        console.log('Individual update response:', json);

        const taskId = json.task_id;
        if (taskId) {
            const statusResult = await pollTaskStatus(taskId, (update) => console.debug('Task update:', update), { maxAttempts: 25 });
            if (statusResult && statusResult.state === 'SUCCESS') {
                alert('Individual update completed successfully.');
            } else {
                alert(`Update started (task id: ${taskId}). Check task status later.`);
            }
        } else {
            alert('Update completed (no task id returned).');
        }

        // optionally reload or update UI
        deleteList = [];
        window.location.reload();

    } catch (err) {
        console.error('Error updating sensors (individual):', err);
        alert('Error updating sensors.');
    } finally {
        hideLoader();
        hideOverlay();
    }
}

// ------- Attach event listeners on DOM ready -------
document.addEventListener('DOMContentLoaded', () => {
    // wire up existing buttons (IDs from your HTML)
    const retrieveBtn = document.getElementById('retrieveButton');
    const updateBtn = document.getElementById('updateButton');
    const validateBtn = document.getElementById('validate'); // if exists for individual flow

    if (retrieveBtn) retrieveBtn.addEventListener('click', retrieveData);

    if (updateBtn) {
        // By default, assume batch update is the configured flow for this page.
        // If you want an explicit "Update Individual" button, wire updateSensorsIndividual() to it instead.
        updateBtn.addEventListener('click', (e) => {
            e.preventDefault();
            // Decide which update to perform:
            // If there are validated unique identifiers in the DOM, prefer individual update; else batch.
            const uids = collectValidatedUniqueIdentifiers();
            if (uids && uids.length > 0) {
                updateSensorsIndividual();
            } else {
                updateElectrodeBatch();
            }
        });
    }

    // If there's an explicit validate (sensor form) button, try to bind it (existing validation flow may be in another module)
    if (validateBtn) {
        validateBtn.addEventListener('click', (e) => {
            // If you have a separate validation flow to fetch/validate sensors, let that run (existing code).
            // This placeholder just prevents default form submission.
            e.preventDefault();
            // If the rest of validation code exists in another file, it will run normally.
        });
    }

    // initialize state
    const loader = document.getElementById('loader');
    if (loader) loader.style.display = 'none';

    // pre-fetch processes
    retrieveProcesses();
}); // end DOMContentLoaded

// Export functions for unit tests / other modules if needed
export {
    retrieveData,
    updateElectrodeBatch,
    updateSensorsIndividual,
    collectValidatedUniqueIdentifiers,
    pollTaskStatus,
};

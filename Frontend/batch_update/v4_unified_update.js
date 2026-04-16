// v3_unified_update.js
// Unified update frontend module (batch + individual).
// Expects shared modules in your repo to exist (data-fetching, table-utils, process-utils, utils).

import { fetcProcesses } from "../shared/data-fetching.js";
import { createUpdateTable, renderWaferProcessesTable } from "../shared/table-utils.js";
import { populateProcessDropdown, selectedProcessList } from "../shared/process-utils.js";
import { getCookie, getToken } from "../shared/utils.js";

const csrftoken = getCookie('csrftoken');
const token = getToken();

// API base - adjust if needed (or set window.API_BASE before loading this file)
const API_BASE = window.API_BASE || 'http://127.0.0.1:8000';
const UNIFIED_UPDATE_URL = `${API_BASE}/batch-encoder/unified_sensor_update/`;
const BATCH_DETAIL = (batchLocation, batchID) => `${API_BASE}/batch-encoder/batch-detail/${encodeURIComponent(batchLocation)}/${encodeURIComponent(batchID)}/`;
const TASK_STATUS = (taskId) => `${API_BASE}/api/task-status/${encodeURIComponent(taskId)}/`;

// Fields available for update
const fieldsToUpdate = [
  'batch_label', 'batch_description', 'wafer_label',
  'wafer_description', 'wafer_design_id', 'sensor_label', 'sensor_description'
];

let deleteList = [];
let processes = [];

// --- UI helpers
function showLoader(){ const loader = document.getElementById('loader'); if(loader) loader.style.display='block'; }
function hideLoader(){ const loader = document.getElementById('loader'); if(loader) loader.style.display='none'; }
function showOverlay(){ const overlay = document.getElementById('overlay'); if(overlay) overlay.style.display='block'; }
function hideOverlay(){ const overlay = document.getElementById('overlay'); if(overlay) overlay.style.display='none'; }

async function safeJsonResponse(resp){
  const txt = await resp.text();
  try { return JSON.parse(txt); } catch(e){ return { text: txt }; }
}

// --- Retrieve batch detail (used by the batch form) ---
async function retrieveData(event){
  if(event) event.preventDefault();
  showLoader();

  const batchLocationEl = document.getElementById('batch_location');
  const batchIdEl = document.getElementById('batch_id');
  if(!batchLocationEl || !batchIdEl){ console.error('Missing batch inputs'); hideLoader(); return; }

  const batchLocation = batchLocationEl.value.trim();
  const batchID = batchIdEl.value.trim();
  if(!batchLocation || !batchID){ alert('Please enter batch location and ID'); hideLoader(); return; }

  try {
    const response = await fetch(BATCH_DETAIL(batchLocation, batchID), {
      method: 'GET',
      headers: {
        'Authorization': token ? `Token ${token}` : '',
        'X-CSRFToken': csrftoken
      }
    });

    if(!response.ok){
      const body = await safeJsonResponse(response);
      console.error('Batch detail error', response.status, body);
      alert('Error retrieving batch data. See console for details.');
      return;
    }

    const data = await response.json();
    console.log('Batch detail:', data);

    document.getElementById('batchLocation').innerText = `Batch Location: ${data.batch_location ?? ''}`;
    document.getElementById('batchId').innerText = `Batch ID: ${data.batch_id ?? ''}`;
    document.getElementById('waferIds').innerText = `Total Wafers: ${data.total_wafers ?? ''}`;
    document.getElementById('sensorIds').innerText = `Total Sensors: ${data.total_sensors ?? ''}`;

    // Render the wafer/processes info via your shared util
    renderWaferProcessesTable(data.sensor_processes ?? [], deleteList);

    const electrodeDetails = document.getElementById('electrodeDetails');
    if(electrodeDetails) electrodeDetails.style.display = 'block';

    createUpdateTable([], fieldsToUpdate);

  } catch(err){
    console.error('Error retrieving batch data', err);
    alert('Error retrieving batch details.');
  } finally {
    hideLoader();
  }
}

// --- Processes ---
async function retrieveProcesses(){
  try {
    processes = await fetcProcesses();
    populateProcessDropdown(processes);
  } catch(err) {
    console.error('Error fetching processes', err);
  }
}

// --- Task polling (optional) ---
async function pollTaskStatus(taskId, onUpdate = null, opts = {}){
  if(!taskId) return null;
  const maxAttempts = opts.maxAttempts || 18;
  let attempt = 0;
  let delay = 1000;

  while(attempt < maxAttempts){
    attempt++;
    try {
      const resp = await fetch(TASK_STATUS(taskId), {
        method: 'GET',
        headers: {
          'Authorization': token ? `Token ${token}` : '',
          'X-CSRFToken': csrftoken
        }
      });
      if(resp.status === 404){
        // endpoint not implemented -> bail
        return null;
      }
      if(resp.ok){
        const json = await resp.json();
        if(onUpdate) onUpdate(json);
        if(json.state === 'SUCCESS' || json.state === 'FAILURE') return json;
      }
    } catch(e){ console.warn('poll error', e); }
    await new Promise(r => setTimeout(r, delay));
    delay = Math.min(Math.round(delay * 1.5), 8000);
  }
  return null;
}

// --- Build update payload helpers ---
function gatherUpdateData(){
  const updateData = {};
  fieldsToUpdate.forEach(field => {
    const checkbox = document.getElementById(`update_${field}`);
    const newValueEl = document.getElementById(`new_${field}`);
    const newValue = newValueEl ? newValueEl.value.trim() : '';
    if (checkbox && checkbox.checked && newValue) updateData[field] = newValue;
  });
  return updateData;
}

// --- Batch update (calls unified endpoint with selection_strategy='batch') ---
async function updateElectrodeBatch(){
  showLoader(); showOverlay();
  try {
    const updateData = gatherUpdateData();
    const payload = {
      selection_strategy: 'batch',
      batch_location: document.getElementById('batch_location')?.value?.trim(),
      batch_id: (() => {
        const v = document.getElementById('batch_id')?.value?.trim();
        return v && !isNaN(Number(v)) ? Number(v) : v;
      })(),
      wafer_ids: document.getElementById('wafer_ids')?.value || '',
      sensor_ids: document.getElementById('sensor_ids')?.value || '',
      updates: updateData,
      new_process_data: selectedProcessList || [],
      delete_list: deleteList
    };

    const resp = await fetch(UNIFIED_UPDATE_URL, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': token ? `Token ${token}` : '',
        'X-CSRFToken': csrftoken
      },
      body: JSON.stringify(payload)
    });

    if(!resp.ok){
      const body = await safeJsonResponse(resp);
      console.error('Batch update error', resp.status, body);
      alert(`Update failed: ${body.error ?? resp.status}`);
      return;
    }

    const json = await resp.json();
    console.log('Batch update response', json);
    const taskId = json.task_id;
    if(taskId){
      const statusResult = await pollTaskStatus(taskId, u => console.debug('task update', u), { maxAttempts: 25 });
      if(statusResult && statusResult.state === 'SUCCESS') alert('Batch update completed successfully.');
      else alert(`Update started (task id: ${taskId}).`);
    } else {
      alert('Update completed (no task id returned).');
    }

    deleteList = [];
    window.location.reload();

  } catch(err){
    console.error('Error updating (batch)', err);
    alert('Error updating sensors (batch).');
  } finally {
    hideLoader(); hideOverlay();
  }
}

// --- Validate input and render validated sensors ---
// This renders checkboxes with class .validated-sensor-checkbox and data-uid attributes.
// collectValidatedUniqueIdentifiers() below reads the list produced here.
function renderValidatedSensors(uids){
  const container = document.getElementById('validated-sensors-container');
  if(!container) return;

  container.innerHTML = ''; // clear previous
  const ul = document.createElement('ul');

  // Select-all control
  const selectAllId = 'select_all_validated';
  const selectAllLi = document.createElement('li');
  selectAllLi.style.marginBottom = '8px';
  selectAllLi.innerHTML = `<label><input id="${selectAllId}" type="checkbox"> Select / Deselect All</label>`;
  ul.appendChild(selectAllLi);

  uids.forEach((uid, idx) => {
    const safeId = `validated_cb_${idx}`;
    const li = document.createElement('li');
    li.innerHTML = `
      <input type="checkbox" class="validated-sensor-checkbox" id="${safeId}" value="${uid}">
      <label for="${safeId}">${uid}</label>
      <button class="remove-uid" data-uid="${uid}" title="Remove">✕</button>
    `;
    ul.appendChild(li);
  });

  container.appendChild(ul);

  // Show containers
  document.getElementById('validSensors').style.display = 'block';
  document.getElementById('updateFields').style.display = 'block';

  // wire remove buttons
  container.querySelectorAll('.remove-uid').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const removeUid = btn.getAttribute('data-uid');
      // remove corresponding li
      btn.closest('li')?.remove();
    });
  });

  // wire select-all
  const selectAllInput = document.getElementById(selectAllId);
  if(selectAllInput){
    selectAllInput.addEventListener('change', (ev) => {
      const checked = ev.target.checked;
      container.querySelectorAll('input.validated-sensor-checkbox').forEach(cb => cb.checked = checked);
    });
  }

  // Create the update table (use your shared helper)
  try { createUpdateTable([], fieldsToUpdate); } catch(e) { console.warn('createUpdateTable not available', e); }
}

// Parse and validate the text the user entered into the u_id input
function parseUidsFromInput(rawText){
  if(!rawText) return [];
  // split by commas, whitespace, or newlines
  const parts = rawText.split(/[\s,]+/).map(s => s.trim()).filter(Boolean);
  // optional: simple sanity filter (alphanumeric, dash, underscrore)
  const re = /^[A-Za-z0-9\-_]+$/;
  const valid = parts.filter(p => re.test(p));
  // If none matched strict regex, fallback to original parts (lenient)
  return valid.length ? valid : parts;
}

async function validateSensorsFromInput(e){
  if(e) e.preventDefault();
  const inputEl = document.getElementById('u_id');
  if(!inputEl) return;
  const raw = inputEl.value.trim();
  if(!raw){ alert('Please enter one or more sensor unique IDs'); return; }

  const uids = parseUidsFromInput(raw);
  if(uids.length === 0){ alert('No valid sensor identifiers parsed. Check format.'); return; }

  // If you have server-side validation (recommended), call an endpoint to check these exist.
  // For now we render them locally as "validated". You can add a fetch to /api/validate-uids if desired.
  renderValidatedSensors(uids);
}

// --- collectValidatedUniqueIdentifiers ---
function collectValidatedUniqueIdentifiers(){
  const container = document.getElementById('validated-sensors-container');
  if(!container) return [];

  // 1) checked checkboxes (our renderer)
  const checkedBoxes = container.querySelectorAll('input.validated-sensor-checkbox[type="checkbox"]:checked');
  if(checkedBoxes && checkedBoxes.length > 0) {
    return Array.from(checkedBoxes).map(cb => cb.value).filter(Boolean);
  }

  // 2) any listed items (checkbox unchecked) — we still may want to update them: use all checkboxes
  const allBoxes = container.querySelectorAll('input.validated-sensor-checkbox[type="checkbox"]');
  if(allBoxes && allBoxes.length > 0) {
    return Array.from(allBoxes).map(cb => cb.value).filter(Boolean);
  }

  // 3) elements with data-uid attribute
  const dataEls = container.querySelectorAll('[data-uid]');
  if(dataEls && dataEls.length > 0) return Array.from(dataEls).map(el => el.getAttribute('data-uid')).filter(Boolean);

  // 4) fallback: parse u_id input field as CSV
  const singleInput = document.getElementById('u_id');
  if(singleInput && singleInput.value.trim()){
    return singleInput.value.split(/[\s,]+/).map(s => s.trim()).filter(Boolean);
  }

  return [];
}

// --- Individual update ---
async function updateSensorsIndividual(){
  showLoader(); showOverlay();
  try {
    const uIds = collectValidatedUniqueIdentifiers();
    if(!uIds || uIds.length === 0){
      alert('No validated sensors found. Validate sensors first or use the batch flow.');
      return;
    }

    const updateData = gatherUpdateData();
    const payload = {
      selection_strategy: 'individual',
      u_ids: uIds,
      updates: updateData,
      new_process_data: selectedProcessList || [],
      delete_list: deleteList
    };

    const resp = await fetch(UNIFIED_UPDATE_URL, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': token ? `Token ${token}` : '',
        'X-CSRFToken': csrftoken
      },
      body: JSON.stringify(payload)
    });

    if(!resp.ok){
      const body = await safeJsonResponse(resp);
      console.error('Individual update failed', resp.status, body);
      alert(`Update failed: ${body.error ?? resp.status}`);
      return;
    }

    const json = await resp.json();
    console.log('Individual update response', json);
    const taskId = json.task_id;
    if(taskId){
      const statusResult = await pollTaskStatus(taskId, u => console.debug('task', u), { maxAttempts: 25 });
      if(statusResult && statusResult.state === 'SUCCESS') alert('Individual update completed.');
      else alert(`Update started (task id: ${taskId}).`);
    } else {
      alert('Update completed (no task id returned).');
    }

    deleteList = [];
    window.location.reload();

  } catch(err){
    console.error('Error updating (individual)', err);
    alert('Error updating sensors (individual).');
  } finally {
    hideLoader(); hideOverlay();
  }
}

// --- DOM wiring ---
document.addEventListener('DOMContentLoaded', () => {
  // Buttons/Forms
  const sensorForm = document.getElementById('sensorForm');
  const validateBtn = document.getElementById('validate'); // submit on form
  const retrieveBatchBtn = document.getElementById('retrieveBatchBtn');
  const retrieveBtnLegacy = document.getElementById('retrieveButton'); // some older pages use this id
  const updateBtn = document.getElementById('updateButton');
  const showBatchFormBtn = document.getElementById('showBatchFormBtn');
  const batchForm = document.getElementById('batchForm');
  const resetBtn = document.getElementById('resetBtn');

  if(sensorForm){
    sensorForm.addEventListener('submit', (e) => {
      e.preventDefault(); validateSensorsFromInput(e);
    });
  }

  if(retrieveBatchBtn) retrieveBatchBtn.addEventListener('click', retrieveData);
  if(retrieveBtnLegacy) retrieveBtnLegacy.addEventListener('click', retrieveData);

  if(batchForm) batchForm.addEventListener('submit', retrieveData);

  if(showBatchFormBtn){
    showBatchFormBtn.addEventListener('click', () => {
      const c = document.getElementById('batchFormContainer');
      c.style.display = (c.style.display === 'none' || c.style.display === '') ? 'block' : 'none';
    });
  }

  if(updateBtn){
    updateBtn.addEventListener('click', (e) => {
      e.preventDefault();
      // automatic strategy selection: prefer individual if any validated sensors exist
      const uids = collectValidatedUniqueIdentifiers();
      if(uids && uids.length > 0) {
        updateSensorsIndividual();
      } else {
        updateElectrodeBatch();
      }
    });
  }

  if(resetBtn){
    resetBtn.addEventListener('click', () => {
      // clear validated sensors and hide UI
      const container = document.getElementById('validated-sensors-container');
      if(container) container.innerHTML = '';
      document.getElementById('validSensors').style.display = 'none';
      document.getElementById('updateFields').style.display = 'none';
      document.getElementById('u_id').value = '';
    });
  }

  // hide loader initial
  hideLoader();

  // pre-fetch processes for dropdowns
  retrieveProcesses();
});

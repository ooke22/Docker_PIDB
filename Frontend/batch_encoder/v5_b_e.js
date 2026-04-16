import { processIdAPI, v3BatchEncoderAPI } from "../shared/url.js";
import { getCookie, getToken } from "../shared/utils.js";
import notifications from "../shared/notifications.js";

const csrftoken = getCookie('csrftoken');
const token = getToken();
let allProcesses = {};

// Make taskProgressBars globally accessible for the global WebSocket handler
window.taskProgressBars = {}; // { task_id: {progressBarEl, progressTextEl} }

// ------------------ Legacy Toast Helper (kept for backwards compatibility) ------------------
//export function showToast(message, type='info', duration=4000) {
    // Redirect to new notification system
//    notifications.show(message, type, { duration });
//}

// ------------------ Fetch Processes ------------------
async function retrieveProcesses() {
    try {
        const response = await fetch(processIdAPI, {
            method: 'GET',
            headers: {'Authorization': `Token ${token}`, 'X-CSRFToken': csrftoken}
        });
        const processes = await response.json();
        processes.forEach(p => { allProcesses[p.process_id] = p.description; });
        populateProcessDropdown(processes);
    } catch (err) {
        console.error('Error fetching processes:', err);
        notifications.error('Failed to fetch processes. Please refresh the page.');
    }
}

function populateProcessDropdown(processes) {
    const dropdown = document.getElementById('wafer_process_dropdown');
    dropdown.innerHTML = '';
    processes.forEach(proc => {
        const option = document.createElement('option');
        option.value = proc.process_id;
        option.textContent = `${proc.process_id} - ${proc.description}`;
        dropdown.appendChild(option);
    });
    dropdown.addEventListener('change', handleProcessSelection);
}

// ------------------ Process Selection ------------------
function handleProcessSelection() {
    const selectedOptions = Array.from(document.getElementById('wafer_process_dropdown').selectedOptions);
    const timestampWrapper = document.getElementById('timestampContainerWrapper');
    const selectedIds = selectedOptions.map(o => o.value);

    timestampWrapper.querySelectorAll('.timestamp-container').forEach(container => {
        const pid = container.querySelector('.new-timestamp').dataset.processId;
        if (!selectedIds.includes(pid)) container.remove();
    });

    selectedIds.forEach(pid => {
        if (!timestampWrapper.querySelector(`[data-process-id="${pid}"]`)) {
            const div = document.createElement('div');
            div.className = 'timestamp-container';
            const label = document.createElement('label');
            label.textContent = `Timestamp for Process ID ${pid}:`;
            const input = document.createElement('input');
            input.type = 'datetime-local';
            input.className = 'new-timestamp';
            input.dataset.processId = pid;
            div.append(label, input);
            timestampWrapper.appendChild(div);
        }
    });
}

// ------------------ Form Validation ------------------
function validateBatchForm(batchData) {
    const errors = [];
    
    if (!batchData.batch_location.trim()) errors.push("Batch location is required");
    if (!batchData.batch_id.trim()) errors.push("Batch ID is required");
    if (!batchData.total_wafers.trim() || isNaN(batchData.total_wafers)) errors.push("Valid total wafers number is required");
    if (!batchData.total_sensors.trim() || isNaN(batchData.total_sensors)) errors.push("Valid total sensors number is required");
    
    return errors;
}

// ------------------ Post Batch ------------------
export async function postBatchData() {
    const loader = document.getElementById('loader'); 
    loader.style.display='block';
    
    const batchData = {
        batch_location: document.getElementById('batch_location').value,
        batch_id: document.getElementById('batch_id').value,
        total_wafers: document.getElementById('total_wafers').value,
        total_sensors: document.getElementById('total_sensors').value,
        batch_label: document.getElementById('batch_label').value,
        batch_description: document.getElementById('batch_description').value,
        wafer_label: document.getElementById('wafer_label').value,
        wafer_description: document.getElementById('wafer_description').value,
        wafer_designID: document.getElementById('wafer_design_id').value,
        sensor_description: document.getElementById('sensor_description').value,
    };

    // Validate form
    const validationErrors = validateBatchForm(batchData);
    if (validationErrors.length > 0) {
        notifications.error(validationErrors.join(', '), {
            title: "Form Validation Error"
        });
        loader.style.display='none';
        return;
    }

    // Process IDs & timestamps
    const processes = Array.from(document.querySelectorAll('.new-timestamp')).map(input => ({
        process_id: input.dataset.processId,
        description: allProcesses[input.dataset.processId] || '',
        timestamp: new Date(input.value).toISOString()
    }));
    batchData.sensor_processes = processes;
    console.log('Batch Data', JSON.stringify(batchData));
    try {
        const response = await fetch(v3BatchEncoderAPI, {
            method:'POST',
            headers: {'Content-Type':'application/json','Authorization':`Token ${token}`,'X-CSRFToken':csrftoken},
            body: JSON.stringify(batchData)
        });
        const data = await response.json();
        if(!response.ok) throw new Error(data.message || 'Error creating batch');

        const taskId = data.task_id;
        
        // Add task progress bar (keep this for visual feedback on current page)
        createProgressBar(taskId);
        
        // Clear the error output on success
        document.getElementById('error-output').textContent = 'Batch creation initiated successfully';
        document.getElementById('error-output').style.color = 'green';

    } catch(err) {
        console.error('Batch creation error:', err);
        notifications.error(`Failed to create batch: ${err.message}`, {
            title: "Batch Creation Error"
        });
        document.getElementById('error-output').textContent = err.message;
        document.getElementById('error-output').style.color = 'red';
    } finally {
        loader.style.display='none';
    }
}

// ------------------ Progress Bar Creation ------------------
function createProgressBar(taskId) {
    const container = document.getElementById('tasksContainer');
    const div = document.createElement('div');
    div.id = `task-${taskId}`;
    div.innerHTML = `
        <label>Task ${taskId} Progress:</label>
        <progress value="0" max="100"></progress>
        <span>0%</span>
    `;
    container.appendChild(div);
    
    // Store in global object so global WebSocket can access it
    window.taskProgressBars[taskId] = {
        progressBarEl: div.querySelector('progress'), 
        progressTextEl: div.querySelector('span')
    };
}

// ------------------ Init ------------------
window.addEventListener('DOMContentLoaded', () => {
    retrieveProcesses();
    document.getElementById('postBatchData').addEventListener('click', postBatchData);
    document.getElementById('loader').style.display = 'none';
});
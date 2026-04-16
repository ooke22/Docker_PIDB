import { processIdAPI, v3BatchEncoderAPI } from "../shared/url.js";
import { getCookie, getToken } from "../shared/utils.js";

const csrftoken = getCookie('csrftoken');
const token = getToken();
let allProcesses = {};
const taskProgressBars = {}; // { task_id: {progressBarEl, progressTextEl} }

// ------------------ Toast Helper ------------------
export function showToast(message, type='info', duration=4000) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span>${message}</span><span class="close-btn">&times;</span>`;
    container.appendChild(toast);

    toast.querySelector('.close-btn').addEventListener('click', () => toast.remove());
    setTimeout(() => toast.remove(), duration);
}

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
        showToast('Error fetching processes', 'error');
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

// ------------------ Post Batch ------------------
export async function postBatchData() {
    const loader = document.getElementById('loader'); loader.style.display='block';
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

    // Process IDs & timestamps
    const processes = Array.from(document.querySelectorAll('.new-timestamp')).map(input => ({
        process_id: input.dataset.processId,
        description: allProcesses[input.dataset.processId] || '',
        timestamp: new Date(input.value).toISOString()
    }));
    batchData.sensor_processes = processes;

    try {
        const response = await fetch(v3BatchEncoderAPI, {
            method:'POST',
            headers: {'Content-Type':'application/json','Authorization':`Token ${token}`,'X-CSRFToken':csrftoken},
            body: JSON.stringify(batchData)
        });
        const data = await response.json();
        if(!response.ok) throw new Error(data.message || 'Error creating batch');

        const taskId = data.task_id;
        showToast(`Batch task ${taskId} started`, 'info');

        // Add task progress bar
        const container = document.getElementById('tasksContainer');
        const div = document.createElement('div');
        div.id = `task-${taskId}`;
        div.innerHTML = `<label>Task ${taskId} Progress:</label>
                        <progress value="0" max="100"></progress><span>0%</span>`;
        container.appendChild(div);
        taskProgressBars[taskId] = {progressBarEl: div.querySelector('progress'), progressTextEl: div.querySelector('span')};

    } catch(err) {
        console.error(err);
        showToast(`Error: ${err.message}`, 'error');
        document.getElementById('error-output').textContent = err.message;
    } finally {
        loader.style.display='none';
    }
}

// ------------------ Register Task-Specific Progress WebSocket ------------------
export function registerProgressWS() {
    const backendHost = window.location.hostname;
    const socket = new WebSocket(`ws://${backendHost}:8000/ws/global-tasks/`);
    socket.onmessage = (event) => {
        const {task_id, progress, state, message} = JSON.parse(event.data);
        const task = taskProgressBars[task_id];
        if(task) {
            if(progress !== undefined) { task.progressBarEl.value = progress; task.progressTextEl.textContent = `${progress}%`; }
        }
        if(state==='SUCCESS') showToast(`Task ${task_id} completed!`, 'success');
        else if(state==='FAILURE') showToast(`Task ${task_id} failed: ${message}`, 'error');
        //else if(progress!==undefined) showToast(`Task ${task_id}: ${progress}%`, 'info');
    };
}

// ------------------ Init ------------------
window.addEventListener('DOMContentLoaded', () => {
    retrieveProcesses();
    registerProgressWS();
    document.getElementById('postBatchData').addEventListener('click', postBatchData);
    
    document.getElementById('loader').style.display = 'none';
});

import { formatDate } from "./utils.js";

export let selectedProcessList = [];

/**
 * Renders the list of available processes in a dropdown-style container.
 * Each process is clickable, triggering a selection handler.
 */
export function populateProcessDropdown(processes) {
    const processList = document.getElementById('processList');
    processList.innerHTML = '';

    processes.forEach(process => {
        const processContainer = document.createElement('div');
        processContainer.className = 'process-item';
        processContainer.dataset.processId = process.process_id;

        const label = document.createElement('span');
        label.textContent = `${process.process_id} - ${process.description}`;

        processContainer.appendChild(label);
        processList.appendChild(processContainer);

        processContainer.addEventListener('click', () => {
            highlightSelectedProcess(processContainer);
            handleProcessSelection(process.process_id, processes);
        });
    });
}

/**
 * Visually highlights the selected process item from the process list.
 */
export function highlightSelectedProcess(container) {
    document.querySelectorAll('#processList .process-item').forEach(item =>
        item.classList.remove('highlighted')
    );
    container.classList.add('highlighted');
}

/**
 * Displays a datetime input and an "Add" button for the selected process.
 * The timestamp and process ID are passed to the process table when "Add" is clicked.
 */
export function handleProcessSelection(processId, processes) {
    const selectedProcessContainer = document.getElementById('selectedProcessContainer');
    selectedProcessContainer.innerHTML = '';

    const process = processes.find(p => p.process_id === processId);
    const description = process?.description || 'N/A';

    const container = document.createElement('div');
    container.className = 'selected-process';

    const input = document.createElement('input');
    input.type = 'datetime-local';
    input.className = 'new-timestamp';
    input.dataset.processId = processId;

    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = 'Add';
    button.onclick = () => addProcesstoTable(processId, description, input.value);

    container.appendChild(input);
    container.appendChild(button);
    selectedProcessContainer.appendChild(container);
}

/**
 * Adds a selected process and timestamp to the "Processes to be Added" table.
 * Prevents duplicates and stores the result in the shared `selectedProcessList`.
 */
export function addProcesstoTable(processId, description, timestamp) {
    if (!timestamp) {
        alert('Please select a timestamp.');
        return;
    }

    const body = document.getElementById('addedProcessTableBody');
    if ([...body.rows].some(row => row.dataset.processId === processId)) {
        alert('Process already added.');
        return;
    }

    const row = body.insertRow();
    row.dataset.processId = processId;

    const formatted = formatDate(new Date(timestamp));
    row.innerHTML = `
        <td style="border: 1px solid #000;">${processId}</td>
        <td style="border: 1px solid #000;">${description}</td>
        <td style="border: 1px solid #000;">${formatted}</td>
        <td style="border: 1px solid #000;">
            <button type="button" class="remove">Remove</button>
        </td>
    `;

    row.querySelector('.remove').onclick = () => {
        body.removeChild(row);
        const index = selectedProcessList.findIndex(p => p.process_id === processId);
        if (index !== -1) selectedProcessList.splice(index, 1);
    };

    selectedProcessList.push({ process_id: processId, description: description, timestamp: new Date(timestamp).toISOString() });
}
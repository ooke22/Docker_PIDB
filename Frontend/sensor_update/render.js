// render.js

// Imports from utility and shared state modules
import { formatDate, createInputListener } from './utils.js';

export let labelOptions = [];
export let selectedProcessList = [];

/**
 * Renders the validated sensor IDs as a table and shows the sensor section.
 * Also triggers the rendering of associated process details.
 */

export function renderResults(sensors) {
    const container = document.getElementById('validated-sensors-container');
    container.innerHTML = '';
    container.style.maxHeight = '400px';
    container.style.overflowY = 'auto';

    if (!sensors.length) {
        container.innerHTML = '<p>No validated sensors to display.</p>';
        return;
    }

    const table = document.createElement('table');
    table.style.width = '100%';

    let row;
    sensors.forEach((sensor, index) => {
        if (index % 7 === 0) {
            row = document.createElement('tr');
            table.appendChild(row);
        }

        const cell = document.createElement('td');
        cell.textContent = sensor.unique_identifier;
        cell.style.border = '1px solid #ccc';
        row.appendChild(cell);
    });

    container.appendChild(table);
    document.getElementById('validSensors').style.display = 'block';

    populateProcessDetails(sensors); // Render process details grouped by batch
}

/**
 * Dynamically builds the update table with fields for "label" and "sensor_description".
 * Uses `createInputListener` to auto-check the box when a value is entered.
 */
export function createUpdateTable(labelOptions) {
    const table = document.getElementById('updateTable');
    const fieldsToUpdate = ['label', 'sensor_description'];
    while (table.rows.length > 1) table.deleteRow(1); // Clear old rows

    fieldsToUpdate.forEach((field, index) => {
        const row = table.insertRow(index + 1);
        const fieldCell = row.insertCell(0);
        fieldCell.textContent = field.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());

        const checkboxCell = row.insertCell(1);
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.id = `update_${field}`;
        checkboxCell.appendChild(checkbox);

        const valueCell = row.insertCell(2);

        if (field === 'label') {
            const select = document.createElement('select');
            select.id = 'new_label';

            if (labelOptions.length > 0) {
                select.innerHTML = `<option value="">Select...</option>` +
                    labelOptions.map(label =>
                        `<option value="${label.id || label.name}">${label.name || label}</option>`
                    ).join('');
            } else {
                select.innerHTML = `<option>No labels available</option>`;
            }

            select.addEventListener('change', createInputListener(checkbox, select));
            valueCell.appendChild(select);
        }

        if (field === 'sensor_description') {
            const input = document.createElement('input');
            input.type = 'text';
            input.id = 'new_sensor_description';
            input.placeholder = 'Enter description...';
            input.addEventListener('input', createInputListener(checkbox, input));
            valueCell.appendChild(input);
        }
    });
}

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

    selectedProcessList.push({ process_id: processId, timestamp: new Date(timestamp).toISOString() });
}

/**
 * Groups validated sensors by batch and renders each batch's process history.
 * Each row includes a "Remove"/"Undo" button that updates the `deleteList`.
 */
export function populateProcessDetails(sensors) {
    const tbody = document.getElementById('processTableBody');
    tbody.innerHTML = '';

    // Group sensors by batch ID (first 4 characters)
    const batchGroups = {};
    sensors.forEach(sensor => {
        const batch = sensor.unique_identifier.slice(0, 4);
        batchGroups[batch] = batchGroups[batch] || [];
        batchGroups[batch].push(sensor);
    });

    Object.entries(batchGroups).forEach(([batch, group]) => {
        const seen = new Set();
        const uniqueProcesses = [];

        // Collect distinct processes for each batch
        group.forEach(sensor => {
            (sensor.sensor_processes || []).forEach(proc => {
                const key = `${proc.process_id}-${proc.timestamp}`;
                if (!seen.has(key)) {
                    seen.add(key);
                    uniqueProcesses.push(proc);
                }
            });
        });

        // Render batch header
        const headerRow = document.createElement('tr');
        const headerCell = document.createElement('td');
        headerCell.colSpan = 4;
        headerCell.textContent = `Batch: ${batch}`;
        headerCell.style.backgroundColor = '#ccdae3';
        headerRow.appendChild(headerCell);
        tbody.appendChild(headerRow);

        // Render each process in the batch
        uniqueProcesses.forEach(proc => {
            const row = document.createElement('tr');

            const id = document.createElement('td');
            id.textContent = proc.process_id;
            id.style.border = '1px solid #000';

            const desc = document.createElement('td');
            desc.textContent = proc.description;
            desc.style.border = '1px solid #000';

            const date = document.createElement('td');
            date.textContent = formatDate(proc.timestamp);
            date.style.border = '1px solid #000';

            const remove = document.createElement('td');
            remove.style.border = '1px solid #000';

            const btn = document.createElement('button');
            btn.textContent = 'Remove';
            btn.style.cssText = 'background-color:#f44336;color:#fff;border:none;padding:5px 10px;cursor:pointer';

            btn.addEventListener('click', () => {
                const key = {
                    process_id: proc.process_id,
                    timestamp: new Date(proc.timestamp).toISOString()
                };
                const index = deleteList.findIndex(
                    item => item.process_id === key.process_id && item.timestamp === key.timestamp
                );

                if (index === -1) {
                    deleteList.push(key);
                    row.style.backgroundColor = '#ffcccc';
                    btn.textContent = 'Undo';
                    btn.style.backgroundColor = '#4CAF50';
                } else {
                    deleteList.splice(index, 1);
                    row.style.backgroundColor = '';
                    btn.textContent = 'Remove';
                    btn.style.backgroundColor = '#f44336';
                }
            });

            remove.appendChild(btn);
            row.append(id, desc, date, remove);
            tbody.appendChild(row);
        });
    });
}

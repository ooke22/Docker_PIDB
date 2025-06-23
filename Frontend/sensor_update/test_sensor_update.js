// main.js
import {
    normalizeSensorId,
    createInputListener,
    formatDate,
    saveSensorCache,
    loadSensorCache,
    mergeValidatedSensors,
    mergeOriginalSensorIds
} from './utils.js';

let labelOptions = [];
let allValidatedSensors = [];
let allOriginalSensorIds = [];
let deleteList = [];
let processes = [];
let selectedProcessList = [];

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

function populateProcessDropdown(processes) {
    const processList = document.getElementById('processList');
    processList.innerHTML = '';

    processes.forEach(process => {
        const processContainer = document.createElement('div');
        processContainer.className = 'process-item';
        processContainer.setAttribute('data-process-id', process.process_id);

        const processLabel = document.createElement('span');
        processLabel.textContent = `${process.process_id} - ${process.description}`;

        processContainer.appendChild(processLabel);
        processList.appendChild(processContainer);

        // Click even listener to highlight selected process and handle selection
        processContainer.addEventListener('click', () => {
            highlightSelectedProcess(processContainer);
            handleProcessSelection(process.process_id);
        });
    });
}

function highlightSelectedProcess(selectedProcessContainer) {
    // Remove highlight from previously selected process
    document.querySelectorAll('#processList .process-item').forEach(item => {
        item.classList.remove('highlighted');
    });
    // Add highlight to currently selected process
    selectedProcessContainer.classList.add('highlighted');
}

function handleProcessSelection(processId) {
    const selectedProcessContainer = document.getElementById('selectedProcessContainer');
    selectedProcessContainer.innerHTML = '';

    const selectedProcess = processes.find(item => item.process_id === processId);
    const processDescription = selectedProcess ? selectedProcess.description : "N/A";

    const processContainer = document.createElement('div');
    processContainer.className = 'selected-process';
    processContainer.setAttribute('data-process-id', processId);

    const timestampInput = document.createElement('input');
    timestampInput.type = 'datetime-local';
    timestampInput.className = 'new-timestamp';
    timestampInput.setAttribute('data-process-id', processId);
    processContainer.appendChild(timestampInput);

    const addButton = document.createElement('button');
    addButton.type = 'button';
    addButton.textContent = 'Add';
    addButton.onclick = () => addProcesstoTable(processId, processDescription, timestampInput.value);
    processContainer.appendChild(addButton);

    selectedProcessContainer.appendChild(processContainer);
}

function addProcesstoTable(processId, processDescription, timestamp) {
    if (!timestamp) {
        alert("Please select a timestamp before adding.");
        return;
    }

    // Check if process is already added
    const addedProcessTableBody = document.getElementById('addedProcessTableBody');
    if ([...addedProcessTableBody.rows].some(row => row.getAttribute('data-process-id') === processId)) {
        alert('Process already added.');
        return;
    }

    const row = addedProcessTableBody.insertRow();
    row.setAttribute('data-process-id', processId);

    const processIDcell = row.insertCell(0);
    const descriptionCell = row.insertCell(1);
    const timeStampcell = row.insertCell(2);
    const removeButtonCell = row.insertCell(3);

    processIDcell.textContent = processId;
    descriptionCell.textContent = processDescription;
    //const date = new Date(timestamp);
    //const formattedDate = `${String(date.getDate()).padStart(2, '0')}/${String(date.getMonth() + 1).padStart(2, '0')}/${String(date.getFullYear()).slice(-2)}, ${date.toLocaleTimeString()}`;
    const formattedDate = formatDate(timestamp);
    timeStampcell.textContent = formattedDate;
    processIDcell.style.border = '1px solid #000';
    descriptionCell.style.border = '1px solid #000';
    timeStampcell.style.border = '1px solid #000';
    removeButtonCell.style.border = '1px solid #000';

    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.textContent = 'Remove';
    removeBtn.onclick = () => {
        // Remove row from the table
        addedProcessTableBody.removeChild(row);

        // Remove the proceess from the selected process list
        const processIndex = selectedProcessList.findIndex(item => item.process_id === processId);
        if (processIndex !== -1) {
            selectedProcessList.splice(processIndex, 1)
        }
    };

    removeButtonCell.appendChild(removeBtn);

    // Add the process to the selected process list
    selectedProcessList.push({ process_id: processId, timestamp: new Date(timestamp).toISOString() });
    console.log('Selected process list:', selectedProcessList);
}


function loadCachedSensors() {
    const cache = loadSensorCache();
    if (cache && cache.validated.length > 0) {
        allValidatedSensors = cache.validated;
        allOriginalSensorIds = cache.original;
        renderResults(allValidatedSensors);
        createUpdateTable();
        document.getElementById('updateFields').style.display = 'block';
    }
}

function saveCurrentSensorStateToLocalStorage() {
    saveSensorCache(allValidatedSensors, allOriginalSensorIds);
}

async function validateSensors() {
    const loader = document.getElementById('loader');
    loader.style.display = 'block';

    let sensorInput = document.getElementById('u_id');
    let rawInput = sensorInput.value;

    let ids = rawInput.split(',').map(id => id.trim()).filter(Boolean);

    let failedNormalization = [];
    let normalizedMap = {};

    const normalizedIds = ids.map(id => {
        const norm = normalizeSensorId(id);
        if (!norm) {
            failedNormalization.push(id);
        } else {
            normalizedMap[norm] = id;
        }
        return norm;
    }).filter(Boolean);

    if (!normalizedIds.length) {
        alert("No valid sensor IDs provided.");
        loader.style.display = 'none';
        return;
    }

    try {
        console.log('Payload:', normalizedIds);
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
        createUpdateTable();
        document.getElementById('updateFields').style.display = 'block';

        const messages = [];
        if (failedNormalization.length) messages.push(`Invalid syntax: ${failedNormalization.join(', ')}`);
        if (notFound.length) messages.push(`Not found: ${notFound.join(', ')}`);
        if (alreadyAdded.length) messages.push(`Already added: ${alreadyAdded.join(', ')}`);
        if (messages.length) alert("Some sensors were not added:\n\n" + messages.join('\n'));

        //saveCurrentSensorStateToLocalStorage();
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

function createUpdateTable() {
    const table = document.getElementById('updateTable');
    const fieldsToUpdate = ['label', 'sensor_description'];
    while (table.rows.length > 1) table.deleteRow(1);

    fieldsToUpdate.forEach((field, index) => {
        const row = table.insertRow(index + 1);
        const fieldCell = row.insertCell(0);
        fieldCell.textContent = field.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());

        const checkboxCell = row.insertCell(1);
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.id = `update_${field}`;
        checkbox.name = `update_${field}`;
        checkboxCell.appendChild(checkbox);

        const valueCell = row.insertCell(2);
        if (field === 'label') {
            const select = document.createElement('select');
            select.id = 'new_label';
            select.name = 'new_label';

            if (labelOptions.length > 0) {
                const defaultOpt = document.createElement('option');
                defaultOpt.value = '';
                defaultOpt.innerText = 'Select...';
                select.appendChild(defaultOpt)

                labelOptions.forEach(label => {
                    const option = document.createElement('option');
                    option.value = label.id || label.name || label;
                    option.textContent = label.name || label;
                    select.appendChild(option);
                });
            } else {
                const option = document.createElement('option');
                option.value = '';
                option.innerText = 'No labels available';
                select.appendChild(option);
            }

            valueCell.appendChild(select);
            select.addEventListener('change', createInputListener(checkbox,select))
        } else if (field === 'sensor_description') {
            const input = document.createElement('input');
            input.type = 'text';
            input.id = 'new_sensor_description';
            input.name = 'new_sensor_description';
            input.placeholder = 'Enter description...';
            valueCell.appendChild(input);
            input.addEventListener('input', createInputListener(checkbox, input));
        }
    });
}

function renderResults(sensors) {
    const container = document.getElementById('validated-sensors-container');
    container.innerHTML = '';
    container.style.maxHeight = '400px';
    container.style.overflowY = 'auto';

    if (!sensors.length) {
        container.innerHTML = '<p>No validated sensors to display.</p>';
        return;
    }

    // Flatten all sensors into a single array to render in a 4x4 table
    const table = document.createElement('table');
    table.style.width = '100%';
    table.style.borderCollapse = 'collapse';
    table.style.marginBottom = '0rem';
    table.style.marginTop = '0rem';
    //table.style.fontSize = '0.85rem'

    let row;
    sensors.forEach((sensor, index) => {
        if (index % 7 === 0) {
            row = document.createElement('tr');
            row.style.height = '30px';
            table.appendChild(row);
        }

        const cell = document.createElement('td');
        cell.textContent = sensor.unique_identifier;
        cell.style.border = '1px solid #ccc';
        cell.style.padding = '4px';
        cell.style.textAlign = 'center';
        cell.style.lineHeight = '1.2';
        row.appendChild(cell);
    });

    container.appendChild(table);
    document.getElementById('validSensors').style.display = 'block';

    // Optionally call a function to populate the Process Details section
    populateProcessDetails(sensors);
}

function populateProcessDetails(sensors) {
    console.log('Populating process details for sensors', sensors);
    const tbody = document.getElementById('processTableBody');
    tbody.innerHTML = '';

    // Group by batch (first 4 chars of unique_identifier)
    const batchGroups = {};
    sensors.forEach(sensor => {
        const batch = sensor.unique_identifier.slice(0, 4);
        if (!batchGroups[batch]) {
            batchGroups[batch] = [];
        }
        batchGroups[batch].push(sensor);
    });

    for (const [batch, batchSensors] of Object.entries(batchGroups)) {
        // Collect unique processes from all sensors in this batch
        const seen = new Set();
        const uniqueProcesses = [];

        batchSensors.forEach(sensor => {
            (sensor.sensor_processes || []).forEach(proc => {
                const key = `${proc.process_id}-${proc.timestamp}`;
                if (!seen.has(key)) {
                    seen.add(key);
                    uniqueProcesses.push({ batch, ...proc });
                }
            });
        });

        // Render batch header row
        const headerRow = document.createElement('tr');
        const headerCell = document.createElement('td');
        headerCell.colSpan = 4;
        headerCell.textContent = `Batch: ${batch}`;
        headerCell.style.fontWeight = 'bold';
        headerCell.style.backgroundColor = '#ccdae3';
        headerRow.appendChild(headerCell);
        tbody.appendChild(headerRow);

        // Render each process row
        uniqueProcesses.forEach(proc => {
            const row = document.createElement('tr');

            const tdId = document.createElement('td');
            tdId.textContent = proc.process_id;
            tdId.style.border = '1px solid #000';

            const tdDesc = document.createElement('td');
            tdDesc.textContent = proc.description;
            tdDesc.style.border = '1px solid #000';

            const tdTime = document.createElement('td');
            const date = new Date(proc.timestamp);
            const formattedDate = `${String(date.getDate()).padStart(2, '0')}/${String(date.getMonth() + 1).padStart(2, '0')}/${String(date.getFullYear()).slice(-2)}, ${date.toLocaleTimeString()}`;
            tdTime.textContent = formattedDate;
            tdTime.style.border = '1px solid #000';

            const tdRemove = document.createElement('td');
            tdRemove.style.border = '1px solid #000';
            const removeBtn = document.createElement('button');
            removeBtn.textContent = 'Remove';
            removeBtn.type = 'button';
            removeBtn.style.backgroundColor = '#f44336';
            removeBtn.style.color = '#fff';
            removeBtn.style.border = 'none';
            removeBtn.style.padding = '5px 10px';
            removeBtn.style.cursor = 'pointer';
            //removeBtn.onclick = () => removeProcess(proc.process_id, proc.batch); // define this function
            removeBtn.addEventListener('click', () => {
                const processIndex = deleteList.findIndex(
                    item => item.process_id === proc.process_id && item.timestamp === new Date(proc.timestamp).toISOString()
                );

                if (processIndex === -1) {
                    deleteList.push({ process_id: proc.process_id, timestamp: new Date(proc.timestamp).toISOString() });
                    console.log('Process added to delete list', proc.process_id);
                    console.log(deleteList);
                    row.style.backgroundColor = '#ffcccc';
                    removeBtn.textContent = 'Undo';
                    removeBtn.style.backgroundColor = '#4CAF50';
                } else {
                    deleteList.splice(processIndex, 1);
                    console.log('Process removed from delete list', proc.process_id);
                    console.log(deleteList);
                    row.style.backgroundColor = '';
                    removeBtn.textContent = 'Remove';
                    removeBtn.style.backgroundColor = '#f44336';

                }
            })
            tdRemove.appendChild(removeBtn);

            row.appendChild(tdId);
            row.appendChild(tdDesc);
            row.appendChild(tdTime);
            row.appendChild(tdRemove);

            tbody.appendChild(row);
        });
    }
    console.log('tbody after populate:', tbody.innerHTML);
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
        u_ids: allOriginalSensorIds,
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

        selectedProcessList = [];
        deleteList = [];

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
    const sensorInput = document.getElementById('u_id');
    sensorInput.value = '';
    document.getElementById('updateFields').style.display = 'none';
    //alert('Sensor data has been reset.');
}



const navEntries = performance.getEntriesByType("navigation");
if (navEntries.length > 0 && navEntries[0].type === "reload") {
    console.log("Page was reloaded. Clearing sensor cache.");
    localStorage.removeItem('wafer_validated_sensors_cache');
}

document.getElementById('loader').style.display = 'none';
document.getElementById('resetBtn').addEventListener('click', resetSensorState);
//document.getElementById('validate').addEventListener('click', validateSensors);
document.getElementById('navtoWF').addEventListener('click', navigatetoWaferForm);
document.getElementById('updateButton').addEventListener('click', submitUpdates);

document.getElementById('sensorForm').addEventListener('submit', function (e) {
    e.preventDefault(); // ✅ Prevent page reload
    validateSensors();
});

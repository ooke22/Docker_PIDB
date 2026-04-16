import { formatDate } from "./utils.js";

/**
 * Dynamically builds the update table to accept a fieldsToUpdate list as a parameter.
 * Uses the createInputListner to auto-check the box when a value is entered.
 */
export function createUpdateTable(labelOptions, fieldsToUpdate = ['label', 'sensor_description']) {
    const table = document.getElementById('updateTable');
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

        if (field === 'label' && labelOptions && labelOptions.length > 0) {
            const select = document.createElement('select');
            select.id = 'new_label';
            select.name = 'new_label';
            select.innerHTML = `<option value="">Select...</option>` +
                labelOptions.map(label =>
                    `<option value="${label.id || label.name}">${label.name || label}</option>`
                ).join('');

            select.addEventListener('change', createInputListener(checkbox, select));
            valueCell.appendChild(select);
        } else {
            const input = document.createElement('input');
            input.type = 'text';
            input.id = `new_${field}`;
            input.name = `new_${field}`;
            input.placeholder = `Enter ${field.replace('_', ' ')}...`;
            input.addEventListener('input', createInputListener(checkbox, input));
            valueCell.appendChild(input);
        }
    });
}

/**
 * Input listener that toggles checkbox based on input value
 */
function createInputListener(checkbox, inputElement) {
    return function () {
        checkbox.checked = inputElement.value.trim() !== '';
    };
}

/**
 * Renders the list of wafer-level processes associated with the retrieved batch into an HTML table.
 * This function populates the #processTableBody element with one row per process, displaying:
 * - Process ID | Description | Timestamp | Remove/Undo Remove Button 
 * @param {Array} processes 
 * @param {Array} deleteList 
 */
export function renderWaferProcessesTable(processes, deleteList) {
    const tableBody = document.getElementById('processTableBody');
    tableBody.innerHTML = '';

    processes.forEach(process => {
        const row = tableBody.insertRow();
        row.style.border = '1px solid #000';

        const processIDcell = row.insertCell(0);
        const descriptionCell = row.insertCell(1);
        const timeStampcell = row.insertCell(2);
        const removeCell = row.insertCell(3);

        processIDcell.textContent = process.process_id;
        descriptionCell.textContent = process.description || 'N/A';

        const formattedDate = formatDate(new Date(process.timestamp));
        timeStampcell.textContent = formattedDate;

        [processIDcell, descriptionCell, timeStampcell, removeCell].forEach(cell => {
            cell.style.border = '1px solid #000';
        });

        const removeButton = document.createElement('button');
        removeButton.textContent = 'Remove';
        removeButton.type = 'button';
        removeButton.style.cssText = `
            background-color: #f44336;
            color: #fff;
            border: none;
            padding: 5px 10px;
            cursor: pointer;
        `;

        removeButton.addEventListener('click', () => {
            const processKey = {
                process_id: process.process_id,
                timestamp: new Date(process.timestamp).toISOString()
            };

            const existingIndex = deleteList.findIndex(
                item => item.process_id === processKey.process_id &&
                        item.timestamp === processKey.timestamp
            );

            if (existingIndex === -1) {
                deleteList.push(processKey);
                row.style.backgroundColor = '#ffcccc';
                removeButton.textContent = 'Undo Remove';
                removeButton.style.backgroundColor = '#4CAF50';
            } else {
                deleteList.splice(existingIndex, 1);
                row.style.backgroundColor = '';
                removeButton.textContent = 'Remove';
                removeButton.style.backgroundColor = '#f44336';
            }

            console.log('Updated deleteList:', deleteList);
        });

        removeCell.appendChild(removeButton);
    });
}


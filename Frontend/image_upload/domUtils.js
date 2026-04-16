import { imageData, sensorUidsList } from "./fileHandler2.js";

/**
 * Clears thumbnail boxes
 */

export function clearPreviewBoxes() {
    document.getElementById('thumbnailBox').innerHTML = '';
    document.getElementById('electrodeBox').innerHTML = '';
    document.getElementById('processIDBox').innerHTML = '';
}

/**
 * Adds thumbnail display for uploaded files.
 * Uses key to handle delete logic
 */
export function addThumbnail(fileName, id, key) {
    const thumbnailBox = document.getElementById('thumbnailBox');
    const item = document.createElement('div');
    item.classList.add('thumbnailBoxItem');
    item.setAttribute('data-key', key);

    const fileInfo = document.createElement('p');
    fileInfo.textContent = `File: ${fileName}`;

    const deleteButton = createDeleteButton(key);

    item.appendChild(fileInfo);
    item.appendChild(deleteButton);
    thumbnailBox.appendChild(item)
}

/**
 * Appends the sensor_uid from the uploaded file to the display
 */
export function addSensorInfo(id) {
    const container = document.createElement('div');
    const info = document.createElement('p');
    info.textContent = `Sensor UID: ${id}`;
    container.appendChild(info);
    document.getElementById('electrodeBox').appendChild(container);
}

/**
 * Displays the selected process_id for the uploaded file
 */
export function displayPID(processID, key) {
    const box = document.getElementById('processIDBox');

    const container = document.createElement('div');
    container.classList.add('process-id-item');
    container.setAttribute('data-key', key);

    //const msg = processID ? `Process ID: ${processID}` : `No Process ID selected.`;
    const info = document.createElement('p');
    info.textContent = `Process ID: ${processID || 'Not Set'}`;
    info.classList.add('process-id-text');

    container.appendChild(info);
    box.appendChild(container);
}

export function removePID(key) {
    const box = document.getElementById('processIDBox');
    const target =[...box.querySelectorAll('.process-id-item')]
        .find(div => div.getAttribute('data-key') === key);
        if (target) target.remove();
}

export function updatePID(key, newPID) {
    const box = document.getElementById('processIDBox');
    const target = [...box.querySelectorAll('.process-id-item')]
        .find(div => div.getAttribute('data-key') === key);

    if (target) {
        const p = target.querySelector('.process-id-text');
        if (p) {
            p.textContent = `Process ID: ${newPID || 'Not Set'}`;
        }
    }
}

// Creates delete button next to each thumbnail item
export function createDeleteButton(key) {
    const button = document.createElement('button');
    button.innerHTML = '&#x2716;';
    button.classList.add('delete-button');
    button.addEventListener('click', () => handleDelete(key));
    return button;
}

/**
 * handleDelete function utilizes imageData array containing imgDict of uploaded image files and their respective sensor_uids
 * will remove key of selected file to delete from the array
 */

function handleDelete(key) {
    const thumbnailBox = document.getElementById('thumbnailBox');
    const sensorBox = document.getElementById('electrodeBox');

    const index = imageData.findIndex(img => img.key === key);
    if (index !== -1) {
        const id = imageData[index].id;
        imageData.splice(index, 1);
        sensorUidsList.splice(index, 1);

        // Remove thumbnail
        const thumbnail = [...thumbnailBox.children].find(
            p => p.getAttribute('data-key') === key
        );
        if (thumbnail) thumbnail.remove();

        // Remove sensor UID
        const matchingID = [...sensorBox.querySelectorAll('p')].find(p => 
            p.textContent.includes(id)
        );
        if (matchingID) matchingID.parentNode.remove();

        // Remove process ID
        removePID(key);
    }
}
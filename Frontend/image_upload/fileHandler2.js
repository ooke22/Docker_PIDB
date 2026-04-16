// fileHandler.js
//import { isImage, getMatchingUID } from './utils.js';
import { sensorIDs, processList } from "./data-fetching.js";
import { clearPreviewBoxes, addThumbnail, addSensorInfo, displayPID, updatePID } from "./domUtils.js";

export let imageData = []; // [{ file, id, process_id, key }]
export let sensorUidsList = []; // [id1, id2, ...]

/**
 * Enables file drop capability
 */
export function handleDrop(event) {
    event.preventDefault();
    const files = event.dataTransfer.files;
    processFiles(files, { append: true });
}

/**
 * Enables file dragover capability
 */

export function handleDragOver(event) {
    event.preventDefault();
}

function createProcessDropdown(key, initialValue) {
    const select = document.createElement('select');
    select.className = 'process-dropdown';
    select.setAttribute('data-key', key);

    processList.forEach(p => {
        const option = document.createElement('option');
        option.value = p.process_id;
        option.textContent = `${p.process_id} - ${p.description}`;
        if (p.process_id === initialValue) option.selected = true;
        select.appendChild(option);
    });

    select.addEventListener('change', (e) => {
        const selectedID = e.target.value;
        const index = imageData.findIndex(img => img.key === key);
        if (index !== -1) {
            imageData[index].process_id = selectedID;
            updatePID(key, selectedID);  
            console.log(`Updated process ID for ${key}: ${selectedID}`);
        }
    });

    return select;
}

export async function processFiles(files, { append = false } = {}) {
    const processID = document.getElementById('processInput')?.value || '';

    if (!append) {
        clearPreviewBoxes();
        imageData = [];
        sensorUidsList = [];
    }

    const groupedImages = {}; // baseId => [file1, file2, ...]
    const seenKeys = new Set(); // To track duplicates like 'M007-01-001 t'

    for (const file of files) {
        if (!isImage(file)) continue;

        const baseId = extractSensorBaseId(file.name);
        const suffix = getSuffix(file.name);
        const uniqueFileKey = `${baseId}${suffix ? ' ' + suffix : ''}`;

        if (!baseId) {
            alert(`Sensor ID could not be parsed from file: ${file.name}`);
            continue;
        }

        if (seenKeys.has(uniqueFileKey)) {
            alert(`Duplicate file skipped: ${uniqueFileKey}`);
            continue;
        }

        seenKeys.add(uniqueFileKey);

        if (!groupedImages[baseId]) {
            groupedImages[baseId] = [];
        }
        groupedImages[baseId].push({ file, suffix });
    }

    for (const [baseId, fileGroup] of Object.entries(groupedImages)) {
        const sensor = getMatchingUID(baseId);
        if (!sensor) {
            alert(`Sensor ${baseId} not found in database.`);
            continue;
        }

        fileGroup.forEach(({ file, suffix }, idx) => {
            const uniqueKey = `${baseId}${suffix ? ' ' + suffix : ''}__${idx}`;
            const imgDict = { file, id: sensor, process_id: processID, key: uniqueKey };

            imageData.push(imgDict);
            sensorUidsList.push(sensor);

            addThumbnail(file.name, sensor, uniqueKey);
            addSensorInfo(sensor);
            displayPID(processID, uniqueKey);

            const thumbnailItems = document.getElementsByClassName('thumbnailBoxItem');
            const lastItem = thumbnailItems[thumbnailItems.length - 1];
            const dropdown = createProcessDropdown(uniqueKey, processID);
            lastItem.appendChild(dropdown);
        });
    }

    sensorUidsList = imageData.map(data => data.id);
    console.log('Found Sensor IDs', sensorUidsList);
}

/**
 * Checks if uploaded file is an image file
 */
function isImage(file) {
    const ext = file.name.split('.').pop().toLowerCase();
    return ['jpg', 'jpeg', 'png', 'tiff'].includes(ext);
}

/**
 * Extracts base sensor ID from filename (e.g., M007-01-001 t.png -> M007-01-001)
 * Updated for M007-01-001_t.png format
 */
function extractSensorBaseId(fileName) {
    const name = fileName.split('.')[0];
    const match = name.match(/^([A-Z]\d{3}-\d{2}-\d{3})/i);
    return match ? match[1].toUpperCase() : null;
}

/**
 * Extracts trailing alphabet suffix from filename (e.g., M007-01-001 t.png -> 't')
 */
function getSuffix(fileName) {
    const name = fileName.split('.')[0];
    const match = name.match(/_([a-z])$/i); // match '_t' style
    return match ? match[1].toLowerCase() : '';
}


/**
 * Matches base sensor ID to known unique_identifier from sensor list
 */
function getMatchingUID(baseId) {
    const match = sensorIDs.find(s => s === baseId);
    if (!match) {
        console.warn(`Sensor UID for uploaded base ID: ${baseId} not found.`);
        return null;
    }
    return match;
}
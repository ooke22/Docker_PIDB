import { sensorIDs, processList } from "./data-fetching.js";
import { clearPreviewBoxes, addThumbnail, addSensorInfo, displayPID, updatePID } from "./domUtils.js";

// sensor u_ids from the backend
sensorIDs

//stored files + matched sensor UID
export let imageData = [];

// Stores extracted sensor UIDS (based on filenames)
export let sensorUidsList = [];

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

/** 
 * Processes uploaded files
 * Extracts dragged and dropped files names
 * appends to the sensorUIDsList
 */

export async function processFiles(files, { append = false } = {}) {
    const processID = document.getElementById('processInput')?.value || '';

    if (!append) {
        clearPreviewBoxes();
        imageData = [];
        sensorUidsList = [];
    }

    const exisitingKeys = new Set(imageData.map(img => img.file.name.toLowerCase()));

    [...files].forEach((file) => {
        const fileKey = file.name.toLowerCase();
        
        if (!isImage(file)) return;

        if (exisitingKeys.has(fileKey)) {
            console.warn(`Duplicate file skipped: ${file.name}`);
            alert(`File already uploaded: ${file.name}`);
            return;
        }

        const id = getMatchingUID(file.name);
        if (!id) {
            alert(`Sensor ${file.name.split('.')[0]} not found in database.`);
            return;
        }
        console.log('Matched ID:', id);
        const imgDict = { file, id, process_id: processID, key: fileKey };
        console.log('Image Dict:', imgDict);

        imageData.push(imgDict);
        sensorUidsList.push(id);

        addThumbnail(file.name, id, fileKey);
        addSensorInfo(id);
        displayPID(processID,fileKey);

        const thumbnailItems = document.getElementsByClassName('thumbnailBoxItem');
        const lastItem = thumbnailItems[thumbnailItems.length - 1];
        const processDropdown = createProcessDropdown(fileKey, processID);
        lastItem.appendChild(processDropdown);
    });

    //displayPID(processID);
    sensorUidsList = imageData.map(data => data.id);
}

/**
 * Checks if uploaded file is an image file
 */
function isImage(file) {
    const ext = file.name.split('.').pop().toLowerCase();
    return ['jpg', 'jpeg', 'png', 'tiff'].includes(ext);
}

/**
 * Matches file name to a known sensor unique identifier
 */
function getMatchingUID(fileName) {
    const id = fileName.split('.')[0].toUpperCase();
    const match = sensorIDs.find(s => s === id);
    if (!match) {
        console.warn(`Sensor UID for uploaded file: ${id} not found.`);
        return null;
    }

    return match;
}


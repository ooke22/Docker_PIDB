/**
 * Normalize sensor ID input to standardized format.
 * Example: "m2-3-4" -> "M002-03-004"
 */

export function normalizeSensorId(id) {
    const cleaned = id.trim().toUpperCase();
    const match = cleaned.match(/^([A-Z])(\d{1,4})[-_](\d{1,4})[-_](\d{1,4})$/);

    if (!match) return null;

    const [, loc, batch, wafer, number] = match;

    const paddedBatch = batch.padStart(3, '0').slice(-3);
    const paddedWafer = wafer.padStart(2, '0').slice(-2);
    const paddedNumber = number.padStart(3, '0').slice(-3);

    return `${loc}${paddedBatch}-${paddedWafer}-${paddedNumber}`;
}



/**
 * Create an  input listener that toggles checkbox based on input value
 */
export function createInputListener(checkbox, inputElement) {
    return function () {
        checkbox.checked = inputElement.value.trim() !== '';
    };
}

/**
 * Format a javascript Date object into `DD/MM/YY, hh:mm:ss AM/PM`.
 */

export function formatDate(date) {
    if (!(date instanceof Date)) date = new Date(date);
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const year = String(date.getFullYear()).slice(-2);
    const time = date.toLocaleTimeString();
    return `${day}/${month}/${year}, ${time}`;
}

/**
 * Parse + normalize sensor IDs
 */
export function parseNormalizedSensorIds(rawInput) {
    const failed = [];
    const normalizedMap = {};

    const ids = rawInput.split(',').map(id => id.trim()).filter(Boolean).map(id => {
        const norm = normalizeSensorId(id);
        if (!norm) {
            failed.push(id);
            return null;
        } else {
            normalizedMap[norm] = id;
        }
        return norm;
    }).filter(Boolean);
    return { normalizedIds: ids, failed, normalizedMap };
}

/**
 * Build feedback messages
 */
export function validationMessaages({ failed = [], notFound = [], alreadyAdded = [] }) {
    const messages = [];
    if (failed.length) messages.push(`Invalid syntax: ${failed.join(',')}`);
    if(notFound.length) messages.push(`Not found: ${notFound.join(',')}`);
    if (alreadyAdded.length) messages.push(`Already added: ${alreadyAdded.join(',')}`);
    return messages.length ? messages.join('\n') : '';
}

/**
 * Save the current state of validated sensors to localStorage.
 */

export function saveSensorCache(validatedSensors, originalIds) {
    localStorage.setItem('wafer_validated_sensors_cache', JSON.stringify({
        validated: validatedSensors,
        original: originalIds
    }));
}

/**
 * Load sensor cache from localStorage
 */

export function loadSensorCache() {
    const cached = localStorage.getItem('wafer_validated_sensors_cache');
    if (!cached) return null;

    try {
        return JSON.parse(cached);
    } catch (e) {
        console.error('Failed to parse cached sensor data:',e);
        return null;
    }
}

/**
 * Merge new validated sensors into existing state.
 * Ensures uniqueness based on `unique_identifier`.
 */
export function mergeValidatedSensors(existing, newSensors) {
    const exisitingIds = new Set(existing.map(s => s.unique_identifier));
    const uniqueNew = newSensors.filter(s => !exisitingIds.has(s.unique_identifier));
    return [...existing, ...uniqueNew];
}

/**
 * Merge new original sensor IDs, ensuring uniqueness.
 */
export function mergeOriginalSensorIds(existing, newOriginal) {
    const newUnique = newOriginal.filter(id => !existing.includes(id));
    return [...existing, ...newUnique];
}
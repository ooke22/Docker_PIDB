// ===========================================================================================
// Configuration
// ===========================================================================================
const API_BASE = 'http://127.0.0.1:8000/experiments';
const DEBOUNCE_DELAY = 500;

// ===========================================================================================
// State Management
// ===========================================================================================
let groups = [];
let groupIdCounter = 0;
let sensorIdCounter = 0;
let csvData = null;
const debounceTimers = {};

// ===========================================================================================
// Initialization
// ===========================================================================================
document.addEventListener('DOMContentLoaded', () => {
    initializeForm();
    addGroup(); // Add first group by default
});

function initializeForm() {
    document.getElementById('addGroupBtn').addEventListener('click', addGroup);
    document.getElementById('experimentForm').addEventListener('submit', handleSubmit);
    document.getElementById('cancelBtn').addEventListener('click', handleCancel);
    document.getElementById('csvFile').addEventListener('change', handleFileUpload);
    
    // Drag and drop for CSV
    const fileLabel = document.getElementById('fileLabel');
    fileLabel.addEventListener('dragover', (e) => {
        e.preventDefault();
        fileLabel.style.borderColor = '#667eea';
    });
    fileLabel.addEventListener('dragleave', () => {
        fileLabel.style.borderColor = '#d1d5db';
    });
    fileLabel.addEventListener('drop', handleFileDrop);
}

// ===========================================================================================
// Group Management
// ===========================================================================================
function addGroup() {
    const groupId = groupIdCounter++;
    const groupNumber = groups.length + 1;
    
    const group = {
        id: groupId,
        number: groupNumber,
        label: `Setup ${groupNumber}`,
        sensors: []
    };
    
    groups.push(group);
    renderGroups();
    
    // Add first sensor to this group
    addSensorToGroup(groupId);
}

function removeGroup(groupId) {
    if (groups.length <= 1) {
        showAlert('error', 'Cannot remove the last group. At least one group is required.');
        return;
    }
    
    groups = groups.filter(g => g.id !== groupId);
    
    // Renumber groups
    groups.forEach((group, index) => {
        group.number = index + 1;
        if (group.label.match(/^Setup \d+$/)) {
            group.label = `Setup ${index + 1}`;
        }
    });
    
    renderGroups();
}

function updateGroupLabel(groupId, label) {
    const group = groups.find(g => g.id === groupId);
    if (group) {
        group.label = label;
    }
}

// ===========================================================================================
// Sensor Management
// ===========================================================================================
function addSensorToGroup(groupId) {
    const group = groups.find(g => g.id === groupId);
    if (!group) return;
    
    const sensorId = sensorIdCounter++;
    const sensor = {
        id: sensorId,
        unique_id: '',
        electrode: 'BOTH',
        role: 'WE',
        notes: '',
        validation: null
    };
    
    group.sensors.push(sensor);
    renderGroups();
}

function removeSensorFromGroup(groupId, sensorId) {
    const group = groups.find(g => g.id === groupId);
    if (!group) return;
    
    if (group.sensors.length <= 1) {
        showAlert('error', 'Each group must have at least one sensor.');
        return;
    }
    
    group.sensors = group.sensors.filter(s => s.id !== sensorId);
    renderGroups();
}

function updateSensor(groupId, sensorId, field, value) {
    const group = groups.find(g => g.id === groupId);
    if (!group) return;
    
    const sensor = group.sensors.find(s => s.id === sensorId);
    if (sensor) {
        sensor[field] = value;
    }
}

// ===========================================================================================
// Rendering Functions
// ===========================================================================================
function renderGroups() {
    const container = document.getElementById('groupList');
    container.innerHTML = groups.map(group => renderGroup(group)).join('');
}

function renderGroup(group) {
    return `
        <div class="group-container" data-group-id="${group.id}">
            <div class="group-header">
                <div class="group-title">
                    <span class="group-number">Group ${group.number}</span>
                    <input 
                        type="text" 
                        class="group-label-input"
                        placeholder="e.g., Primary Setup"
                        value="${group.label}"
                        onchange="updateGroupLabel(${group.id}, this.value)"
                    >
                </div>
                <div class="group-actions">
                    ${groups.length > 1 ? `
                        <button type="button" class="remove-group-btn" onclick="removeGroup(${group.id})">
                            Remove Group
                        </button>
                    ` : ''}
                </div>
            </div>
            
            <div class="sensor-list">
                ${group.sensors.map((sensor, index) => renderSensor(group.id, sensor, index)).join('')}
            </div>
            
            <button type="button" class="add-sensor-btn" onclick="addSensorToGroup(${group.id})">
                <span>+</span> Add Sensor to This Group
            </button>
        </div>
    `;
}

function renderSensor(groupId, sensor, index) {
    return `
        <div class="sensor-item ${getSensorClass(sensor)}" data-sensor-id="${sensor.id}">
            <div class="sensor-header">
                <span class="sensor-number">Sensor ${index + 1}</span>
                <button type="button" class="remove-sensor" onclick="removeSensorFromGroup(${groupId}, ${sensor.id})">
                    Remove
                </button>
            </div>
            <div class="sensor-grid">
                <div>
                    <label>Sensor ID *</label>
                    <input 
                        type="text" 
                        placeholder="e.g., M021-01-045"
                        value="${sensor.unique_id}"
                        onchange="updateSensor(${groupId}, ${sensor.id}, 'unique_id', this.value)"
                        oninput="debouncedValidate(${groupId}, ${sensor.id}, this.value)"
                        required
                    >
                    <div class="validation-container">
                        ${renderValidationStatus(sensor)}
                    </div>
                </div>
                <div>
                    <label>Electrode *</label>
                    <select onchange="updateSensor(${groupId}, ${sensor.id}, 'electrode', this.value)">
                        <option value="BOTH" ${sensor.electrode === 'BOTH' ? 'selected' : ''}>Both</option>
                        <option value="E1" ${sensor.electrode === 'E1' ? 'selected' : ''}>E1</option>
                        <option value="E2" ${sensor.electrode === 'E2' ? 'selected' : ''}>E2</option>
                    </select>
                </div>
                <div>
                    <label>Role *</label>
                    <select onchange="updateSensor(${groupId}, ${sensor.id}, 'role', this.value)">
                        <option value="WE" ${sensor.role === 'WE' ? 'selected' : ''}>WE</option>
                        <option value="RE" ${sensor.role === 'RE' ? 'selected' : ''}>RE</option>
                        <option value="CE" ${sensor.role === 'CE' ? 'selected' : ''}>CE</option>
                    </select>
                </div>
            </div>
            <div class="sensor-notes">
                <label>Notes</label>
                <input 
                    type="text" 
                    placeholder="Optional notes..."
                    value="${sensor.notes}"
                    onchange="updateSensor(${groupId}, ${sensor.id}, 'notes', this.value)"
                >
            </div>
        </div>
    `;
}

function getSensorClass(sensor) {
    if (!sensor.validation) return '';
    if (sensor.validation.status === 'validating') return 'validating';
    if (sensor.validation.status === 'valid') return 'valid';
    if (sensor.validation.status === 'invalid') return 'invalid';
    return '';
}

function renderValidationStatus(sensor) {
    if (!sensor.validation) return '';
    
    const { status, message, info } = sensor.validation;
    
    if (status === 'validating') {
        return `
            <div class="validation-status checking">
                <span>⏳</span>
                <span>Validating...</span>
            </div>
        `;
    }
    
    if (status === 'valid') {
        return `
            <div class="validation-status success">
                <span>✓</span>
                <span>${message}</span>
            </div>
            ${info ? `<div class="sensor-info">Batch: ${info.batch_location}, Processes: ${info.process_count}</div>` : ''}
        `;
    }
    
    if (status === 'invalid') {
        return `
            <div class="validation-status error">
                <span>✗</span>
                <span>${message}</span>
            </div>
        `;
    }
    
    return '';
}

// ===========================================================================================
// Targeted DOM Update Functions (FIX FOR INPUT LOSING FOCUS)
// ===========================================================================================

/**
 * Updates only the validation status of a specific sensor without re-rendering entire DOM.
 * This prevents the input field from losing focus during typing.
 */
function updateValidationUI(groupId, sensorId, validation) {
    // Find the specific sensor item in the DOM
    const sensorItem = document.querySelector(
        `.group-container[data-group-id="${groupId}"] .sensor-item[data-sensor-id="${sensorId}"]`
    );
    
    if (!sensorItem) {
        console.warn(`Sensor item not found for groupId: ${groupId}, sensorId: ${sensorId}`);
        return;
    }
    
    // Update the sensor item's class for styling
    sensorItem.className = `sensor-item ${getSensorClass({ validation })}`;
    
    // Find and update the validation container
    const validationContainer = sensorItem.querySelector('.validation-container');
    if (validationContainer) {
        // Get the sensor object to pass to renderValidationStatus
        const group = groups.find(g => g.id === groupId);
        const sensor = group?.sensors.find(s => s.id === sensorId);
        
        if (sensor) {
            validationContainer.innerHTML = renderValidationStatus(sensor);
        }
    }
}

// ===========================================================================================
// Validation Functions (FIXED - No longer re-renders entire DOM)
// ===========================================================================================

function debouncedValidate(groupId, sensorId, value) {
    const key = `${groupId}-${sensorId}`;
    clearTimeout(debounceTimers[key]);
    
    debounceTimers[key] = setTimeout(() => {
        validateSensor(groupId, sensorId, value);
    }, DEBOUNCE_DELAY);
}

async function validateSensor(groupId, sensorId, sensorUniqueId) {
    const group = groups.find(g => g.id === groupId);
    if (!group) return;
    
    const sensor = group.sensors.find(s => s.id === sensorId);
    if (!sensor) return;
    
    // Guard clause: invalid input
    if (!sensorUniqueId || sensorUniqueId.length < 5) {
        sensor.validation = null;
        updateValidationUI(groupId, sensorId, null);  // Targeted update instead of full re-render
        return;
    }

    // Set validating state
    sensor.validation = { status: 'validating', message: 'Checking...' };
    updateValidationUI(groupId, sensorId, sensor.validation);  // Targeted update

    try {
        // Make API call
        const response = await fetch(`${API_BASE}/utils/validate-sensors/?sensor_ids=${encodeURIComponent(sensorUniqueId)}`);
        const data = await response.json();

        if (data.valid && data.sensors.length > 0) {
            const sensorInfo = data.sensors[0];
            sensor.validation = {
                status: 'valid',
                message: 'Sensor found',
                info: sensorInfo
            };
        } else {
            sensor.validation = {
                status: 'invalid',
                message: 'Sensor not found in database'
            };
        }
    } catch (error) {
        console.error('Validation error:', error);
        sensor.validation = {
            status: 'invalid',
            message: 'Validation failed'
        };
    }

    updateValidationUI(groupId, sensorId, sensor.validation);  // Targeted update
}

// ===========================================================================================
// CSV File Handling
// ===========================================================================================
function handleFileUpload(e) {
    const file = e.target.files[0];
    if (file) {
        processCSVFile(file);
    }
}

function handleFileDrop(e) {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file && (file.name.endsWith('.csv') || file.name.endsWith('.txt'))) {
        document.getElementById('csvFile').files = e.dataTransfer.files;
        processCSVFile(file);
    }
    e.target.style.borderColor = '#d1d5db';
}

function processCSVFile(file) {
    const reader = new FileReader();
    reader.onload = (e) => {
        csvData = parseCSV(e.target.result);
        const fileLabel = document.getElementById('fileLabel');
        const fileName = document.getElementById('fileName');
        fileLabel.classList.add('has-file');
        fileName.textContent = `✓ ${file.name} (${csvData.rows.length} rows)`;
    };
    reader.onerror = (e) => {
        showAlert('error', 'Failed to read file: ' + e.target.error);
    };
    reader.readAsText(file);
}

function parseCSV(text) {
    const lines = text.split('\n').filter(line => line.trim());
    if (lines.length === 0) return { headers: [], rows: [] };
    
    const headers = lines[0].split(',').map(h => h.trim());
    const rows = lines.slice(1).map(line => {
        const values = line.split(',').map(v => v.trim());
        return headers.reduce((obj, header, index) => {
            obj[header] = values[index] || '';
            return obj;
        }, {});
    });
    return { headers, rows };
}

// ===========================================================================================
// Form Submission
// ===========================================================================================
async function handleSubmit(e) {
    e.preventDefault();

    // Validate all sensors
    let allSensorsValid = true;
    let invalidCount = 0;
    
    for (const group of groups) {
        for (const sensor of group.sensors) {
            if (!sensor.validation || sensor.validation.status !== 'valid') {
                allSensorsValid = false;
                invalidCount++;
            }
        }
    }

    if (!allSensorsValid) {
        showAlert('error', `Please ensure all sensors are validated before submitting. (${invalidCount} sensor${invalidCount > 1 ? 's' : ''} not validated)`);
        return;
    }

    // Check for required fields
    const formData = new FormData(e.target);
    if (!formData.get('experiment_id') || !formData.get('title')) {
        showAlert('error', 'Please fill in all required fields (Experiment ID and Title).');
        return;
    }

    // Disable submit button
    const submitBtn = document.getElementById('submitBtn');
    const submitText = document.getElementById('submitText');
    const submitSpinner = document.getElementById('submitSpinner');
    submitBtn.disabled = true;
    submitText.style.display = 'none';
    submitSpinner.style.display = 'block';

    try {
        // Build sensor payload with group information
        const sensorsPayload = [];
        groups.forEach(group => {
            group.sensors.forEach(sensor => {
                sensorsPayload.push({
                    unique_id: sensor.unique_id,
                    electrode: sensor.electrode,
                    role: sensor.role,
                    notes: sensor.notes,
                    group_id: group.number,
                    group_label: group.label
                });
            });
        });

        const payload = {
            experiment_id: formData.get('experiment_id'),
            title: formData.get('title'),
            description: formData.get('description') || '',
            experiment_type: formData.get('experiment_type') || null,
            test_date: formData.get('test_date') || null,
            status: formData.get('status'),
            notes: formData.get('notes') || '',
            sensors: sensorsPayload,
            user_data: csvData || {}
        };

        console.log('Submitting payload:', payload);

        const response = await fetch(`${API_BASE}/create/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (response.ok) {
            showAlert('success', `Experiment ${data.experiment.experiment_id} created successfully! Redirecting...`);
            setTimeout(() => {
                window.location.href = `/experiments/${data.experiment.experiment_id}/`;
            }, 2000);
        } else {
            const errorMessage = data.error || data.message || 'Failed to create experiment';
            let errorDetails = '';
            
            if (data.detail) {
                errorDetails = typeof data.detail === 'string' 
                    ? data.detail 
                    : JSON.stringify(data.detail, null, 2);
            }
            
            showAlert('error', errorMessage + (errorDetails ? '\n' + errorDetails : ''));
            submitBtn.disabled = false;
            submitText.style.display = 'block';
            submitSpinner.style.display = 'none';
        }
    } catch (error) {
        console.error('Submission error:', error);
        showAlert('error', 'Network error: ' + error.message);
        submitBtn.disabled = false;
        submitText.style.display = 'block';
        submitSpinner.style.display = 'none';
    }
}

function handleCancel() {
    if (confirm('Are you sure you want to cancel? All data will be lost.')) {
        window.location.href = '/experiments/';
    }
}

// ===========================================================================================
// UI Utilities
// ===========================================================================================
function showAlert(type, message) {
    const container = document.getElementById('alertContainer');
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.innerHTML = `
        <span class="alert-icon">${type === 'success' ? '✓' : '✗'}</span>
        <span style="white-space: pre-wrap;">${escapeHtml(message)}</span>
    `;
    container.innerHTML = '';
    container.appendChild(alert);
    container.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    
    // Auto-dismiss success alerts after 5 seconds
    if (type === 'success') {
        setTimeout(() => {
            alert.style.transition = 'opacity 0.5s';
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 500);
        }, 5000);
    }
}

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

// ===========================================================================================
// Expose Functions to Window (for inline event handlers)
// ===========================================================================================
window.addGroup = addGroup;
window.removeGroup = removeGroup;
window.updateGroupLabel = updateGroupLabel;
window.addSensorToGroup = addSensorToGroup;
window.removeSensorFromGroup = removeSensorFromGroup;
window.updateSensor = updateSensor;
window.debouncedValidate = debouncedValidate;
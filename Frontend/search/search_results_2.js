import { renderImageSection } from "./imageSection.js";

// Get search results from localStorage
let searchResults = null;

try {
    const storedResults = localStorage.getItem('searchResults');
    if (storedResults) {
        searchResults = JSON.parse(storedResults);
        console.log('Search Results:', searchResults);
        console.log('Processes:', searchResults.process_summary?.processes);
    } else {
        console.warn('No search results found in localStorage');
        // Show error state
        showErrorState('No search results found');
    }
} catch (error) {
    console.error('Error parsing search results from localStorage:', error);
    showErrorState('Error loading search results');
}

function formatDate(dateString) {
    if (!dateString) return 'N/A';
    try {
        const date = new Date(dateString);
        if (isNaN(date.getTime())) return 'Invalid Date';
        
        return date.toLocaleString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch (error) {
        console.error('Error formatting date:', error);
        return 'Invalid Date';
    }
}

function createInfoItem(label, value) {
    // Handle null, undefined, or empty string values
    const displayValue = (value !== null && value !== undefined && value !== '') ? value : 'N/A';
    
    return `
        <div class="info-item">
            <span class="info-label">${label}</span>
            <span class="info-value">${displayValue}</span>
        </div>
    `;
}

function createTimelineItem(process, index, total) {
    if (!process) return '';
    
    const isCompleted = index < total;
    const description = process.description || 'Unknown Process';
    const processId = process.process_id || 'N/A';
    const timestamp = formatDate(process.timestamp);
    
    return `
        <div class="timeline-item">
            <div class="timeline-marker ${isCompleted ? 'completed' : ''}"></div>
            <div class="timeline-content">
                <div class="timeline-header">
                    <div class="timeline-title">${description}</div>
                    <div class="timeline-id">${processId}</div>
                </div>
                <div class="timeline-timestamp">
                    <i class="fas fa-clock"></i>
                    ${timestamp}
                </div>
            </div>
        </div>
    `;
}

function populateInterface(searchResults) {
    if (!searchResults) {
        showErrorState('No search results available');
        return;
    }

    const sensorInfo = searchResults.sensor_info || {};
    const processInfo = searchResults.process_summary || {};

    // Update header and overview with safe access
    const sensorIdentifierEl = document.getElementById('sensor-identifier');
    const totalProcessesEl = document.getElementById('total-processes');
    const totalWafersEl = document.getElementById('total-wafers');
    const totalSensorsEl = document.getElementById('total-sensors');
    const lastProcessDateEl = document.getElementById('last-process-date');
    const batchLocationEl = document.getElementById('batch-location');
    const batchIdEl = document.getElementById('batch-id');

    if (sensorIdentifierEl) sensorIdentifierEl.textContent = sensorInfo.unique_identifier || 'N/A';
    if (totalProcessesEl) totalProcessesEl.textContent = processInfo.total_processes || '0';
    if (totalWafersEl) totalWafersEl.textContent = sensorInfo.total_wafers || '0';
    if (totalSensorsEl) totalSensorsEl.textContent = sensorInfo.total_sensors || '0';
    if (lastProcessDateEl) lastProcessDateEl.textContent = formatDate(processInfo.last_process_timestamp);
    if (batchLocationEl) batchLocationEl.textContent = sensorInfo.batch_location || 'N/A';
    if (batchIdEl) batchIdEl.textContent = sensorInfo.batch_id || 'N/A';

    // Populate batch information
    const batchInfo = document.getElementById('batch-info');
    if (batchInfo) {
        batchInfo.innerHTML = `
            ${createInfoItem('Location', sensorInfo.batch_location)}
            ${createInfoItem('Batch ID', sensorInfo.batch_id)}
            ${createInfoItem('Label', sensorInfo.batch_label)}
            ${createInfoItem('Description', sensorInfo.batch_description)}
            ${createInfoItem('Total Wafers', sensorInfo.total_wafers)}
        `;
    }

    // Populate wafer information
    const waferInfo = document.getElementById('wafer-info');
    if (waferInfo) {
        waferInfo.innerHTML = `
            ${createInfoItem('Wafer ID', sensorInfo.wafer_id)}
            ${createInfoItem('Label', sensorInfo.wafer_label)}
            ${createInfoItem('Description', sensorInfo.wafer_description)}
            ${createInfoItem('Design ID', sensorInfo.wafer_design_id)}
            ${createInfoItem('Total Sensors', sensorInfo.total_sensors)}
        `;
    }

    // Populate sensor information
    const sensorInfoDiv = document.getElementById('sensor-info');
    if (sensorInfoDiv) {
        sensorInfoDiv.innerHTML = `
            ${createInfoItem('Sensor ID', sensorInfo.sensor_id)}
            ${createInfoItem('Label', sensorInfo.sensor_label)}
            ${createInfoItem('Description', sensorInfo.sensor_description)}
            ${createInfoItem('Unique ID', sensorInfo.unique_identifier)}
        `;
    }

    // Populate process timeline
    const timeline = document.getElementById('process-timeline');
    if (timeline) {
        if (processInfo.processes && Array.isArray(processInfo.processes) && processInfo.processes.length > 0) {
            timeline.innerHTML = processInfo.processes
                .map((process, index) => createTimelineItem(process, index, processInfo.processes.length))
                .join('');
        } else {
            timeline.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-clipboard-list"></i>
                    <p>No processes found</p>
                </div>
            `;
        }
    }

    // Handle images section
    const imagesSection = document.getElementById('images-section');
    if (imagesSection) {
        const imagesByProcess = searchResults.images_by_process;
        if (imagesByProcess && Object.keys(imagesByProcess).length > 0) {
            renderImageSection(imagesSection, imagesByProcess);
        }
    }
}

function pageHeader() {
    const sensorIdEl = document.getElementById('sensorID');
    if (sensorIdEl && searchResults && searchResults.sensor_info) {
        sensorIdEl.textContent = `Sensor: ${searchResults.sensor_info.unique_identifier}` || 'Search Results';
    } else if (sensorIdEl) {
        sensorIdEl.textContent = 'Search Results';
    }
}

function showErrorState(message) {
    // Show error in the main content area
    const mainContent = document.querySelector('.main-content');
    if (mainContent) {
        mainContent.innerHTML = `
            <div class="results-container">
                <div class="empty-state" style="padding: 4rem 1rem;">
                    <i class="fas fa-exclamation-triangle" style="font-size: 4rem; color: var(--error-color); margin-bottom: 2rem;"></i>
                    <h2 style="color: var(--text-primary); margin-bottom: 1rem;">${message}</h2>
                    <p style="color: var(--text-secondary);">Please try searching again or contact support if the problem persists.</p>
                    <button onclick="window.history.back()" style="
                        margin-top: 2rem;
                        padding: 0.75rem 1.5rem;
                        background: var(--primary-color);
                        color: white;
                        border: none;
                        border-radius: var(--radius);
                        cursor: pointer;
                        font-size: 1rem;
                    ">Go Back</button>
                </div>
            </div>
        `;
    }
}

// Initialize the interface when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Set up page header
    pageHeader();
    
    // Populate interface if we have search results
    if (searchResults) {
        populateInterface(searchResults);
    } else {
        showErrorState('No search results found');
    }
});

// Export functions for potential use by other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        formatDate,
        createInfoItem,
        createTimelineItem,
        populateInterface,
        pageHeader
    };
}
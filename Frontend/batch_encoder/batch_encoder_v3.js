import { processIdAPI, v2BatchEncoderAPI, } from "../shared/url.js";
import { getCookie, getToken } from "../shared/utils.js";

const csrftoken = getCookie('csrftoken');
const token = getToken();

let allProcesses = {};

// Function to be called on page load
async function retrieveProcesses() {
    try {
        const response = await fetch(processIdAPI, {
            method: 'GET',
            headers: {
                'Authorization': `Token ${token}`,
                'X-CSRFToken': csrftoken,
            }
        });
        if (!response.ok) {
            const errorText = await response.text();
            console.error('HTTP error details:', response.status, errorText);
            throw new Error('Unable to fetch processes.');
        }

        const processes = await response.json();

        //Build lookup table: { process_id: description }
        processes.forEach(proc => {
            allProcesses[proc.process_id] = proc.description;
        });

        // Populate the  Process ID Dropdown
        populateProcessDropdown(processes);
    } catch (error) {
        console.error('Error fetching processes: ', error);
        alert('Error fetching processes. Please try again.');
    }
}

// Function to populate Process ID Dropdown
function populateProcessDropdown(processes) {
    const dropdown = document.getElementById('wafer_process_dropdown');
    dropdown.innerHTML = ''; // Clear existing options

    // Ensure the dropdown is properly configured for multi-select
    dropdown.setAttribute('multiple', 'multiple');
    dropdown.setAttribute('size', '5');

    // Add an option for each Process
    processes.forEach(process => {
        const option = document.createElement('option');
        option.value = process.process_id;
        option.textContent = `${process.process_id} - ${process.description}`;
        dropdown.appendChild(option);
    });

    if (!dropdown.hasAttribute('listener-attached')) {
        dropdown.addEventListener('change', handleProcessSelection);
        dropdown.setAttribute('listener-attached', 'true');
    }
}

function handleProcessSelection() {
    const selectedOptions = Array.from(document.getElementById('wafer_process_dropdown').selectedOptions);
    const timestampContainerWrapper = document.getElementById('timestampContainerWrapper');
    
    // Get currently selected process IDs
    const selectedProcessIds = selectedOptions.map(option => option.value);
    
    console.log('Selected Process IDs:', selectedProcessIds); // Debug log
    
    // First, handle the "no process selected" message
    let noProcessMessage = timestampContainerWrapper.querySelector('.no-process-message');
    
    if (selectedProcessIds.length === 0) {
        // Show "no process selected" message if no processes are selected
        if (!noProcessMessage) {
            noProcessMessage = document.createElement('p');
            noProcessMessage.className = 'no-process-message';
            noProcessMessage.style.color = 'gray';
            noProcessMessage.textContent = 'No process selected.';
            timestampContainerWrapper.appendChild(noProcessMessage);
        }
        
        // Remove all timestamp containers when no processes are selected
        const allContainers = timestampContainerWrapper.querySelectorAll('.timestamp-container');
        allContainers.forEach(container => container.remove());
        return;
    } else {
        // Remove "no process selected" message if processes are selected
        if (noProcessMessage) {
            noProcessMessage.remove();
        }
    }
    
    // Get existing timestamp containers and their process IDs
    const existingContainers = Array.from(timestampContainerWrapper.querySelectorAll('.timestamp-container'));
    const existingProcessIds = [];
    
    existingContainers.forEach(container => {
        const input = container.querySelector('.new-timestamp');
        if (input) {
            const processId = input.getAttribute('data-process-id');
            if (processId) {
                existingProcessIds.push(processId);
            }
        }
    });
    
    console.log('Existing Process IDs:', existingProcessIds); // Debug log

    // Remove containers for deselected processes
    existingContainers.forEach(container => {
        const input = container.querySelector('.new-timestamp');
        if (input) {
            const processId = input.getAttribute('data-process-id');
            if (processId && !selectedProcessIds.includes(processId)) {
                console.log('Removing container for process:', processId); // Debug log
                container.remove();
            }
        }
    });

    // Add containers for newly selected processes
    selectedProcessIds.forEach(processId => {
        if (!existingProcessIds.includes(processId)) {
            console.log('Adding container for process:', processId); // Debug log
            
            // Create a new container for each timestamp input
            const timestampContainer = document.createElement('div');
            timestampContainer.className = 'timestamp-container';

            const label = document.createElement('label');
            label.textContent = `Timestamp for Process ID ${processId}:`;
            timestampContainer.appendChild(label);

            const timestampInput = document.createElement('input');
            timestampInput.type = 'datetime-local';
            timestampInput.className = 'new-timestamp';
            timestampInput.setAttribute('data-process-id', processId);

            timestampContainer.appendChild(timestampInput);
            timestampContainerWrapper.appendChild(timestampContainer);
        }
    });
}

function showProcessInfo() {
    const processInforUrl = `${STATIC_BASE_URL}process_views.html`; 
    window.open(processInforUrl, "_blank");
}

async function postBatchData() {
    const loader = document.getElementById('loader');
    loader.style.display = 'block';
    const batchData = {
        batch_location: document.getElementById('batch_location').value,
        batch_id: document.getElementById('batch_id').value,
        total_wafers: document.getElementById('total_wafers').value,
        total_sensors: document.getElementById('total_sensors').value,
        batch_label: document.getElementById('batch_label').value,
        batch_description: document.getElementById('batch_description').value,
        wafer_label: document.getElementById('wafer_label').value,
        wafer_description: document.getElementById('wafer_description').value,
        wafer_designID: document.getElementById('wafer_design_id').value,
        sensor_description: document.getElementById('sensor_description').value,
    };

    // Collect all selected process IDs and their timestamps
    let processes = []
    const timestampInputs = document.querySelectorAll('.new-timestamp');
    timestampInputs.forEach(input => {
        const processId = input.getAttribute('data-process-id');
        const localTimestamp = input.value;

        const utcTimestamp = new Date(localTimestamp).toISOString();

        processes.push({ process_id: processId, description: allProcesses[processId] || "", timestamp: utcTimestamp });
    });

    batchData['sensor_processes'] = processes.length > 0 ? processes : [];

    console.log('Batch Data:', JSON.stringify(batchData));

    try {
        const response = await fetch(v2BatchEncoderAPI, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Token ${token}`,
                'X-CSRFToken': csrftoken,
            },
            body: JSON.stringify(batchData)
        });

        // FIXED: Read response once and handle both success and error cases
        const responseData = await response.json();
        console.log('Response Data: ', responseData);

        if (!response.ok) {
            // Handle error response
            console.error('HTTP error details: ', response.status, responseData);
            const errorMessage = responseData.error || responseData.message || 'Unknown error occurred';
            document.getElementById('error-output').textContent = `Error: ${errorMessage}`;
            
            // Show details if available
            if (responseData.details) {
                console.error('Error details:', responseData.details);
            }
            
            throw new Error(`HTTP error! Status: ${response.status} - ${errorMessage}`);
        } else {
            // Handle success response
            document.getElementById('error-output').innerText = 'Batch created successfully!';
            document.getElementById('error-output').style.color = 'green';
            
            // Show creation details if available
            if (responseData.details) {
                console.log('Creation details:', responseData.details);
                const detailsText = `Created ${responseData.details.sensors_created} sensors and ${responseData.details.image_groups_created} image groups`;
                document.getElementById('error-output').innerText += `\n${detailsText}`;
            }
            
            alert('Batch created successfully!');
            
            // Optional: Don't reload immediately, let user see the success message
            setTimeout(() => {
                window.location.reload();
            }, 2000);
        }
    } catch (error) {
        console.error('Error posting data: ', error);
        document.getElementById('error-output').innerText = 'Error: ' + error.message;
        document.getElementById('error-output').style.color = 'red';
    } finally {
        loader.style.display = 'none';
    }
}


window.addEventListener('DOMContentLoaded', function() {
    retrieveProcesses();
});

document.querySelector('.info-icon').addEventListener('click', showProcessInfo);

document.getElementById('postBatchData').addEventListener('click', postBatchData);

document.getElementById('loader').style.display = 'none';
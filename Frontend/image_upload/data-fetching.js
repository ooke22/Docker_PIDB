/**
 * Navigates the user to the process views page upon click
 */
export function showProcessInfo() {
    const processInfoUrl = "../process_views/process_views.html";
    window.open(processInfoUrl, "_blank");
}


/**
 * Fetches the processes and displays list in a dropdown menu
 */
export let processList = [];

export async function processDropdown() {
    const processInput = document.getElementById('processInput');
    const dropdownMenu = document.getElementById('processDropdown');

    try {
        const res = await fetch('http://127.0.0.1:8000/process-test/get_processes/', {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            }
        });
        if (!res.ok) {
            const errorText = await res.text();
            console.error('HTTP error', res.status, errorText);
            throw new Error('Unable to fetch processes');
        }
        processList = await res.json();
        console.log('Processes', processList);
    } catch (err) {
        console.error('Failed to fetch processes:', err);
        return;
    }

    processInput.addEventListener('input', () => {
        renderProcessDropdown(processInput.value);
    });

    processInput.addEventListener('focus', () => {
        renderProcessDropdown(processInput.value);  // Ensure it's shown even on first click
    });

    document.addEventListener('click', function (event) {
        if (!dropdownMenu.contains(event.target) && event.target !== processInput) {
            dropdownMenu.style.display = 'none';
        }
    });
}


function renderProcessDropdown(query = '') {
    const dropdownMenu = document.getElementById('processDropdown');
    const processInput = document.getElementById('processInput');

    dropdownMenu.innerHTML = '';
    const filtered = processList.filter(p =>
        p.process_id.toLowerCase().includes(query.toLowerCase())
    );

    filtered.forEach(p => {
        const div = document.createElement('div');
        div.textContent = `${p.process_id} - ${p.description}`;
        div.className = 'dropdown-item';
        div.onclick = () => {
            processInput.value = p.process_id;
            dropdownMenu.innerHTML = '';
        };
        dropdownMenu.appendChild(div);
    });
    dropdownMenu.style.display = 'block';
}


import { getCookie } from "../shared/utils.js";
const csrftoken = getCookie('csrftoken');
/**
 * Fetches the sensor uids from the backend and displays list in a dropdown menu
 */
export let sensorIDs = [];

export async function fetchSensors() {
    const sensorBox = document.getElementById('electrodeBox');
    const dropdown = document.createElement('select');
    dropdown.className = 'dropdown';

    try {
        const res = await fetch('http://127.0.0.1:8000/batch-encoder/u_id-dropdown/', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer: ${localStorage.getItem('token')}`,
                //'X-CSRFTokken': csrftoken
            }
        });
        sensorIDs = await res.json();
    } catch (err) {
        console.error('Failed to fetch sensors', err);
        return;
    }

    sensorIDs.forEach(id => {
        const option = document.createElement('option');
        option.value = id;
        option.textContent = id;
        dropdown.appendChild(option);
    });
    sensorBox.appendChild(dropdown);
}

window.addEventListener('DOMContentLoaded', processDropdown());
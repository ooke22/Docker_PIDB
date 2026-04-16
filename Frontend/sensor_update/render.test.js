// render.test.js
import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  renderResults,
  createUpdateTable,
  populateProcessDropdown,
  handleProcessSelection,
  populateProcessDetails,
  addProcesstoTable,
  highlightSelectedProcess
} from './render.js';

// Minimal HTML mock setup for DOM functions
beforeEach(() => {
  document.body.innerHTML = `
    <section id="validSensors" style="display: none;"></section>
    <div id="validated-sensors-container"></div>

    <table id="updateTable">
    <thead>
        <tr>
            <th>Field</th>
            <th>Update</th>
            <th>Value</th>
        </tr>
    </thead>
    <tbody></tbody>
    </table>

    <div id="processList"></div>

    <!-- Needed by populateProcessDetails -->
    <table>
      <tbody id="processTableBody"></tbody>
    </table>

    <!-- Needed by handleProcessSelection -->
    <div id="selectedProcessContainer"></div>
  `;
});


const mockSensors = [
  { unique_identifier: 'M001-01-001', label: 'TestLabel', description: 'TestDesc', process_ids: [] },
  { unique_identifier: 'M001-01-002', label: 'TestLabel2', description: 'TestDesc2', process_ids: [] },
];

const mockProcesses = [
  { process_id: 'proc1', description: 'Process One' },
  { process_id: 'proc2', description: 'Process Two' }
];

describe('render.js integration tests', () => {
  beforeEach(() => {
    document.querySelector('#validated-sensors-container').innerHTML = '';
    document.querySelector('#validSensors').style.display = 'none';
    document.querySelector('#updateTable tbody').innerHTML = '';
    document.querySelector('#processList').innerHTML = '';
  });

  it('renderResults displays sensor data and shows validSensors section', () => {
    renderResults(mockSensors);
    expect(document.querySelector('#validSensors').style.display).toBe('block');
    expect(document.querySelectorAll('#validated-sensors-container table tbody td').length).toBe(2);
  });

  it('createUpdateTable generates dropdowns for each sensor', () => {
    createUpdateTable([{ name: 'LabelA' }, { name: 'LabelB' }]);
    expect(document.querySelectorAll('#updateTable tbody tr').length).toBeGreaterThan(0);
    expect(document.querySelectorAll('select').length).toBeGreaterThan(0);
  });

  it('populateProcessDropdown renders clickable items', () => {
    populateProcessDropdown(mockProcesses);
    const items = document.querySelectorAll('#processList .process-item');
    expect(items.length).toBe(2);
    expect(items[0].textContent).toContain('Process One');
  });

  it('handleProcessSelection adds a datetime input and an "Add" button', () => {
    handleProcessSelection('proc1', mockProcesses);
    const container = document.getElementById('selectedProcessContainer');
    expect(container.querySelector('.selected-process')).not.toBeNull();
    expect(container.querySelector('input.new-timestamp')).not.toBeNull();
   expect(container.querySelector('button').textContent).toBe('Add');
  });

  it('populateProcessDetails renders grouped sensor table rows', () => {
    populateProcessDetails(mockSensors);
    expect(document.querySelectorAll('tr').length).toBeGreaterThan(0);
  });

  it('highlightSelectedProcess toggles the selected class', () => {
    const div = document.createElement('div');
    div.classList.add('process-item');
    document.body.appendChild(div);
    highlightSelectedProcess(div);
    expect(div.classList.contains('highlighted')).toBe(true);
  });
});

let searchResults = localStorage.getItem('searchResults');
console.log(searchResults);

if (searchResults) {
    searchResults = JSON.parse(searchResults);
    console.log('Processes', searchResults.process_summary.processes);
    const resultsDiv = document.querySelector('.Results');

    function createTimelineItem(title, content) {
        const timelineItem = document.createElement('div');
        timelineItem.classList.add('timeline-item');

        const contentDiv = document.createElement('div');
        contentDiv.classList.add('timeline-content');
        contentDiv.innerHTML = `<h3>${title}</h3>${content}`;

        timelineItem.appendChild(contentDiv);

        return timelineItem;
    }

    let identifier = `
        <strong>${searchResults.sensor_info.unique_identifier}</strong>
    `;

    let batchContent = `
        <strong>Batch Location:</strong> ${searchResults.sensor_info.batch_location || 'N/A'}<br><br>
        <strong>Batch ID:</strong> ${searchResults.sensor_info.batch_id || 'N/A'}<br><br>
        <strong>Batch Label:</strong> ${searchResults.sensor_info.batch_label || 'N/A'}<br><br>
        <strong>Batch Description:</strong> ${searchResults.sensor_info.batch_description || 'N/A'}
    `;

    let waferContent = `
        <strong>Wafer ID:</strong> ${searchResults.sensor_info.wafer_id || 'N/A'}<br><br>
        <strong>Wafer Label:</strong> ${searchResults.sensor_info.wafer_label || 'N/A'}<br><br>
        <strong>Wafer Description:</strong> ${searchResults.sensor_info.wafer_description || 'N/A'}<br><br>
    `;

    let sensorContent = `
        <strong>Sensor ID:</strong> ${searchResults.sensor_info.sensor_id || 'N/A'}<br><br>
        <strong>Sensor Label:</strong> ${searchResults.sensor_info.sensor_label || 'N/A'}<br><br>
        <strong>Sensor Description:</strong> ${searchResults.sensor_info.sensor_description || 'N/A'}
    `;

    let processContent = '';
    if (Array.isArray(searchResults.process_summary.processes)) {
        const processTable = document.createElement('table');
        processTable.style.width = '100%';
        processTable.style.borderCollapse = 'collapse';

        const thead = processTable.createTHead();
        const headerRow = thead.insertRow();
        const headerCells = ['Process ID', 'Description', 'Timestamp'];

        headerCells.forEach(header => {
            const th = document.createElement('th');
            th.style.border = '1px solid #000';
            th.textContent = header;
            headerRow.appendChild(th);
        });

        const tbody = processTable.createTBody();
        searchResults.process_summary.processes.forEach(process => {
            const row = tbody.insertRow();
            const processIDCell = row.insertCell(0);
            const descriptionCell =row.insertCell(1);
            const timeStampCell = row.insertCell(2);

            processIDCell.textContent = process.process_id;
            descriptionCell.textContent = process.description;
            timeStampCell.textContent = new Date(process.timestamp).toLocaleString();

            processIDCell.style.border = '1px solid #000';
            descriptionCell.style.border = '1px solid #000';
            timeStampCell.style.border = '1px solid #000';
        });

        processContent = processTable.outerHTML;
    }

    let imagesContent = '';
    if (Array.isArray(searchResults.sensor_info.images)) {
        searchResults.images.forEach(imageObj => {
            const correctedImageUrl = imageObj.image.replace('https//', 'https://');
            imagesContent += `<div id="imageContainer"><img src="${correctedImageUrl}" alt="Electrode Image"></div>`;
        });
    }

    resultsDiv.appendChild(createTimelineItem('Sensor', identifier));
    resultsDiv.appendChild(createTimelineItem('Batch Information', batchContent));
    resultsDiv.appendChild(createTimelineItem('Wafer Details', waferContent));
    resultsDiv.appendChild(createTimelineItem('Sensor Details', sensorContent));
    resultsDiv.appendChild(createTimelineItem('Processes', processContent));
    resultsDiv.appendChild(createTimelineItem('Images', imagesContent));
} else {
    console.error('No search results found in local storage');
}
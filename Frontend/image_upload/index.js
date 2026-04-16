import { handleDrop, handleDragOver, processFiles } from "./fileHandler2.js";
import { fetchSensors, showProcessInfo } from "./data-fetching.js";
import { uploadImage } from "./uploader.js";

window.addEventListener('DOMContentLoaded', () => {
    // Fetch sensor list and populate dropdown
    fetchSensors();

    // Setup drag-and-drop area
    const dropArea = document.getElementById('dropArea');
    dropArea.addEventListener('dragover', handleDragOver);
    dropArea.addEventListener('drop', handleDrop);

    // Setup manual file input selection
    const imageInput = document.getElementById('imageFile');
    imageInput.addEventListener('change', () => {
        processFiles(imageInput.files, { append: true });
        imageInput.value = '';
    });

    // Clicking the label triggers file input
    const fileLabel = document.getElementById('fileLabel');
    fileLabel.addEventListener('click', () => {
        imageInput.click();
    });

    // Upload button
    const uploadBtn = document.getElementById('uploadBtn');
    uploadBtn.addEventListener('click', uploadImage);

    // Process info icon opens process view page
    const infoIcon = document.getElementById('processInfoIcon');
    infoIcon.addEventListener('click', showProcessInfo);
});

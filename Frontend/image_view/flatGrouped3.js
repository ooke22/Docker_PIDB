import { getCookie } from "../shared/utils.js";
const csrftoken = getCookie("csrftoken");
const BACKEND_BASE_URL = "http://127.0.0.1:8000";

let currentPage = 1;
let hasNextPage = true;
let allImages = [];
let modalImages = [];
let modalIndex = 0;

const modal = document.getElementById("imageModal");
const modalImg = document.getElementById("modalImage");
const modalFilename = document.getElementById("modalFilename");
const modalDownloadBtn = document.getElementById("modalDownloadBtn");
const downloadToast = document.getElementById("downloadToast");

// Download functionality
function downloadImage(downloadUrl, filename) {
if (!downloadUrl) {
    showToast("No download available for this image", "error");
    return;
}

try {
    const link = document.createElement('a');
    link.href = `${BACKEND_BASE_URL}${downloadUrl}`;
    link.download = filename || 'image';
    link.target = '_blank';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    showToast("Download started!", "success");
} catch (error) {
    console.error('Download failed:', error);
    showToast("Download failed", "error");
}
}

function showToast(message, type = "success") {
const toast = document.getElementById("downloadToast");
const icon = type === "success" ? "fas fa-check-circle" : "fas fa-exclamation-circle";
const bgColor = type === "success" ? "#28a745" : "#dc3545";

toast.innerHTML = `<i class="${icon}"></i><span>${message}</span>`;
toast.style.backgroundColor = bgColor;
toast.classList.add("show");

setTimeout(() => {
    toast.classList.remove("show");
}, 3000);
}

function openModal(images, index) {
modalImages = images;
modalIndex = index;
const current = images[index];
modalImg.src = `${BACKEND_BASE_URL}${current.image}`;
modalFilename.textContent = current.file_name || "Untitled";

// Update download button
modalDownloadBtn.onclick = () => {
    downloadImage(current.download_url, current.file_name);
};

// Disable download button if no download URL
if (!current.download_url) {
    modalDownloadBtn.style.opacity = "0.5";
    modalDownloadBtn.style.cursor = "not-allowed";
    modalDownloadBtn.title = "No original file available for download";
} else {
    modalDownloadBtn.style.opacity = "1";
    modalDownloadBtn.style.cursor = "pointer";
    modalDownloadBtn.title = "Download original file";
}

modal.style.display = "flex";
}

function closeModal() {
modal.style.display = "none";
}

// Make closeModal available globally
window.closeModal = closeModal;

document.getElementById("prevBtn").onclick = () => {
if (modalIndex > 0) {
    modalIndex--;
    const current = modalImages[modalIndex];
    modalImg.src = `${BACKEND_BASE_URL}${current.image}`;
    modalFilename.textContent = current.file_name || "Untitled";
    
    // Update download button
    modalDownloadBtn.onclick = () => {
    downloadImage(current.download_url, current.file_name);
    };
    
    if (!current.download_url) {
    modalDownloadBtn.style.opacity = "0.5";
    modalDownloadBtn.style.cursor = "not-allowed";
    } else {
    modalDownloadBtn.style.opacity = "1";
    modalDownloadBtn.style.cursor = "pointer";
    }
}
};

document.getElementById("nextBtn").onclick = () => {
if (modalIndex < modalImages.length - 1) {
    modalIndex++;
    const current = modalImages[modalIndex];
    modalImg.src = `${BACKEND_BASE_URL}${current.image}`;
    modalFilename.textContent = current.file_name || "Untitled";
    
    // Update download button
    modalDownloadBtn.onclick = () => {
    downloadImage(current.download_url, current.file_name);
    };
    
    if (!current.download_url) {
    modalDownloadBtn.style.opacity = "0.5";
    modalDownloadBtn.style.cursor = "not-allowed";
    } else {
    modalDownloadBtn.style.opacity = "1";
    modalDownloadBtn.style.cursor = "pointer";
    }
}
};

window.onclick = (e) => {
if (e.target === modal) closeModal();
};

window.addEventListener("keydown", (e) => {
if (modal.style.display === "flex") {
    if (e.key === "ArrowRight" && modalIndex < modalImages.length - 1) {
    document.getElementById("nextBtn").click();
    }
    if (e.key === "ArrowLeft" && modalIndex > 0) {
    document.getElementById("prevBtn").click();
    }
    if (e.key === "Escape") {
    closeModal();
    }
}
});

let filterSensor = "";
let filterProcess = "";

async function fetchImages(reset = false) {
const token = localStorage.getItem("token");
const params = new URLSearchParams({
    page: currentPage,
});

if (filterSensor) params.append("sensor", filterSensor);
if (filterProcess) params.append("process", filterProcess);

const res = await fetch(
    `${BACKEND_BASE_URL}/batch-encoder/images/?${params.toString()}`,
    {
    method: 'GET',
    headers: {
        Authorization: `Token ${token}`,
        "X-CSRFToken": csrftoken,
    },
    }
);

const data = await res.json();
console.log('Image Data', data);

if (reset) {
    allImages = data.results;
    document.getElementById("more").style.display = "block";
    hasNextPage = true;
} else {
    allImages = [...allImages, ...data.results];
}

if (!data.next) {
    hasNextPage = false;
    document.getElementById("more").style.display = "none";
}

console.log('All Images', allImages);
renderGroupedCards(allImages);
}

function groupImages(data) {
const grouped = {};
data.forEach((img) => {
    const sensor = img.sensor;
    const process = img.process_id || "Unspecified";
    if (!grouped[sensor]) grouped[sensor] = {};
    if (!grouped[sensor][process]) grouped[sensor][process] = [];
    grouped[sensor][process].push(img);
});
return grouped;
}

function renderGroupedCards(data) {
const container = document.getElementById("batchSummary");
container.innerHTML = "";

const grouped = groupImages(data);
Object.entries(grouped).forEach(([sensorId, processes]) => {
    const card = document.createElement("div");
    card.className = "batch_card";
    const header = document.createElement("h2");
    header.textContent = `${sensorId}`;
    card.appendChild(header);

    Object.entries(processes).forEach(([procId, imgs]) => {
    const toggle = document.createElement("div");
    toggle.className = "process-toggle";
    toggle.textContent = `Process ID: ${procId}`;

    const imgContainer = document.createElement("div");
    imgContainer.className = "image-grid hidden";

    imgs.forEach((img, index) => {
        // Create image container with hover menu
        const imageContainer = document.createElement("div");
        imageContainer.className = "image-container";

        const imgEl = document.createElement("img");
        imgEl.loading = 'lazy';
        imgEl.src = `${BACKEND_BASE_URL}${img.image}`;
        imgEl.alt = img.file_name;
        imgEl.className = "image-thumb";
        imgEl.onclick = () => openModal(imgs, index);

        // Create hover menu
        const hoverMenu = document.createElement("div");
        hoverMenu.className = "image-hover-menu";
        
        const downloadBtn = document.createElement("button");
        downloadBtn.className = "hover-download-btn";
        downloadBtn.innerHTML = '<i class="fas fa-download"></i> Download';
        downloadBtn.onclick = (e) => {
        e.stopPropagation(); // Prevent modal from opening
        downloadImage(img.download_url, img.file_name);
        };

        // Disable if no download URL
        if (!img.download_url) {
        downloadBtn.style.opacity = "0.5";
        downloadBtn.style.cursor = "not-allowed";
        downloadBtn.title = "No original file available";
        downloadBtn.onclick = null;
        }

        hoverMenu.appendChild(downloadBtn);
        imageContainer.appendChild(imgEl);
        imageContainer.appendChild(hoverMenu);
        imgContainer.appendChild(imageContainer);
    });

    toggle.onclick = () => {
        imgContainer.classList.toggle("hidden");
    };

    card.appendChild(toggle);
    card.appendChild(imgContainer);
    });

    container.appendChild(card);
});
}

document.getElementById("searchBar").addEventListener("input", (e) => {
const query = e.target.value.trim();
const lower = query.toLowerCase();

// Clear both filters first
filterSensor = "";
filterProcess = "";

if (/^sp\d{3}$/i.test(lower)) {
    // Looks like a process ID
    filterProcess = query.toUpperCase(); // preserve SP001 casing
} else {
    // Assume sensor ID
    filterSensor = query;
}

currentPage = 1;
hasNextPage = true;
fetchImages(true);
});

document.querySelectorAll(".filter-pill").forEach((pill) => {
pill.addEventListener("click", (e) => {
    document.querySelectorAll(".filter-pill").forEach(p => p.classList.remove("active"));
    e.target.classList.add("active");

    const val = e.target.dataset.filter;
    filterProcess = val === "all" ? "" : val;
    currentPage = 1;
    hasNextPage = true;
    fetchImages(true);
});
});

document.getElementById("clearSearch").addEventListener("click", () => {
document.getElementById("searchBar").value = "";
filterSensor = "";
currentPage = 1;
hasNextPage = true;
fetchImages(true);
});

document.getElementById("more").addEventListener("click", () => {
if (hasNextPage) {
    currentPage++;
    fetchImages();
}
});

window.addEventListener("DOMContentLoaded", fetchImages);
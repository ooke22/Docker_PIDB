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

const modalDownload = document.getElementById("modalDownload");

function openModal(images, index) {
  modalImages = images;
  modalIndex = index;
  const current = images[index];

  modalImg.src = `${BACKEND_BASE_URL}${current.image}`;
  modalFilename.textContent = current.file_name || "Untitled";

  // Build absolute download URL
  const dlUrl = current.download_url
    ? `${BACKEND_BASE_URL}${current.download_url}`
    : `${BACKEND_BASE_URL}${current.image}`;

  modalDownload.setAttribute("href", dlUrl);
  modalDownload.setAttribute("target", "_blank"); // ensures browser handles file directly
  modalDownload.removeAttribute("download");      // let the backend headers control download
  modal.style.display = "flex";
}

function closeModal() {
  modal.style.display = "none";
}

document.getElementById("prevBtn").onclick = () => {
  if (modalIndex > 0) {
    modalIndex--;
    const current = modalImages[modalIndex];
    modalImg.src = `${BACKEND_BASE_URL}${current.image}`;
    modalFilename.textContent = current.file_name || "Untitled";
    modalDownload.href = current.download_url
      ? `${BACKEND_BASE_URL}${current.download_url}`
      : `${BACKEND_BASE_URL}${current.image}`;
  }
};

document.getElementById("nextBtn").onclick = () => {
  if (modalIndex < modalImages.length - 1) {
    modalIndex++;
    const current = modalImages[modalIndex];
    modalImg.src = `${BACKEND_BASE_URL}${current.image}`;
    modalFilename.textContent = current.file_name || "Untitled";
    modalDownload.href = current.download_url
      ? `${BACKEND_BASE_URL}${current.download_url}`
      : `${BACKEND_BASE_URL}${current.image}`;
  }
};


window.onclick = (e) => {
  if (e.target === modal) closeModal();
};

window.addEventListener("keydown", (e) => {
  if (modal.style.display === "flex") {
    if (e.key === "ArrowRight" && modalIndex < modalImages.length - 1) {
      modalIndex++;
      const current = modalImages[modalIndex];
      modalImg.src = `${BACKEND_BASE_URL}${current.image}`;
      modalFilename.textContent = current.file_name || "Untitled";
    }
    if (e.key === "ArrowLeft" && modalIndex > 0) {
      modalIndex--;
      const current = modalImages[modalIndex];
      modalImg.src = `${BACKEND_BASE_URL}${current.image}`;
      modalFilename.textContent = current.file_name || "Untitled";
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
    `${BACKEND_BASE_URL}/test/v3/view-images/?${params.toString()}`,
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
        const wrapper = document.createElement("div");
        wrapper.className = "thumb-wrapper";

        const imgEl = document.createElement("img");
        imgEl.loading = "lazy";
        imgEl.src = `${BACKEND_BASE_URL}${img.image}`;
        imgEl.alt = img.file_name;
        imgEl.className = "image-thumb";
        imgEl.onclick = () => openModal(imgs, index);

        const dlEl = document.createElement("a");
        const dlUrl = img.download_url
            ? `${BACKEND_BASE_URL}${img.download_url}`
            : `${BACKEND_BASE_URL}${img.image}`;

        dlEl.href = dlUrl;
        dlEl.target = "_blank"; // important
        dlEl.className = "thumb-download";
        dlEl.innerHTML = '<i class="fas fa-download"></i>';


        wrapper.appendChild(imgEl);
        wrapper.appendChild(dlEl);
        imgContainer.appendChild(wrapper);
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

function filterImages(query) {
  const lower = query.toLowerCase();
  const filtered = allImages.filter(
    (img) =>
      img.sensor.toLowerCase().includes(lower) ||
      (img.process_id && img.process_id.toLowerCase().includes(lower))
  );
  renderGroupedCards(filtered);
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

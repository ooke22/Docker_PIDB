// @shared/imageSection.js
import { formatDate } from "../shared/utils.js";
import { openImageModal } from "./image_modal.js";

/**
 * Renders the images section for the given search results.
 * @param {HTMLElement} container - The DOM element to render images into
 * @param {Object} imagesByProcess - Dictionary of processId -> { images: [], count: number }
 */
export function renderImageSection(container, imagesByProcess) {
    if (!container) return;

    if (!imagesByProcess || Object.keys(imagesByProcess).length === 0) {
        container.innerHTML = emptyStateHTML();
        return;
    }

    let html = "";

    Object.keys(imagesByProcess).forEach(processId => {
        const processData = imagesByProcess[processId];
        if (!processData || !Array.isArray(processData.images) || processData.images.length === 0) {
            return;
        }

        html += `
            <div class="process-images-section">
                <h4 class="process-images-header">
                    Process ${processId} (${processData.count} images)
                </h4>
                <div class="images-grid">
        `;

        processData.images.forEach((imageObj, index) => {
            const imageUrl = resolveImageUrl(imageObj.display_url);
            const uploadDate = formatDate(imageObj.upload_date);

            if (imageUrl) {
                html += `
                    <div class="image-card">
                        <div class="image-container">
                            <img 
                                src="${imageUrl}" 
                                alt="Process ${processId} - Image ${index + 1}"
                                class="image-thumb"
                                data-process="${processId}"
                                data-index="${index}"
                            >
                        </div>
                        <div class="image-info">
                            <div class="info-row">
                                <span class="info-label">File:</span>
                                <span class="info-value">${imageObj.file_name || "Unknown"}</span>
                            </div>
                            <div class="info-row">
                                <span class="info-label">Uploaded:</span>
                                <span class="info-value">${uploadDate}</span>
                            </div>
                        </div>
                    </div>
                `;
            }
        });

        html += `</div></div>`;
    });

    container.innerHTML = html;

    // Add interactivity
    attachImageEvents(container, imagesByProcess);
}

function resolveImageUrl(displayUrl) {
    if (!displayUrl) return "";
    return displayUrl.startsWith("/") 
        ? `http://127.0.0.1:8000${displayUrl}` 
        : displayUrl;
}

function attachImageEvents(container, imagesByProcess) {
    const images = container.querySelectorAll(".image-thumb");
    images.forEach(img => {
        img.addEventListener("mouseenter", () => {
            img.classList.add("hovered");
        });
        img.addEventListener("mouseleave", () => {
            img.classList.remove("hovered");
        });
        img.addEventListener("click", () => {
            const processId = img.dataset.process;
            const index = parseInt(img.dataset.index, 10);
            const processData = imagesByProcess[processId];

            // Map images into the { src, alt } format expected by openImageModal
            const modalImages = processData.images.map((imageObj, i) => ({
                src: resolveImageUrl(imageObj.display_url),
                alt: `Process ${processId} - Image ${i + 1}`
            }));

            openImageModal(modalImages, index);
        });
    });
}

function emptyStateHTML() {
    return `
        <div class="empty-state">
            <i class="fas fa-image"></i>
            <p>No images available for this sensor</p>
        </div>
    `;
}

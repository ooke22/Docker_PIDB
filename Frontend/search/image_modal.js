// @shared/imageModal.js

let modalImages = [];
let modalIndex = 0;

/**
 * Opens an image modal overlay with navigation controls
 * @param {string[]} images - Array of image objects { src, alt }
 * @param {number} startIndex - Index of the image to start with
 */
export function openImageModal(images, startIndex = 0) {
    modalImages = images;
    modalIndex = startIndex;

    const modal = document.createElement("div");
    modal.className = "image-modal-overlay";

    const modalContent = document.createElement("div");
    modalContent.className = "image-modal-content";

    const closeButton = document.createElement("button");
    closeButton.className = "modal-close-btn";
    closeButton.innerHTML = "×";

    const prevButton = document.createElement("button");
    prevButton.className = "modal-nav-btn modal-prev-btn";
    prevButton.innerHTML = "❮";

    const nextButton = document.createElement("button");
    nextButton.className = "modal-nav-btn modal-next-btn";
    nextButton.innerHTML = "❯";

    const modalImage = document.createElement("img");
    modalImage.className = "modal-image";

    function updateModal() {
        const current = modalImages[modalIndex];
        modalImage.src = current.src;
        modalImage.alt = current.alt || `Image ${modalIndex + 1}`;
    }

    function closeModal() {
        document.body.removeChild(modal);
        document.body.style.overflow = "auto";
        document.removeEventListener("keydown", handleKeydown);
    }

    function showPrev() {
        if (modalIndex > 0) {
            modalIndex--;
            updateModal();
        }
    }

    function showNext() {
        if (modalIndex < modalImages.length - 1) {
            modalIndex++;
            updateModal();
        }
    }

    function handleKeydown(e) {
        if (e.key === "Escape") closeModal();
        if (e.key === "ArrowLeft") showPrev();
        if (e.key === "ArrowRight") showNext();
    }

    closeButton.addEventListener("click", closeModal);
    prevButton.addEventListener("click", showPrev);
    nextButton.addEventListener("click", showNext);
    modal.addEventListener("click", closeModal);
    modalContent.addEventListener("click", (e) => e.stopPropagation());

    modalContent.appendChild(closeButton);
    modalContent.appendChild(prevButton);
    modalContent.appendChild(modalImage);
    modalContent.appendChild(nextButton);
    modal.appendChild(modalContent);
    document.body.appendChild(modal);

    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", handleKeydown);

    updateModal();
}

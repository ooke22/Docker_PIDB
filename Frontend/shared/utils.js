/**
 * CSRF Token
 */

export function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}


/**
 * Format a javascript Date object into `DD/MM/YY, hh:mm:ss AM/PM`.
 */

export function formatDate(date) {
    if (!(date instanceof Date)) date = new Date(date);
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const year = String(date.getFullYear()).slice(-2);
    const time = date.toLocaleTimeString();
    return `${day}/${month}/${year}, ${time}`;
}

export function getToken() {
    const token = localStorage.getItem('token');
    return token;
}

export function showToast(message, type = "info", duration = 4000) {
    // Create the container if it doesn’t exist
    let container = document.getElementById("toast-container");
    if (!container) {
        container = document.createElement("div");
        container.id = "toast-container";
        container.style.position = "fixed";
        container.style.top = "1rem";
        container.style.right = "1rem";
        container.style.zIndex = "9999";
        container.style.display = "flex";
        container.style.flexDirection = "column";
        container.style.gap = "0.5rem";
        document.body.appendChild(container);
    }

    // Create the toast
    const toast = document.createElement("div");
    toast.textContent = message;

    // Style it
    toast.style.padding = "12px 20px";
    toast.style.borderRadius = "8px";
    toast.style.fontSize = "14px";
    toast.style.color = "#fff";
    toast.style.boxShadow = "0 2px 6px rgba(0,0,0,0.2)";
    toast.style.cursor = "pointer";
    toast.style.opacity = "0";
    toast.style.transition = "opacity 0.3s ease";

    // Color scheme depending on type
    switch (type) {
        case "success":
            toast.style.backgroundColor = "#4CAF50"; // green
            break;
        case "error":
            toast.style.backgroundColor = "#f44336"; // red
            break;
        case "warning":
            toast.style.backgroundColor = "#ff9800"; // orange
            break;
        default:
            toast.style.backgroundColor = "#333"; // neutral
    }

    // Add to container
    container.appendChild(toast);

    // Trigger fade-in
    requestAnimationFrame(() => {
        toast.style.opacity = "1";
    });

    // Remove after duration
    const removeToast = () => {
        toast.style.opacity = "0";
        setTimeout(() => {
            toast.remove();
        }, 300);
    };

    // Auto-dismiss
    setTimeout(removeToast, duration);

    // Allow manual dismiss
    toast.addEventListener("click", removeToast);
}
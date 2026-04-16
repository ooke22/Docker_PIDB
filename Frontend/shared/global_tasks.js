// shared/global_tasks.js
// Global task listener with clean notification system

import notifications from './notifications.js';

// Track which tasks we've already shown start notifications for
const taskStartNotified = new Set();

// ------------------ Global Task WebSocket ------------------
export function initGlobalTaskListener() {
    // Prevent multiple connections
    if (window.__globalTasksSocket && window.__globalTasksSocket.readyState === WebSocket.OPEN) {
        console.log("[GlobalTasks] WebSocket already connected");
        return;
    }

    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const backendHost = window.location.hostname;
    const socket = new WebSocket(`${protocol}://${backendHost}:8000/ws/global-tasks/`);
    
    // Store socket reference globally to prevent duplicates
    window.__globalTasksSocket = socket;

    socket.onopen = () => {
        console.log("[GlobalTasks] Connected to WebSocket");
    };

    socket.onmessage = (event) => {
        try {
            const wsMsg = JSON.parse(event.data);
            const data = wsMsg.data || wsMsg;
            const { task_id, state, progress, message } = data;

            // Update progress bar if it exists on current page (for batch encoder page)
            updateProgressBar(task_id, progress);

            // Handle notifications - only show start and completion
            handleTaskNotification(task_id, state, progress, message);
            
        } catch (err) {
            console.error("[GlobalTasks] Error parsing WS message:", err);
        }
    };

    socket.onclose = (event) => {
        console.warn("[GlobalTasks] WebSocket closed. Code:", event.code);
        window.__globalTasksSocket = null;
        
        // Auto-reconnect only if it wasn't a clean close
        if (!event.wasClean) {
            console.log("[GlobalTasks] Reconnecting in 5s...");
            setTimeout(() => {
                taskStartNotified.clear();
                initGlobalTaskListener();
            }, 5000);
        }
    };

    socket.onerror = (err) => {
        console.error("[GlobalTasks] WebSocket error:", err);
        notifications.error("Connection error with task monitoring system");
    };
}

// Update progress bar if it exists on current page
function updateProgressBar(taskId, progress) {
    if (window.taskProgressBars && window.taskProgressBars[taskId] && progress !== undefined) {
        const task = window.taskProgressBars[taskId];
        task.progressBarEl.value = progress;
        task.progressTextEl.textContent = `${progress}%`;
    }
}

// Handle task notifications with clean logic
function handleTaskNotification(taskId, state, progress, message) {
    if (state === "STARTED") {
        notifications.info(message, { title: "Task Started" });
        return;
    }
    if (state === "SUCCESS") {
        notifications.success(message, { title: "Task Completed" });
        return;
    }
    if (state === "FAILURE") {
        notifications.error(`Batch processing task ${taskId} failed: ${message}`, {
            title: "Task Failed",
            duration: 10000
        });
        return;
    }
    if (state === "PROGRESS") {
        updateProgressBar(taskId, progress); // just visual, no duplicate notifications
    }
}

// ------------------ Auto Init ------------------
document.addEventListener("DOMContentLoaded", () => {
    // Only initialize once per page
    if (!window.__globalTasksInitialized) {
        window.__globalTasksInitialized = true;
        initGlobalTaskListener();
    }
});

// Export for manual use if needed
export { notifications };
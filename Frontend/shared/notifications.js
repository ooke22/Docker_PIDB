// shared/notifications.js
// Professional System-Style Notification Module

class NotificationSystem {
    constructor() {
        this.container = null;
        this.stylesInjected = false;
        this.maxNotifications = 3;
        this.defaultDuration = 8000;
        this.init();
    }

    init() {
        this.createContainer();
        this.injectStyles();
    }

    createContainer() {
        if (this.container) return;
        
        this.container = document.createElement('div');
        this.container.id = 'system-notification-container';
        this.container.className = 'notification-container';
        document.body.appendChild(this.container);
    }

    injectStyles() {
        if (this.stylesInjected || document.getElementById('notification-system-styles')) return;
        
        const style = document.createElement('style');
        style.id = 'notification-system-styles';
        style.textContent = `
            .notification-container {
                position: fixed;
                bottom: 20px;
                right: 20px;
                z-index: 10000;
                display: flex;
                flex-direction: column;
                gap: 10px;
                pointer-events: none;
            }

            .system-notification {
                min-width: 300px;
                max-width: 400px;
                padding: 16px 20px;
                border-radius: 8px;
                color: #fff;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                font-size: 14px;
                line-height: 1.4;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15), 0 2px 4px rgba(0, 0, 0, 0.1);
                border-left: 4px solid rgba(255, 255, 255, 0.3);
                backdrop-filter: blur(10px);
                transform: translateX(420px);
                transition: all 0.3s ease-out;
                pointer-events: auto;
                position: relative;
                overflow: hidden;
            }

            .system-notification.show {
                transform: translateX(0);
            }

            .system-notification.success {
                background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            }

            .system-notification.error {
                background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
            }

            .system-notification.info {
                background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
            }

            .system-notification.warning {
                background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
            }

            .notification-content {
                display: flex;
                align-items: flex-start;
                gap: 12px;
            }

            .notification-icon {
                background: rgba(255, 255, 255, 0.2);
                border-radius: 50%;
                width: 24px;
                height: 24px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: bold;
                flex-shrink: 0;
                margin-top: 1px;
            }

            .notification-text {
                flex: 1;
            }

            .notification-title {
                font-weight: 600;
                margin-bottom: 2px;
            }

            .notification-message {
                opacity: 0.95;
            }

            .notification-close {
                background: none;
                border: none;
                color: rgba(255, 255, 255, 0.7);
                font-size: 18px;
                cursor: pointer;
                padding: 0;
                width: 20px;
                height: 20px;
                display: flex;
                align-items: center;
                justify-content: center;
                border-radius: 50%;
                transition: all 0.2s ease;
                margin-top: 1px;
            }

            .notification-close:hover {
                background: rgba(255, 255, 255, 0.2);
            }

            .notification-progress {
                position: absolute;
                bottom: 0;
                left: 0;
                height: 3px;
                background: rgba(255, 255, 255, 0.3);
                width: 100%;
                transform-origin: left;
            }

            @keyframes progressBar {
                from { transform: scaleX(1); }
                to { transform: scaleX(0); }
            }

            .notification-progress.animate {
                animation: progressBar var(--duration) linear forwards;
            }
        `;
        document.head.appendChild(style);
        this.stylesInjected = true;
    }

    show(message, type = 'info', options = {}) {
        const {
            title,
            duration = this.defaultDuration,
            persistent = false,
            onClick
        } = options;

        const notification = this.createNotification(message, type, title, duration, persistent, onClick);
        this.addToContainer(notification);
        this.animateIn(notification);

        if (!persistent) {
            this.scheduleRemoval(notification, duration);
        }

        return notification;
    }

    createNotification(message, type, title, duration, persistent, onClick) {
        const notification = document.createElement('div');
        notification.className = `system-notification ${type}`;
        
        const config = this.getTypeConfig(type);
        
        notification.innerHTML = `
            <div class="notification-content">
                <div class="notification-icon">${config.icon}</div>
                <div class="notification-text">
                    <div class="notification-title">${title || config.title}</div>
                    <div class="notification-message">${message}</div>
                </div>
                <button class="notification-close" onclick="this.closest('.system-notification').remove()">×</button>
            </div>
            ${!persistent ? `<div class="notification-progress" style="--duration: ${duration}ms"></div>` : ''}
        `;

        if (onClick) {
            notification.style.cursor = 'pointer';
            notification.addEventListener('click', onClick);
        }

        return notification;
    }

    getTypeConfig(type) {
        const configs = {
            success: { icon: '✓', title: 'Success' },
            error: { icon: '✕', title: 'Error' },
            warning: { icon: '⚠', title: 'Warning' },
            info: { icon: 'ℹ', title: 'Information' }
        };
        return configs[type] || configs.info;
    }

    addToContainer(notification) {
        this.container.appendChild(notification);
        this.limitNotifications();
    }

    limitNotifications() {
        const notifications = this.container.children;
        while (notifications.length > this.maxNotifications) {
            this.removeNotification(notifications[0]);
        }
    }

    animateIn(notification) {
        requestAnimationFrame(() => {
            notification.classList.add('show');
            
            // Start progress bar animation if it exists
            const progressBar = notification.querySelector('.notification-progress');
            if (progressBar) {
                progressBar.classList.add('animate');
            }
        });
    }

    scheduleRemoval(notification, duration) {
        setTimeout(() => {
            this.removeNotification(notification);
        }, duration);
    }

    removeNotification(notification) {
        if (!notification.parentElement) return;
        
        notification.style.transform = 'translateX(420px)';
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 300);
    }

    // Convenience methods
    success(message, options = {}) {
        return this.show(message, 'success', options);
    }

    error(message, options = {}) {
        return this.show(message, 'error', options);
    }

    warning(message, options = {}) {
        return this.show(message, 'warning', options);
    }

    info(message, options = {}) {
        return this.show(message, 'info', options);
    }

    // Clear all notifications
    clear() {
        if (this.container) {
            this.container.innerHTML = '';
        }
    }

    // Update configuration
    setMaxNotifications(max) {
        this.maxNotifications = max;
    }

    setDefaultDuration(duration) {
        this.defaultDuration = duration;
    }
}

// Create singleton instance
const notifications = new NotificationSystem();

// Export both the instance and individual methods for convenience
export default notifications;
export const { success, error, warning, info, show, clear } = notifications;
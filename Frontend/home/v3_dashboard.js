import { formatDate } from "../shared/utils.js";

class DashboardWebSocket {
    constructor() {
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectInterval = 3000;
        this.isConnecting = false;
    }

    connect() {
        if (this.isConnecting || (this.ws && this.ws.readyState === WebSocket.OPEN)) {
            return;
        }

        this.isConnecting = true;
        
        // Show loading state
        this.showLoadingState();

        // Determine WebSocket protocol based on current page protocol
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const backendHost = window.location.hostname;
        const wsUrl = `${protocol}//${backendHost}:8000/ws/dashboard/`;
        
        try {
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = () => {
                console.log('Dashboard WebSocket connected');
                this.isConnecting = false;
                this.reconnectAttempts = 0;
                this.hideLoadingState();
            };

            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleMessage(data);
                } catch (error) {
                    console.error('Error parsing WebSocket message:', error);
                }
            };

            this.ws.onclose = (event) => {
                console.log('Dashboard WebSocket closed:', event.code, event.reason);
                this.isConnecting = false;
                this.ws = null;
                
                // Attempt to reconnect if not a normal close
                if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
                    this.attemptReconnect();
                }
            };

            this.ws.onerror = (error) => {
                console.error('Dashboard WebSocket error:', error);
                this.isConnecting = false;
                this.showErrorState();
            };
            
        } catch (error) {
            console.error('Failed to create WebSocket connection:', error);
            this.isConnecting = false;
            this.showErrorState();
        }
    }

    attemptReconnect() {
        this.reconnectAttempts++;
        console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
        
        setTimeout(() => {
            this.connect();
        }, this.reconnectInterval);
    }

    handleMessage(data) {
        switch (data.type) {
            case 'dashboard_data':
                this.updateDashboard(data.data);
                break;
            case 'error':
                console.error('Dashboard WebSocket error:', data.message);
                this.showErrorMessage(data.message);
                break;
            case 'pong':
                // Handle ping-pong for connection health
                break;
            default:
                console.log('Unknown message type:', data.type);
        }
    }

    updateDashboard(data) {
        try {
            // Update core stats
            if (data.core_stats) {
                this.updateCoreStats(data.core_stats);
            }

            // Update recent activity
            if (data.recent_activity) {
                this.displayRecentActivity(data.recent_activity);
            }

            // Update latest batches
            if (data.latest_batches) {
                this.displayRecentBatches(data.latest_batches);
            }

            // Update process statistics
            if (data.processes_stats) {
                this.displayProcessStats(data.processes_stats);
            }

            console.log('Dashboard updated successfully');
        } catch (error) {
            console.error('Error updating dashboard:', error);
            this.showErrorMessage('Failed to update dashboard display');
        }
    }

    updateCoreStats(coreStats) {
        const elements = {
            'totalBatches': coreStats.total_batches,
            'totalWafers': coreStats.total_wafers,
            'totalSensors': coreStats.total_sensors,
            'totalProcesses': coreStats.total_processes,
            'batchesThisWeek': coreStats.batches_this_week
        };

        Object.entries(elements).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) {
                element.textContent = value;
                // Add a subtle animation to show the data has been updated
                element.style.opacity = '0.5';
                setTimeout(() => {
                    element.style.opacity = '1';
                }, 150);
            }
        });
    }

    displayRecentActivity(data) {
        const recentActElement = document.getElementById('recentAct');
        
        if (!recentActElement) return;
        
        if (!data) {
            recentActElement.innerHTML = '<p>No recent activity data available</p>';
            return;
        }
        
        const html = `
            <div class="activity-container">
                <div class="activity-item">
                    <span class="activity-label">Last Batch Created</span>
                    <div class="activity-value">
                        <div class="activity-primary">${data.last_batch?.identifier || 'N/A'}</div>
                        <div class="activity-timestamp">${formatDate(data.last_batch?.timestamp)}</div>
                    </div>
                </div>
                
                <div class="activity-item">
                    <span class="activity-label">Last Process Applied</span>
                    <div class="activity-value">
                        <div class="activity-primary">${data.last_process?.process_id || 'N/A'}</div>
                        <div class="activity-timestamp">${formatDate(data.last_process?.timestamp)}</div>
                    </div>
                </div>
                
                <div class="activity-item">
                    <span class="activity-label">Today's New Batches</span>
                    <div class="activity-value">
                        <div class="activity-primary activity-count">${data.today_batches || 0}</div>
                    </div>
                </div>
                
                <div class="activity-item activity-item-last">
                    <span class="activity-label">Active Celery Tasks</span>
                    <div class="activity-value activity-with-badge">
                        <div class="activity-primary">${data.active_celery_tasks || 0}</div>
                        <span class="status-badge status-running">Running</span>
                    </div>
                </div>
            </div>
        `;
        
        recentActElement.innerHTML = html;
    }

    displayRecentBatches(batches) {
        const recentBatchElement = document.getElementById('recentBatches');
        
        if (!recentBatchElement) return;

        if (!batches || !Array.isArray(batches) || batches.length === 0) {
            recentBatchElement.innerHTML = '<p>No recent batches available</p>';
            return;
        }

        // Function to determine status and time ago based on last process timestamp
        function getStatusAndTime(timestamp) {
            const now = new Date();
            const processTime = new Date(timestamp);
            const diffInHours = Math.floor((now - processTime) / (1000 * 60 * 60));
            const diffInDays = Math.floor(diffInHours / 24);
            
            let timeAgo, status, statusClass;
            
            if (diffInHours < 6) {
                timeAgo = `${diffInHours}h ago`;
                status = 'Processing';
                statusClass = 'status-processing';
            } else if (diffInDays === 1) {
                timeAgo = '1d ago';
                status = 'Complete';
                statusClass = 'status-complete';
            } else if (diffInDays >= 2) {
                timeAgo = `${diffInDays}d ago`;
                status = 'Pending QC';
                statusClass = 'status-pending';
            } else {
                timeAgo = `${diffInHours}h ago`;
                status = 'Processing';
                statusClass = 'status-processing';
            }
            
            return { timeAgo, status, statusClass };
        }

        const html = batches.map(batch => {
            const { timeAgo, status, statusClass } = getStatusAndTime(batch.last_process_timestamp);
            
            return `
                <div class="batch-item">
                    <div class="batch-content">
                        <div class="batch-info">
                            <div class="batch-title">
                                Batch ${batch.batch_location}${batch.batch_id.toString().padStart(3, '0')} - ${batch.batch_label}
                            </div>
                            <div class="batch-details">
                                ${batch.total_wafers} wafers, ${batch.total_sensors.toLocaleString()} sensors
                            </div>
                        </div>
                        <div class="batch-status">
                            <span class="status-badge ${statusClass}">${status}</span>
                            <span class="batch-timestamp">${timeAgo}</span>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
        
        recentBatchElement.innerHTML = `<div class="batch-container">${html}</div>`;
    }

    displayProcessStats(processStats) {
        const processesElement = document.getElementById('processes');
        
        if (!processesElement) return;

        if (!processStats) {
            processesElement.innerHTML = '<p>No process statistics available</p>';
            return;
        }

        const html = `
            <div class="process-stats-container">
                <!-- Process Overview -->
                <div class="stats-overview">
                    <div class="stat-item">
                        <span class="stat-label">Total Process Applications</span>
                        <div class="stat-value">${processStats.total_process_applications?.toLocaleString() || 0}</div>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Processes Applied</span>
                        <div class="stat-value">${processStats.unique_processes_applied || 0}</div>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Avg Processes/Sensor</span>
                        <div class="stat-value">${processStats.avg_processes_per_sensor || 0}</div>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Sensors Processed</span>
                        <div class="stat-value">${processStats.sensors_with_processes?.toLocaleString() || 0}</div>
                    </div>
                </div>

                <!-- Most Applied Processes -->
                <div class="section">
                    <h3>Most Applied Processes</h3>
                    <div class="process-list">
                        ${processStats.most_applied_processes?.map(process => `
                            <div class="process-item">
                                <div class="process-info">
                                    <div class="process-name">${process.process_id}</div>
                                    <div class="process-count">${process.applications.toLocaleString()} applications (${process.percentage}%)</div>
                                </div>
                                <div class="process-bar">
                                    <div class="process-bar-fill" style="width: ${process.percentage}%"></div>
                                </div>
                            </div>
                        `).join('') || '<p>No process data available</p>'}
                    </div>
                </div>

                <!-- Top Diverse Batches -->
                <div class="section">
                    <h3>Batches with Most Process Steps</h3>
                    <div class="batch-diversity-list">
                        ${processStats.top_diverse_batches?.map(batch => `
                            <div class="diversity-item">
                                <div class="diversity-info">
                                    <div class="batch-name">Batch ${batch.batch_identifier}</div>
                                    <div class="diversity-details">
                                        ${batch.unique_processes} unique processes • 
                                        ${batch.total_applications} applications • 
                                        ${batch.sensors_processed} sensors
                                    </div>
                                </div>
                                <div class="diversity-badge">${batch.unique_processes} processes</div>
                            </div>
                        `).join('') || '<p>No batch diversity data available</p>'}
                    </div>
                </div>
            </div>
        `;
        
        processesElement.innerHTML = html;
    }

    refreshDashboard() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'refresh_dashboard'
            }));
        } else {
            console.log('WebSocket not connected. Attempting to reconnect...');
            this.connect();
        }
    }

    showLoadingState() {
        // Add loading indicators to each section
        const sections = ['recentAct', 'recentBatches', 'processes'];
        sections.forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.innerHTML = '<div class="loading-spinner">Loading...</div>';
            }
        });

        // Show loading for core stats
        const coreStatElements = ['totalBatches', 'totalWafers', 'totalSensors', 'totalProcesses', 'batchesThisWeek'];
        coreStatElements.forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.textContent = '...';
            }
        });
    }

    hideLoadingState() {
        // Remove any loading states - this will be replaced by actual data
    }

    showErrorState() {
        const errorMessage = 'Unable to load dashboard data. Please refresh the page.';
        
        // Show error in activity section
        const recentActElement = document.getElementById('recentAct');
        if (recentActElement) {
            recentActElement.innerHTML = `<p class="error-message">${errorMessage}</p>`;
        }

        // Show error in batches section
        const recentBatchElement = document.getElementById('recentBatches');
        if (recentBatchElement) {
            recentBatchElement.innerHTML = `<p class="error-message">${errorMessage}</p>`;
        }

        // Show error in batches section
        const processesElement = document.getElementById('processes');
        if (processesElement) {
            processesElement.innerHTML = `<p class="error-message">${errorMessage}</p>`;
        }
    }

    showErrorMessage(message) {
        console.error('Dashboard error:', message);
        // You can implement a toast notification system here if desired
    }

    disconnect() {
        if (this.ws) {
            this.ws.close(1000, 'Normal close');
            this.ws = null;
        }
    }

    // Health check method
    ping() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: 'ping' }));
        }
    }
}

// Create and initialize the dashboard WebSocket
const dashboardWS = new DashboardWebSocket();

// Connect when the page loads
dashboardWS.connect();

// Optional: Add a refresh button handler
document.addEventListener('DOMContentLoaded', () => {
    const refreshButton = document.getElementById('refreshDashboard');
    if (refreshButton) {
        refreshButton.addEventListener('click', () => {
            dashboardWS.refreshDashboard();
        });
    }

    // Optional: Periodic health check
    setInterval(() => {
        dashboardWS.ping();
    }, 30000); // Ping every 30 seconds
});

// Clean up on page unload
window.addEventListener('beforeunload', () => {
    dashboardWS.disconnect();

});
// Export for potential external use
window.dashboardWS = dashboardWS;

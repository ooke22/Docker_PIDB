import { formatDate } from "../shared/utils.js";

async function dashboardCoreStats() {
    try {
        const res = await fetch('http://127.0.0.1:8000/batch-encoder/dashboard-core-stats/', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer: ${localStorage.getItem('token')}`
            }
        });

        if (!res.ok) {
            const errorText = await res.text();
            console.error('HTTP Error', res.status, errorText);
            throw new Error('Unable to fetch core stats.')
        }

        const coreStats = await res.json();
        console.log('Retrieved core stats', coreStats);

        // Populate Metrics
        document.getElementById("totalBatches").textContent = coreStats.total_batches;
        document.getElementById("totalWafers").textContent = coreStats.total_wafers;
        document.getElementById("totalSensors").textContent = coreStats.total_sensors;
        document.getElementById("totalProcesses").textContent = coreStats.avg_sensors_per_batch;
        document.getElementById("batchesThisWeek").textContent = coreStats.batches_this_week;
    } catch (err) {
        console.error('Failed to fetch core stats');
        throw err;
    } 
}

async function recentActivity() {
    try {
        const res = await fetch('http://127.0.0.1:8000/batch-encoder/dashboard-recent-activity/', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer: ${localStorage.getItem('token')}`
            }
        });
        
        if (!res.ok) {
            const errorText = await res.text();
            console.error('HTTP Error', res.status, errorText);
            throw new Error('Unable to fetch recent activity data');
        }
        
        const recentAct = await res.json();
        console.log('Recent Activity:', recentAct);
        
        // Display recent activity data
        displayRecentActivity(recentAct);
        
    } catch (err) {
        console.error('Failed to fetch recent activity:', err);
        // Display error message in the recent activity section
        document.getElementById('recentAct').innerHTML = '<p class="error-message">Unable to load recent activity data</p>';
    }
}

function displayRecentActivity(data) {
    const recentActElement = document.getElementById('recentAct');
    
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

async function latestBatches() {
    try {
        const res = await fetch('http://127.0.0.1:8000/batch-encoder/dashboard-latest-batches/', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer: ${localStorage.getItem('token')}`
            }
        });

        if (!res.ok) {
            const errorText = await res.text();
            console.error('HTTP error: ', res.status, errorText);
            throw new Error('Unable to fetch recent batches')
        }

        const batches = await res.json()
        console.log('Recent Batches:', batches);

        displayRecentBatches(batches);
    } catch (err) {
        console.error('Failed to fetch recent batches:', err);
        document.getElementById('recentBatches').innerHTML = '<p class="error-message">Unable to load recent batches</p>';
    }
}

function displayRecentBatches(batches) {
    const recentBatchElement = document.getElementById('recentBatches');

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

async function processesStats() {
    try {
        const res = await fetch('http://127.0.0.1:8000/batch-encoder/dashboard-process-stats/', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer: ${localStorage.getItem('token')}`
            }
        });

        if (!res.ok) {
            const errorText = await res.text();
            console.error('HTTP error: ', res.status, errorText);
            throw new Error('Unable to fetch recent batches')
        }

        const processStats = await res.json()
        console.log('Recent Batches:', processStats);

        displayProcessStats(processStats);
    } catch (err) {
        console.error('Failed to fetch recent processStats:', err);
    }
}

function displayProcessStats(processStats) {
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

// Initialize dashboard
dashboardCoreStats();
recentActivity();
latestBatches();
processesStats();
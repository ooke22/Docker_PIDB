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
        document.getElementById("totalErrors").textContent = coreStats.batches_this_week;
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
        document.getElementById('recentAct').innerHTML = '<p style="color: #e74c3c;">Unable to load recent activity data</p>';
    }
}

function displayRecentActivity(data) {
    const recentActElement = document.getElementById('recentAct');
    
    if (!data) {
        recentActElement.innerHTML = '<p>No recent activity data available</p>';
        return;
    }
    
    
    const html = `
        <div style="display: grid; gap: 1rem; margin-top: 1rem;">
            <div style="border-left: 4px solid #0073e6; padding-left: 1rem;">
                <h3 style="margin: 0 0 0.5rem 0; color: #0073e6;">Last Batch created: <strong>${data.last_batch?.identifier || 'N/A'}</strong></h3>
                <p><strong>ID:</strong> ${data.last_batch?.identifier || 'N/A'}</p>
                <p><strong>Label:</strong> ${data.last_batch?.label || 'N/A'}</p>
                <p><strong>Time:</strong> ${formatDate(data.last_batch?.timestamp)}</p>
            </div>
            
            <div style="border-left: 4px solid #27ae60; padding-left: 1rem;">
                <h3 style="margin: 0 0 0.5rem 0; color: #27ae60;">Last Process</h3>
                <p><strong>Process ID:</strong> ${data.last_process?.process_id || 'N/A'}</p>
                <p><strong>Sensor ID:</strong> ${data.last_process?.sensor_id || 'N/A'}</p>
                <p><strong>Time:</strong> ${formatDate(data.last_process?.timestamp)}</p>
            </div>
            
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: 1rem;">
                <div style="background: #f8f9fa; padding: 0.75rem; border-radius: 6px; text-align: center;">
                    <div style="font-size: 1.5rem; font-weight: bold; color: #0073e6;">${data.today_batches || 0}</div>
                    <div style="font-size: 0.9rem; color: #666;">Today's Batches</div>
                </div>
                <div style="background: #f8f9fa; padding: 0.75rem; border-radius: 6px; text-align: center;">
                    <div style="font-size: 1.5rem; font-weight: bold; color: #27ae60;">${data.active_celery_tasks || 0}</div>
                    <div style="font-size: 0.9rem; color: #666;">Active Tasks</div>
                </div>
            </div>
        </div>
    `;
    
    recentActElement.innerHTML = html;
}

// Initialize dashboard
dashboardCoreStats();
recentActivity();
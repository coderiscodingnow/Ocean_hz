const AdminApp = {
    async init() {
        console.log('Initializing Admin Dashboard...');

        // check auth
        if (sessionStorage.getItem('admin_logged_in') === 'true') {
            this.showDashboard();
        }
    },

    handleLogin(e) {
        e.preventDefault();
        const user = document.getElementById('admin-user').value.toLowerCase().trim();
        const pass = document.getElementById('admin-pass').value;

        if (user === 'admin' && pass === 'admin123') {
            sessionStorage.setItem('admin_logged_in', 'true');
            this.showDashboard();
        } else {
            alert('Invalid Credentials');
        }
    },

    async showDashboard() {
        // Hide login, show content
        const overlay = document.getElementById('login-overlay');
        if (overlay) overlay.style.display = 'none';

        const content = document.getElementById('admin-content');
        if (content) {
            content.style.filter = 'none';
            content.style.pointerEvents = 'all';
        }

        // Translation Support for Admin (Basic)
        if (window.TranslationManager) {
            const currentLang = localStorage.getItem('app_language') || 'en';
            if (currentLang !== 'en') {
                const header = document.querySelector('h2.section-title[style*="var(--error)"]');
                if (header) {
                    const TR = {
                        hi: '🚨 सक्रिय बचाव अभियान',
                        kn: '🚨 ಸಕ್ರಿಯ ರಕ್ಷಣಾ ಕಾರ್ಯಾಚರಣೆಗಳು'
                    };
                    if (TR[currentLang]) header.textContent = TR[currentLang];
                }
            }
        }

        // Load Data
        await this.loadPendingPosts();
        await this.loadSensorData();
        await this.loadSOSReports();
        await this.loadActiveSafetyAlerts();
    },

    async loadPendingPosts() {
        try {
            const response = await fetch(`${API_CONFIG.BASE_URL}/posts?limit=100`);
            const posts = await response.json();

            // Filter pending (not verified AND not rejected)
            const pending = posts.filter(p => !p.verified && !p.rejected);

            this.renderPending(pending);
        } catch (error) {
            console.error('Error loading posts:', error);
            const container = document.getElementById('pending-container');
            if (container) container.innerHTML = '<p class="text-center" style="color:var(--error)">Failed to load posts.</p>';
        }
    },

    renderPending(posts) {
        const container = document.getElementById('pending-container');
        if (!container) return;
        container.innerHTML = '';

        if (posts.length === 0) {
            container.innerHTML = '<div class="card"><p style="text-align:center; color:var(--text-muted); padding:20px;">No pending reports for verification.</p></div>';
            return;
        }

        posts.forEach(post => {
            const card = document.createElement('div');
            card.className = 'card post-card';
            card.style.marginBottom = '20px';

            const baseUrl = API_CONFIG.BASE_URL.replace('/api', '');

            // Helper to sanitize path (replace backslahes with forward slashes for URLs)
            const sanitize = (path) => path ? path.replace(/\\/g, '/') : '';

            const imageUrl = post.watermarked_image_path
                ? `${baseUrl}/${sanitize(post.watermarked_image_path)}`
                : (post.image_path ? `${baseUrl}/${sanitize(post.image_path)}` : 'https://placehold.co/600x400?text=No+Image');

            const hazardName = post.hazard_type.replace(/_/g, ' ').toUpperCase();

            // Ensure timestamp is treated as UTC
            const timeStr = new Date(post.timestamp.endsWith('Z') ? post.timestamp : post.timestamp + 'Z').toLocaleString();

            card.innerHTML = `
                <div style="display:flex; gap: 20px; flex-wrap: wrap;">
                    <img src="${imageUrl}" style="width: 200px; height: 150px; object-fit: cover; border-radius: 8px; background: #000;">
                    <div style="flex:1; min-width: 200px;">
                        <div style="display:flex; justify-content:space-between; margin-bottom: 10px;">
                            <h4 style="margin:0">${hazardName}</h4>
                            <span class="alert-severity ${post.severity}" style="font-size:0.8rem; padding: 2px 8px; border-radius: 4px;">${post.severity.toUpperCase()}</span>
                        </div>
                        <p style="margin-bottom: 10px; color: var(--text-color);">${post.description || 'No description provided.'}</p>
                        <p style="font-size:0.9rem; color: var(--text-muted); margin-bottom: 5px;">
                            <strong>📍 Location:</strong> ${post.location_name || `${post.latitude.toFixed(4)}, ${post.longitude.toFixed(4)}`}
                        </p>
                        <p style="font-size:0.8rem; color: var(--text-muted);">
                            <strong>🕒 Time:</strong> ${timeStr}
                        </p>
                        
                        <div style="margin-top: 10px; padding: 10px; background: rgba(255,255,255,0.05); border-radius: 6px; font-size: 0.9rem; border: 1px solid var(--border);">
                            <strong>🤖 AI Analysis:</strong> Confidence ${(post.ai_confidence * 100).toFixed(1)}%
                        </div>
                        
                        <div style="margin-top: 10px; padding: 10px; background: rgba(255,255,255,0.05); border-radius: 6px; font-size: 0.9rem; border: 1px solid ${post.ai_relevance_score < 50 ? 'var(--error)' : 'var(--border)'};">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
                                <strong>🎯 BLIP Relevance Score:</strong>
                                <span style="font-weight: bold; color: ${post.ai_relevance_score >= 70 ? 'var(--success)' : post.ai_relevance_score >= 50 ? 'var(--warning)' : 'var(--error)'};">
                                    ${post.ai_relevance_score ? post.ai_relevance_score.toFixed(1) : '0.0'}%
                                </span>
                            </div>
                            <div style="width: 100%; height: 8px; background: rgba(0,0,0,0.3); border-radius: 4px; overflow: hidden;">
                                <div style="width: ${post.ai_relevance_score || 0}%; height: 100%; background: ${post.ai_relevance_score >= 70 ? 'var(--success)' : post.ai_relevance_score >= 50 ? 'var(--warning)' : 'var(--error)'}; transition: width 0.3s;"></div>
                            </div>
                            ${post.ai_relevance_score < 50 ? `
                                <div style="margin-top: 8px; padding: 6px 10px; background: rgba(239, 68, 68, 0.15); border-left: 3px solid var(--error); border-radius: 4px;">
                                    <strong style="color: var(--error);">⚠️ WARNING:</strong> 
                                    <span style="color: var(--error); font-size: 0.85rem;">Low relevance score - Image may not match reported hazard category</span>
                                </div>
                            ` : ''}
                        </div>
                        
                        <div style="margin-top: 15px; display: flex; gap: 10px;">
                            <button onclick="AdminApp.verifyPost(${post.id}, true)" class="action-btn btn-verify">Verify / Approve</button>
                            <button onclick="AdminApp.verifyPost(${post.id}, false)" class="action-btn btn-reject">Reject</button>
                        </div>
                    </div>
                </div>
            `;
            container.appendChild(card);
        });
    },

    async verifyPost(postId, isApproved) {
        let reason = null;
        if (!isApproved) {
            reason = prompt("Please provide a reason for rejection:");
            if (reason === null) return; // User cancelled
        }

        try {
            // Find button to disable
            const btn = event.target;
            if (btn) {
                btn.textContent = 'Processing...';
                btn.disabled = true;
            }

            const response = await fetch(`${API_CONFIG.BASE_URL}/admin/posts/${postId}/status`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    verified: isApproved,
                    rejected: !isApproved,
                    rejection_reason: reason
                })
            });

            if (response.ok) {
                this.loadPendingPosts();
                this.loadSensorData(); // Update stats
            } else {
                alert('Failed to update status');
                if (btn) {
                    btn.disabled = false;
                    btn.textContent = isApproved ? 'Verify / Approve' : 'Reject';
                }
            }
        } catch (error) {
            console.error('Action failed:', error);
            alert('Network error');
        }
    },

    async loadSensorData() {
        try {
            const response = await fetch(`${API_CONFIG.BASE_URL}/admin/historical-data`);
            const data = await response.json();

            // Render Stats
            const statsDiv = document.getElementById('admin-stats');
            if (statsDiv) {
                statsDiv.innerHTML = `
                    <div class="card" style="flex:1">
                        <h3 style="font-size: 0.9rem; color: var(--text-muted); margin-bottom: 5px;">Total Reports</h3>
                        <p style="font-size:2rem; font-weight:bold; margin:0;">${data.stats.total_reports}</p>
                    </div>
                    <div class="card" style="flex:1">
                        <h3 style="font-size: 0.9rem; color: var(--text-muted); margin-bottom: 5px;">Verified</h3>
                        <div style="font-size:2rem; font-weight:bold; color:var(--success); margin:0;">${data.stats.verified}</div>
                    </div>
                    <div class="card" style="flex:1">
                        <h3 style="font-size: 0.9rem; color: var(--text-muted); margin-bottom: 5px;">Accuracy</h3>
                        <div style="font-size:2rem; font-weight:bold; color:var(--primary); margin:0;">${data.stats.accuracy_rate.toFixed(1)}%</div>
                    </div>
                `;
            }

            // Render Sensor Table
            const tbody = document.querySelector('#sensor-table tbody');
            if (tbody) {
                tbody.innerHTML = '';

                if (!data.sensor_data || data.sensor_data.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="3" style="text-align:center">No sensors available</td></tr>';
                } else {
                    data.sensor_data.forEach(sensor => {
                        const row = document.createElement('tr');
                        let color = 'var(--text-color)';
                        if (sensor.status === 'Operational') color = 'var(--success)';
                        else if (sensor.status === 'Offline') color = 'var(--error)';
                        else if (sensor.status === 'Maintenance') color = 'var(--warning)';

                        row.innerHTML = `
                            <td>
                                <div><strong>${sensor.id}</strong></div>
                                <div style="font-size:0.8rem; color:var(--text-muted)">${sensor.location}</div>
                            </td>
                            <td>${sensor.type}</td>
                            <td>
                                <div style="color:${color}; font-weight:bold">${sensor.status}</div>
                                <div style="font-size:0.8rem">${sensor.reading}</div>
                            </td>
                        `;
                        tbody.appendChild(row);
                    });
                }
            }

        } catch (error) {
            console.error('Error loading sensor data:', error);
        }
    },

    async loadSOSReports() {
        try {
            const container = document.getElementById('sos-container');
            if (!container) return;

            const response = await fetch(`${API_CONFIG.BASE_URL}/sos/reports?active_only=true`);
            const reports = await response.json();

            container.innerHTML = '';

            if (reports.length === 0) {
                container.innerHTML = '<div class="card"><p style="text-align:center; color:var(--text-muted); padding:10px;">No active SOS alerts</p></div>';
                return;
            }

            reports.forEach(sos => {
                const card = document.createElement('div');
                card.className = 'card post-card';
                card.style.borderColor = sos.deployed ? 'var(--success)' : 'var(--error)';
                card.style.marginBottom = '15px';

                if (sos.deployed) {
                    card.style.background = 'rgba(0, 255, 0, 0.05)';
                } else {
                    card.style.background = 'rgba(255, 0, 0, 0.05)';
                }

                card.innerHTML = `
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                        <h3 style="margin:0; color: ${sos.deployed ? 'var(--success)' : 'var(--error)'}">
                            ${sos.deployed ? '🚁 RECOVERY IN PROGRESS' : '🚨 SOS ALERT'}
                        </h3>
                        <span style="font-size:0.8rem;">${new Date(sos.timestamp + 'Z').toLocaleString()}</span>
                    </div>
                    
                    <div style="margin-bottom: 10px;">
                        <strong>Type:</strong> ${sos.emergency_type.toUpperCase()} <br>
                        <strong>Location:</strong> ${sos.location_name || `${sos.latitude}, ${sos.longitude}`} <br>
                        <strong>Contact:</strong> ${sos.contact_number || 'N/A'}
                    </div>

                    ${sos.description ? `<p style="font-style:italic">"${sos.description}"</p>` : ''}

                    ${sos.deployed ? `
                        <div style="margin-top:10px; padding:10px; background:rgba(0,0,0,0.2); border-radius:4px;">
                            <strong>Team Deployed:</strong> ${sos.deployed_by} <br>
                            <small>Notes: ${sos.rescue_notes || 'None'}</small>
                        </div>
                    ` : '<div style="color:var(--error); font-weight:bold;">⚠️ Waiting for Rescue Team Deployment</div>'}
                `;
                container.appendChild(card);
            });

        } catch (error) {
            console.error('Error loading SOS reports:', error);
        }
    },

    // --- Safety Alerts Logic ---
    async createSafetyAlert(e) {
        e.preventDefault();
        const form = e.target;
        const formData = new FormData(form);
        const statusDiv = document.getElementById('form-status');

        const data = {
            location_name: formData.get('location_name'),
            hazard_type: formData.get('hazard_type')
        };

        if (statusDiv) {
            statusDiv.style.display = 'block';
            statusDiv.style.background = 'rgba(255, 255, 255, 0.1)';
            statusDiv.style.color = 'var(--text-color)';
            statusDiv.textContent = 'Broadcasting...';
        }

        try {
            const response = await fetch(`${API_CONFIG.BASE_URL}/admin/safety-alerts`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            if (response.ok) {
                if (statusDiv) {
                    statusDiv.style.background = 'rgba(16, 185, 129, 0.2)';
                    statusDiv.style.color = '#10b981';
                    statusDiv.textContent = '✅ Alert Broadcasted Successfully!';
                }
                form.reset();
                this.loadActiveSafetyAlerts(); // Refresh list

                // Hide status after 3s
                setTimeout(() => { if (statusDiv) statusDiv.style.display = 'none'; }, 3000);

            } else {
                const err = await response.json();
                if (statusDiv) {
                    statusDiv.style.background = 'rgba(239, 68, 68, 0.2)';
                    statusDiv.style.color = '#ef4444';
                    statusDiv.textContent = '❌ Failed: ' + (err.detail || 'Unknown error');
                }
            }
        } catch (error) {
            console.error('Error creating alert:', error);
            if (statusDiv) {
                statusDiv.style.background = 'rgba(239, 68, 68, 0.2)';
                statusDiv.style.color = '#ef4444';
                statusDiv.textContent = '❌ Network Connection Error';
            }
        }
    },

    async loadActiveSafetyAlerts() {
        try {
            const container = document.getElementById('active-alerts-list');
            if (!container) return;

            const response = await fetch(`${API_CONFIG.BASE_URL}/safety-alerts`);
            const alerts = await response.json();

            container.innerHTML = '';

            if (alerts.length === 0) {
                container.innerHTML = '<p style="font-size:0.9rem; color:var(--text-muted);">No active alerts.</p>';
                return;
            }

            alerts.forEach(alert => {
                const item = document.createElement('div');
                item.style.padding = '10px';
                item.style.marginBottom = '10px';
                item.style.background = 'rgba(255,0,0,0.1)';
                item.style.borderRadius = '6px';
                item.style.border = '1px solid var(--error)';

                item.innerHTML = `
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <strong>🚫 ${alert.location_name}</strong><br>
                            <small style="color:var(--error);">Hazard: ${alert.hazard_type.toUpperCase()}</small>
                        </div>
                        <button onclick="AdminApp.deactivateAlert(${alert.id})" style="background:var(--surface); border:1px solid var(--border); color:white; padding:4px 8px; border-radius:4px; cursor:pointer;">End</button>
                    </div>
                `;
                container.appendChild(item);
            });

        } catch (error) {
            console.error('Error loading alerts:', error);
        }
    },

    async deactivateAlert(id) {
        if (!confirm('Deactivate this alert?')) return;
        try {
            await fetch(`${API_CONFIG.BASE_URL}/admin/safety-alerts/${id}/deactivate`, { method: 'PUT' });
            this.loadActiveSafetyAlerts();
        } catch (error) {
            console.error('Error deactivating:', error);
        }
    }
};


// Expose to window for onclick handlers
window.AdminApp = AdminApp;
document.addEventListener('DOMContentLoaded', () => AdminApp.init());

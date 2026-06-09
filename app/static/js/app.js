/* ════════════════════════════════════════════════════════════════
   GLOBAL UTILITIES — AJAX helpers, toasts, debounce, WebSocket, notifications
   ════════════════════════════════════════════════════════════════ */

// ─── Toast notifications ───
function showToast(message, type = 'info') {
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    // Add icon based on type
    let icon = 'info-circle';
    if (type === 'success') icon = 'check';
    if (type === 'error') icon = 'alert-circle';
    if (type === 'warning') icon = 'alert-triangle';
    
    toast.innerHTML = `<i class="ti ti-${icon}"></i> <span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('fade-out');
        setTimeout(() => toast.remove(), 400);
    }, 4000);
}

// ─── AJAX helper ───
async function api(url, options = {}) {
    const defaults = {
        headers: { 'Content-Type': 'application/json' },
    };
    const config = { ...defaults, ...options };

    try {
        const response = await fetch(url, config);
        const contentType = response.headers.get('content-type');
        
        let data = null;
        if (contentType && contentType.includes('application/json')) {
            data = await response.json();
        }

        if (!response.ok) {
            const errorMsg = (data && data.error) ? data.error : `Server error: ${response.status}`;
            showToast(errorMsg, 'error');
            console.error('API Error:', errorMsg, response.status);
            return null;
        }

        return data;
    } catch (err) {
        showToast('Network error. Please try again.', 'error');
        console.error('Fetch Error:', err);
        return null;
    }
}

// ─── Debounce ───
function debounce(fn, delay = 300) {
    let timer;
    return function (...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}

// ─── WebSocket connection ───
let socket = null;

function initSocket() {
    if (typeof io === 'undefined') return;
    socket = io();

    socket.on('connect', () => {
        console.log('🔌 Connected to WebSocket');
    });

    socket.on('notification', (data) => {
        handleNotification(data);
    });

    socket.on('disconnect', () => {
        console.log('❌ Disconnected from WebSocket');
    });
}

// ─── Notifications ───
function handleNotification(data) {
    const badge = document.getElementById('notif-count');
    if (badge) {
        let current = parseInt(badge.textContent) || 0;
        badge.textContent = current + 1;
        badge.style.display = 'flex';
        // Add animation class
        badge.classList.add('pulse');
        setTimeout(() => badge.classList.remove('pulse'), 1000);
    }

    let message = data.data.message || 'New notification received';
    let type = 'info';
    
    if (data.type === 'resume_ready') type = 'success';
    if (data.type === 'mentorship_requested') type = 'warning';
    if (data.type === 'mentorship_status_update') type = data.data.status === 'accepted' ? 'success' : 'error';
    if (data.type === 'referral_status_update') type = data.data.status === 'hired' ? 'success' : 'info';

    showToast(message, type);
    
    // Refresh lists if on specific pages
    if (window.location.pathname.includes('/mentorship/dashboard') && typeof loadRequests === 'function') loadRequests();
    if (window.location.pathname.includes('/referral') && typeof loadApplications === 'function') loadApplications();
}

async function loadNotificationCount() {
    const data = await api('/api/notifications/count');
    if (data) {
        const badge = document.getElementById('notif-count');
        if (badge && data.count > 0) {
            badge.textContent = data.count;
            badge.style.display = 'flex';
        }
    }
}

function toggleNotifications() {
    const panel = document.getElementById('notif-panel');
    if (panel.style.display === 'none' || !panel.style.display) {
        panel.style.display = 'block';
        loadNotifications();
    } else {
        panel.style.display = 'none';
    }
}

async function loadNotifications() {
    const data = await api('/api/notifications');
    const list = document.getElementById('notif-list');
    if (!data || !data.length) {
        list.innerHTML = '<div class="p-4 text-center text-muted text-xs">No notifications</div>';
        return;
    }

    list.innerHTML = data.map(n => `
        <div class="notif-panel-item ${n.is_read ? 'read' : 'unread'}" onclick="handleNotifClick(${n.id}, '${n.type}')">
            <div class="notif-icon-mini ${n.type}"><i class="ti ti-bell"></i></div>
            <div class="notif-body">
                <div class="notif-msg">${n.data_json.message || n.type}</div>
                <div class="notif-time-mini">${formatISTShort(n.created_at)}</div>
            </div>
            ${!n.is_read ? '<div class="unread-dot"></div>' : ''}
        </div>
    `).join('');
}

async function handleNotifClick(id, type) {
    await api('/api/notifications/read', {
        method: 'POST',
        body: JSON.stringify({ ids: [id] })
    });
    
    // Redirect based on type
    if (type.includes('mentorship')) window.location.href = '/mentorship/';
    else if (type.includes('referral')) window.location.href = '/referral/';
    else if (type.includes('resume')) window.location.href = '/resume/';
    else loadNotificationCount();
}

// ─── Global Search ───
function initGlobalSearch() {
    const input = document.getElementById('global-search');
    const results = document.getElementById('search-results');
    if (!input || !results) return;

    input.addEventListener('input', debounce(async (e) => {
        const q = e.target.value.trim();
        if (q.length < 2) { results.style.display = 'none'; return; }

        const data = await api(`/api/search/users?q=${encodeURIComponent(q)}`);
        if (!data || !data.length) { results.style.display = 'none'; return; }

        results.innerHTML = data.map(u => `
            <a href="/profile/${u.id}" class="dropdown-item d-flex align-items-center gap-3">
                <div class="user-avatar sm">${u.name[0]}</div>
                <div>
                    <div class="font-700 text-sm">${u.name}</div>
                    <div class="text-xs text-muted">@${u.username} · ${u.role}</div>
                </div>
            </a>
        `).join('');
        results.style.display = 'block';
    }, 300));
}

// ─── Initialize ───
document.addEventListener('DOMContentLoaded', () => {
    initSocket();
    loadNotificationCount();
    initGlobalSearch();
});

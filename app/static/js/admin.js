/* ════════ ADMIN JAVASCRIPT ════════ */

// ─── Users ───
async function loadUsers(page = 1) {
    const role = document.getElementById('filter-role')?.value || '';
    const status = document.getElementById('filter-status')?.value || '';
    const data = await api(`/admin/api/users?page=${page}&role=${role}&status=${status}`);
    if (!data) return;

    const tbody = document.getElementById('users-tbody');
    tbody.innerHTML = data.users.map(u => `
        <tr>
            <td><div class="d-flex align-center gap-1"><div class="user-avatar" style="width:28px;height:28px;font-size:11px;">${u.name ? u.name[0].toUpperCase() : u.username[0].toUpperCase()}</div><div><div style="font-weight:600;">${u.name || u.username}</div><div style="font-size:11px;color:var(--text-muted);">@${u.username}</div></div></div></td>
            <td>${u.email}</td>
            <td><span class="badge role-badge-${u.role}">${u.role}</span></td>
            <td><span class="badge ${u.is_active ? 'badge-success' : 'badge-danger'}">${u.is_active ? 'Active' : 'Inactive'}</span></td>
            <td style="font-size:var(--font-size-xs);color:var(--text-muted);">${new Date(u.created_at).toLocaleDateString()}</td>
            <td>
                <button class="btn btn-sm btn-secondary" onclick="toggleUserActive(${u.id})">${u.is_active ? 'Deactivate' : 'Activate'}</button>
            </td>
        </tr>
    `).join('');
}

async function toggleUserActive(userId) {
    const data = await api(`/admin/api/users/${userId}/toggle-active`, { method: 'POST' });
    if (data) { showToast('User status updated', 'success'); loadUsers(); }
}

// ─── Resumes ───
async function loadAdminResumes(page = 1) {
    const data = await api(`/admin/api/resumes?page=${page}`);
    if (!data) return;
    const tbody = document.getElementById('resumes-tbody');
    tbody.innerHTML = data.resumes.map(r => `
        <tr>
            <td>${r.user}</td>
            <td>${r.filename}</td>
            <td><span class="${r.score >= 70 ? 'text-success' : r.score >= 40 ? 'text-warning' : 'text-danger'}" style="font-weight:700;">${r.score}</span></td>
            <td><span class="badge ${r.status === 'completed' ? 'badge-success' : r.status === 'processing' ? 'badge-info' : 'badge-warning'}">${r.status}</span></td>
            <td style="font-size:var(--font-size-xs);">${new Date(r.created_at).toLocaleDateString()}</td>
        </tr>
    `).join('');
}

// ─── LLM Logs ───
async function loadLLMLogs(page = 1) {
    const data = await api(`/admin/api/llm-logs?page=${page}`);
    if (!data) return;
    const tbody = document.getElementById('llm-tbody');
    tbody.innerHTML = data.logs.map(l => `
        <tr>
            <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${l.prompt}">${l.prompt}</td>
            <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${l.response}">${l.response}</td>
            <td>${l.tokens}</td>
            <td>${l.duration_ms}ms</td>
            <td style="font-size:var(--font-size-xs);">${new Date(l.created_at).toLocaleString()}</td>
        </tr>
    `).join('');
}

// ─── Jobs Queue ───
async function loadJobsQueue(page = 1) {
    const status = document.getElementById('job-status-filter')?.value || '';
    const data = await api(`/admin/api/jobs-queue?page=${page}&status=${status}`);
    if (!data) return;
    const tbody = document.getElementById('jobs-tbody');
    tbody.innerHTML = data.jobs.map(j => `
        <tr>
            <td><span class="badge badge-primary">${j.event_type}</span></td>
            <td><span class="badge ${j.status === 'completed' ? 'badge-success' : j.status === 'failed' ? 'badge-danger' : 'badge-warning'}">${j.status}</span></td>
            <td>${j.retries}</td>
            <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;">${j.error || '—'}</td>
            <td style="font-size:var(--font-size-xs);">${new Date(j.created_at).toLocaleString()}</td>
        </tr>
    `).join('');
}

// ─── Audit Logs ───
async function loadAuditLogs(page = 1) {
    const data = await api(`/admin/api/audit-logs?page=${page}`);
    if (!data) return;
    const tbody = document.getElementById('audit-tbody');
    tbody.innerHTML = data.logs.map(l => `
        <tr>
            <td style="font-weight:600;">${l.actor}</td>
            <td><span class="badge badge-primary">${l.action}</span></td>
            <td>${l.target}</td>
            <td style="font-size:var(--font-size-xs);color:var(--text-muted);">${new Date(l.timestamp).toLocaleString()}</td>
        </tr>
    `).join('');
}

// ─── Model Weights ───
async function loadWeights() {
    const data = await api('/admin/api/weights');
    const editor = document.getElementById('weights-editor');
    if (!data || !editor) return;

    editor.innerHTML = data.map(w => `
        <div style="margin-bottom:var(--space-lg);">
            <h4 style="margin-bottom:var(--space-md);text-transform:capitalize;">${w.context.replace('_',' ')}</h4>
            <div class="weight-editor">
                ${Object.entries(w.weights).map(([k, v]) => `
                    <div class="weight-item">
                        <label>${k.replace('_',' ')}</label>
                        <input type="range" min="0.05" max="0.8" step="0.01" value="${v}" oninput="this.nextElementSibling.textContent=this.value">
                        <span class="weight-value">${v}</span>
                    </div>
                `).join('')}
            </div>
            <button class="btn btn-sm btn-primary mt-2" onclick="saveWeights(${w.id})">Save</button>
            <span style="font-size:var(--font-size-xs);color:var(--text-muted);margin-left:var(--space-md);">v${w.version}</span>
        </div>
    `).join('');
}

async function saveWeights(weightId) {
    const editor = document.getElementById('weights-editor');
    const items = editor.querySelectorAll('.weight-item');
    const weights = {};
    items.forEach(item => {
        const label = item.querySelector('label').textContent.replace(' ', '_');
        const value = parseFloat(item.querySelector('input').value);
        weights[label] = value;
    });

    const data = await api(`/admin/api/weights/${weightId}`, {
        method: 'PUT',
        body: JSON.stringify({ weights })
    });
    if (data) showToast('Weights saved!', 'success');
}

// ─── Recompute Rankings ───
async function recomputeRankings() {
    const data = await api('/admin/api/recompute-rankings', { method: 'POST' });
    if (data) showToast(data.message, 'success');
}

// Load weights on admin dashboard
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('weights-editor')) loadWeights();
});

let allJobs = [];

document.addEventListener('DOMContentLoaded', () => {
    // Determine which view we are in
    if (document.getElementById('jobs-list')) {
        loadJobs();
        loadApplications();
    }
    if (document.getElementById('my-jobs-list')) {
        loadMyJobs();
    }
});

function switchTab(tab) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    
    event.currentTarget.classList.add('active');
    document.getElementById(`${tab}-tab`).classList.add('active');
}

// ─── Student Functions ───
async function loadJobs() {
    const data = await api('/referral/api/jobs');
    if (!data) return;
    allJobs = data;
    renderJobs(data);
}

function renderJobs(jobs) {
    const list = document.getElementById('jobs-list');
    if (!list) return;
    if (jobs.length === 0) {
        list.innerHTML = '<p class="text-center py-5 text-muted">No open positions found.</p>';
        return;
    }

    list.innerHTML = jobs.map(j => `
        <div class="job-card">
            <div class="job-main">
                <span class="job-badge">${j.type}</span>
                <h3 class="job-title">${j.title}</h3>
                <div class="job-meta">
                    <span><i class="ti ti-building"></i> ${j.company}</span>
                    <span><i class="ti ti-map-pin"></i> ${j.location || 'Remote'}</span>
                </div>
            </div>
            <div class="job-skills">
                ${j.skills.map(s => `<span class="mini-skill">${s}</span>`).join('')}
            </div>
            <div class="mt-4 pt-3 border-top-light d-flex justify-content-between align-items-center">
                <span class="text-xs text-muted">Posted ${timeAgoIST(j.created_at)}</span>
                <button class="btn btn-sm btn-primary" onclick="applyJob(${j.id})">Apply Now</button>
            </div>
        </div>
    `).join('');
}

function filterJobs() {
    const term = document.getElementById('job-search').value.toLowerCase();
    const filtered = allJobs.filter(j => 
        j.title.toLowerCase().includes(term) || 
        j.company.toLowerCase().includes(term) ||
        j.skills.some(s => s.toLowerCase().includes(term))
    );
    renderJobs(filtered);
}

async function applyJob(jobId) {
    if (!confirm('Apply for this position with your current resume?')) return;
    
    const data = await api('/referral/api/apply', {
        method: 'POST',
        body: JSON.stringify({ job_id: jobId })
    });

    if (data) {
        showToast(data.message, 'success');
        loadApplications();
        switchTab('applications');
    }
}

async function loadApplications() {
    const container = document.getElementById('my-applications');
    if (!container) return;
    
    const data = await api('/referral/api/my-applications');
    if (!data || data.length === 0) {
        container.innerHTML = '<p class="text-center py-5 text-muted">You haven\'t applied for any referrals yet.</p>';
        return;
    }

    container.innerHTML = data.map(a => `
        <div class="app-card" onclick="viewApplicationDetail(${a.id})">
            <div class="app-info">
                <div class="app-icon purple"><i class="ti ti-briefcase"></i></div>
                <div>
                    <h4 class="font-800 mb-0">${a.job_title}</h4>
                    <p class="text-xs text-muted font-600">${a.company}</p>
                </div>
            </div>
            <div class="d-flex align-items-center gap-4">
                <div class="text-right d-none d-md-block">
                    <div class="text-xs text-muted">Applied On</div>
                    <div class="font-700 text-sm">${formatISTDate(a.created_at)}</div>
                </div>
                <span class="app-status-badge status-${a.status}">${a.status.replace('_', ' ')}</span>
                <i class="ti ti-chevron-right text-muted"></i>
            </div>
        </div>
    `).join('');
}

async function viewApplicationDetail(id) {
    const data = await api(`/referral/api/referral/${id}`);
    if (!data) return;

    document.getElementById('modal-job-title').textContent = data.job.title;
    document.getElementById('modal-company').textContent = data.job.company;
    
    // Reset stepper
    document.querySelectorAll('.step').forEach(s => s.classList.remove('active', 'completed'));

    const statusMap = {
        'applied': 1,
        'selected': 2,
        'referred': 3,
        'interviewing': 4,
        'hired': 5,
        'rejected': 0
    };

    const currentStep = statusMap[data.status] || 1;
    const steps = ['applied', 'selected', 'referred', 'interviewing', 'hired'];
    
    steps.forEach((s, idx) => {
        const stepNum = idx + 1;
        const el = document.getElementById(`step-${s}`);
        if (!el) return;
        if (stepNum < currentStep) {
            el.classList.add('completed');
        } else if (stepNum === currentStep) {
            el.classList.add('active');
        }
    });

    // Special handling for rejected
    if (data.status === 'rejected') {
        const lastActive = document.querySelector('.step.active');
        if (lastActive) lastActive.innerHTML += '<span class="badge badge-danger" style="position:absolute;top:-10px;">Rejected</span>';
    }

    // Insights
    const insights = document.getElementById('matching-insights');
    if (data.explanation && data.explanation.strengths) {
        insights.innerHTML = `
            <div class="text-sm mb-3"><strong>Matching Score:</strong> ${data.score}%</div>
            <div class="mb-2"><strong>Strengths:</strong></div>
            <ul class="text-xs pl-3">
                ${data.explanation.strengths.map(s => `<li>${s}</li>`).join('')}
            </ul>
        `;
    } else {
        insights.innerHTML = '<p class="text-xs text-muted">Ranking results will appear once the AI completes the analysis.</p>';
    }

    // Referral Message
    const msgSection = document.getElementById('referral-message-section');
    if (data.referral_message) {
        msgSection.style.display = 'block';
        document.getElementById('referral-message-text').textContent = data.referral_message;
    } else {
        msgSection.style.display = 'none';
    }

    // Next Steps
    const nextSteps = document.getElementById('next-steps-info');
    if (data.status === 'applied') {
        nextSteps.innerHTML = 'The alumni who posted this job is currently reviewing all candidates. You will be notified if you are shortlisted for a referral.';
    } else if (data.status === 'selected') {
        nextSteps.innerHTML = 'Great news! You have been shortlisted. The alumni is preparing to officially refer your profile to the company.';
    } else if (data.status === 'referred') {
        nextSteps.innerHTML = 'Your profile has been referred! Keep an eye on your email for direct communication from the company\'s recruitment team.';
    } else if (data.status === 'interviewing') {
        nextSteps.innerHTML = 'Interview phase started. Good luck! Let your referrer know if you need any preparation tips.';
    } else {
        nextSteps.innerHTML = 'Check your email for further instructions regarding this application.';
    }

    document.getElementById('detail-modal').style.display = 'flex';
}

// ─── Alumni Functions ───
async function postJob() {
    const title = document.getElementById('job-title').value;
    const company = document.getElementById('job-company').value;
    const description = document.getElementById('job-desc').value;
    const location = document.getElementById('job-location').value;
    const skills = document.getElementById('job-skills').value.split(',').map(s => s.trim()).filter(s => s);

    const data = await api('/referral/api/jobs', {
        method: 'POST',
        body: JSON.stringify({ title, company, description, location, skills })
    });

    if (data) {
        showToast('Job posted successfully!', 'success');
        document.getElementById('job-form').reset();
        loadMyJobs();
    }
}

async function loadMyJobs() {
    const container = document.getElementById('my-jobs-list');
    if (!container) return;

    const data = await api('/referral/api/my-jobs');
    if (!data || data.length === 0) {
        container.innerHTML = '<p class="text-center py-4 text-muted text-sm">You haven\'t posted any jobs yet.</p>';
        return;
    }

    container.innerHTML = data.map(j => `
        <div class="job-admin-card mb-3 p-3 border-light rounded">
            <div class="d-flex justify-content-between align-items-center">
                <div>
                    <h4 class="font-800 mb-1">${j.title}</h4>
                    <p class="text-xs text-muted">${j.company} · ${j.applications_count} applicants</p>
                </div>
                <button class="btn btn-sm btn-secondary" onclick="viewApplicants(${j.id})">View Applicants</button>
            </div>
            <div id="applicants-${j.id}" class="applicants-drawer mt-3" style="display:none;">
                <!-- Applicants will load here -->
            </div>
        </div>
    `).join('');
}

async function viewApplicants(jobId) {
    const drawer = document.getElementById(`applicants-${jobId}`);
    if (drawer.style.display === 'block') {
        drawer.style.display = 'none';
        return;
    }

    drawer.innerHTML = '<p class="text-xs text-muted">Loading applicants...</p>';
    drawer.style.display = 'block';

    const data = await api(`/referral/api/jobs/${jobId}/applicants`);
    if (!data || data.length === 0) {
        drawer.innerHTML = '<p class="text-xs text-muted">No applicants yet.</p>';
        return;
    }

    drawer.innerHTML = data.map(a => `
        <div class="applicant-row d-flex justify-content-between align-items-center py-2 border-top-light">
            <div class="d-flex align-items-center gap-2">
                <div class="user-avatar xs">${a.student_name[0]}</div>
                <div>
                    <div class="text-sm font-700">${a.student_name} <span class="badge badge-primary text-xs">${a.score}% Match</span></div>
                    <div class="text-xs text-muted">Applied ${timeAgoIST(a.created_at)}</div>
                </div>
            </div>
            <div class="d-flex gap-2">
                <select class="form-input py-1 text-xs" onchange="updateReferralStatus(${a.id}, this.value)" style="width:auto;">
                    <option value="applied" ${a.status === 'applied' ? 'selected' : ''}>Applied</option>
                    <option value="selected" ${a.status === 'selected' ? 'selected' : ''}>Shortlist</option>
                    <option value="referred" ${a.status === 'referred' ? 'selected' : ''}>Referred</option>
                    <option value="interviewing" ${a.status === 'interviewing' ? 'selected' : ''}>Interviewing</option>
                    <option value="hired" ${a.status === 'hired' ? 'selected' : ''}>Hired</option>
                    <option value="rejected" ${a.status === 'rejected' ? 'selected' : ''}>Rejected</option>
                </select>
            </div>
        </div>
    `).join('');
}

async function updateReferralStatus(refId, status) {
    const data = await api(`/referral/api/referral/${refId}/status`, {
        method: 'POST',
        body: JSON.stringify({ status })
    });
    if (data) {
        showToast('Status updated!', 'success');
    }
}

function hideModal() {
    document.getElementById('detail-modal').style.display = 'none';
}

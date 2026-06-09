/* ════════ RESUME JAVASCRIPT ════════ */

function handleDrop(event) {
    const file = event.dataTransfer.files[0];
    if (file) uploadFile(file);
}

async function uploadFile(file) {
    if (!file) return;

    const allowed = ['.pdf', '.docx', '.txt'];
    const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
    if (!allowed.includes(ext)) {
        showToast('Unsupported file type. Use PDF, DOCX, or TXT.', 'error');
        return;
    }

    // Show progress
    document.getElementById('upload-progress').style.display = 'block';
    const bar = document.getElementById('upload-bar');

    const formData = new FormData();
    formData.append('file', file);

    // Simulate progress
    let progress = 0;
    const interval = setInterval(() => {
        progress = Math.min(progress + 10, 90);
        bar.style.width = progress + '%';
    }, 200);

    try {
        const response = await fetch('/resume/api/upload', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();

        clearInterval(interval);
        bar.style.width = '100%';

        if (response.ok) {
            showToast(data.message || 'Resume uploaded!', 'success');
            setTimeout(() => {
                window.location.href = `/resume/analysis/${data.id}`;
            }, 1000);
        } else {
            showToast(data.error || 'Upload failed', 'error');
            document.getElementById('upload-progress').style.display = 'none';
        }
    } catch (err) {
        clearInterval(interval);
        showToast('Upload failed. Please try again.', 'error');
        document.getElementById('upload-progress').style.display = 'none';
    }
}

/**
 * admin.js — Admin panel logic
 * Login, stats, file management, upload, re-index
 */

let token = localStorage.getItem('haui_admin_token');

// Check if already logged in
if (token) {
    showDashboard();
}

async function doLogin() {
    const username = document.getElementById('loginUsername').value.trim();
    const password = document.getElementById('loginPassword').value;
    const errorEl = document.getElementById('loginError');
    errorEl.style.display = 'none';

    if (!username || !password) {
        errorEl.textContent = 'Vui lòng nhập đầy đủ thông tin';
        errorEl.style.display = 'block';
        return;
    }

    try {
        const res = await fetch('/api/admin/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });

        const data = await res.json();

        if (res.ok && data.token) {
            token = data.token;
            localStorage.setItem('haui_admin_token', token);
            showDashboard();
        } else {
            errorEl.textContent = data.error || 'Đăng nhập thất bại';
            errorEl.style.display = 'block';
        }
    } catch (e) {
        errorEl.textContent = 'Lỗi kết nối server';
        errorEl.style.display = 'block';
    }
}

function doLogout() {
    token = null;
    localStorage.removeItem('haui_admin_token');
    document.getElementById('loginOverlay').style.display = 'flex';
    document.getElementById('adminDashboard').style.display = 'none';
}

function showDashboard() {
    document.getElementById('loginOverlay').style.display = 'none';
    document.getElementById('adminDashboard').style.display = 'block';
    loadStats();
}

async function apiCall(url, options = {}) {
    options.headers = {
        ...options.headers,
        'Authorization': `Bearer ${token}`
    };
    const res = await fetch(url, options);
    if (res.status === 401) {
        doLogout();
        showToast('Phiên đăng nhập hết hạn', 'error');
        throw new Error('Unauthorized');
    }
    return res;
}

async function loadStats() {
    try {
        const res = await apiCall('/api/admin/stats');
        const data = await res.json();

        document.getElementById('statChunks').textContent = data.total_chunks || 0;
        document.getElementById('statChroma').textContent = data.chroma_docs || 0;
        document.getElementById('statFiles').textContent = (data.data_files || []).length;

        // Render file list
        const fileList = document.getElementById('fileList');
        fileList.innerHTML = '';
        (data.data_files || []).forEach(f => {
            const li = document.createElement('li');
            li.className = 'file-item';
            li.innerHTML = `
                <span class="file-name">
                    ${f.type === 'json' ? '📄' : '📝'} ${f.name}
                </span>
                <span>
                    <span class="file-size">${formatSize(f.size)}</span>
                    <button class="delete-btn" onclick="deleteFile('${f.name}')">🗑️</button>
                </span>
            `;
            fileList.appendChild(li);
        });
    } catch (e) {
        console.error('Load stats error:', e);
    }
}

async function uploadFile(file) {
    if (!file) return;

    showToast(`Uploading ${file.name}...`, 'info');

    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await apiCall('/api/admin/upload', {
            method: 'POST',
            body: formData
        });

        const data = await res.json();
        if (res.ok) {
            showToast(`✓ ${file.name} uploaded & indexed!`, 'success');
            loadStats();
        } else {
            showToast(`✗ ${data.error}`, 'error');
        }
    } catch (e) {
        showToast('Upload failed', 'error');
    }

    document.getElementById('fileInput').value = '';
}

async function deleteFile(filename) {
    if (!confirm(`Xóa file ${filename}?`)) return;

    try {
        const res = await apiCall(`/api/admin/delete/${filename}`, { method: 'DELETE' });
        if (res.ok) {
            showToast(`✓ ${filename} đã xóa`, 'success');
            loadStats();
        }
    } catch (e) {
        showToast('Xóa thất bại', 'error');
    }
}

async function doReindex() {
    if (!confirm('Re-index toàn bộ dữ liệu? Quá trình có thể mất vài phút.')) return;

    showToast('🔄 Đang re-index...', 'info');

    try {
        const res = await apiCall('/api/admin/reindex', { method: 'POST' });
        const data = await res.json();
        if (res.ok) {
            showToast(`✓ Re-index xong! ${data.total_chunks} chunks`, 'success');
            loadStats();
        } else {
            showToast(`✗ ${data.error}`, 'error');
        }
    } catch (e) {
        showToast('Re-index failed', 'error');
    }
}

function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
}

function showToast(msg, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = msg;
    toast.className = `toast show ${type}`;
    setTimeout(() => { toast.className = 'toast'; }, 4000);
}

// Drag and drop support
const uploadZone = document.getElementById('uploadZone');
if (uploadZone) {
    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.style.borderColor = 'var(--haui-red)';
    });
    uploadZone.addEventListener('dragleave', () => {
        uploadZone.style.borderColor = 'var(--border-color)';
    });
    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.style.borderColor = 'var(--border-color)';
        if (e.dataTransfer.files.length) {
            uploadFile(e.dataTransfer.files[0]);
        }
    });
}

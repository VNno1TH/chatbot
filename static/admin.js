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
    loadAnalytics();
    loadFeedback();
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

// ── Chart instances (kept to destroy before re-render) ────────────────────────
let _chartIntent = null;
let _chartMajors = null;

// ── Analytics ─────────────────────────────────────────────────────────────────
async function loadAnalytics() {
    try {
        const res  = await apiCall('/api/admin/analytics');
        const data = await res.json();

        // Update stat cards
        document.getElementById('statTotalQueries').textContent = data.total ?? '—';
        document.getElementById('statAvgTime').textContent      = data.avg_time != null ? data.avg_time + 's' : '—';

        if (!data.total) {
            document.getElementById('analyticsEmpty').style.display = 'block';
            return;
        }
        document.getElementById('analyticsEmpty').style.display = 'none';

        // ── Pie chart: Intent distribution ──
        const intentLabels = Object.keys(data.intents || {});
        const intentValues = Object.values(data.intents || {});
        const PALETTE = [
            '#ef4444','#f97316','#eab308','#22c55e',
            '#06b6d4','#6366f1','#a855f7','#ec4899','#14b8a6',
        ];

        if (_chartIntent) _chartIntent.destroy();
        _chartIntent = new Chart(document.getElementById('chartIntent'), {
            type: 'doughnut',
            data: {
                labels:   intentLabels,
                datasets: [{ data: intentValues, backgroundColor: PALETTE, borderWidth: 2 }],
            },
            options: {
                plugins: {
                    legend: { position: 'bottom', labels: { font: { size: 11 } } },
                },
            },
        });

        // ── Horizontal bar chart: Top majors ──
        const majorLabels = (data.top_majors || []).map(m => m.name);
        const majorValues = (data.top_majors || []).map(m => m.count);

        if (_chartMajors) _chartMajors.destroy();
        _chartMajors = new Chart(document.getElementById('chartMajors'), {
            type: 'bar',
            data: {
                labels:   majorLabels,
                datasets: [{
                    label:           'Số câu hỏi',
                    data:            majorValues,
                    backgroundColor: '#ef4444cc',
                    borderRadius:    4,
                }],
            },
            options: {
                indexAxis: 'y',
                plugins: { legend: { display: false } },
                scales:  { x: { beginAtZero: true, ticks: { precision: 0 } } },
            },
        });

    } catch (e) {
        console.error('loadAnalytics error:', e);
    }
}

// ── Feedback table ────────────────────────────────────────────────────────────
async function loadFeedback() {
    try {
        const res   = await apiCall('/api/admin/feedback?limit=30');
        const items = await res.json();

        const wrap  = document.getElementById('feedbackTableWrap');
        const empty = document.getElementById('feedbackEmpty');

        if (!items.length) {
            empty.style.display = 'block';
            return;
        }
        empty.style.display = 'none';

        const rows = items.map(fb => `
            <tr style="${fb.type === 'down' ? 'background:rgba(239,68,68,.08)' : ''}">
                <td>${fb.type === 'up' ? '👍' : '👎'}</td>
                <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escHtml(fb.question)}">${escHtml(fb.question)}</td>
                <td style="max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escHtml(fb.answer)}">${escHtml(fb.answer)}</td>
                <td>${escHtml(fb.comment || '—')}</td>
                <td style="white-space:nowrap;font-size:12px">${fb.ts}</td>
            </tr>
        `).join('');

        wrap.innerHTML = `
            <table style="width:100%;border-collapse:collapse;font-size:13px">
                <thead>
                    <tr style="border-bottom:1px solid var(--border-color);text-align:left">
                        <th style="padding:8px 12px">Loại</th>
                        <th style="padding:8px 12px">Câu hỏi</th>
                        <th style="padding:8px 12px">Câu trả lời</th>
                        <th style="padding:8px 12px">Bình luận</th>
                        <th style="padding:8px 12px">Thời gian</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        `;
    } catch (e) {
        console.error('loadFeedback error:', e);
    }
}

function escHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

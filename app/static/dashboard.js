/* InvoicePilot Dashboard JavaScript */

// ─── State ──────────────────────────────────────────────────────────────
let allCases = [];

// ─── Initialize ─────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    loadDashboard();
    setupUpload();
    setInterval(loadDashboard, 3000);  // Poll every 3s
});

async function loadDashboard() {
    await Promise.all([loadMetrics(), loadCases()]);
}

// ─── Metrics ────────────────────────────────────────────────────────────
async function loadMetrics() {
    try {
        const resp = await fetch('/api/dashboard');
        const data = await resp.json();

        document.getElementById('metricTotal').textContent = data.total_cases;
        document.getElementById('metricApproved').textContent = data.auto_approved;
        // "Needs Attention" = needs_review + needs_information + blocked
        const attention = data.needs_review + data.needs_information + data.blocked;
        document.getElementById('metricAttention').textContent = attention;
        document.getElementById('metricApprovedNet').textContent = data.approved_net_display;
    } catch (e) {
        console.error('Failed to load metrics:', e);
    }
}

// ─── Cases ──────────────────────────────────────────────────────────────
async function loadCases() {
    try {
        const resp = await fetch('/api/cases');
        allCases = await resp.json();
        renderCases(allCases);
    } catch (e) {
        console.error('Failed to load cases:', e);
    }
}

function renderCases(cases) {
    const container = document.getElementById('casesTable');

    if (cases.length === 0) {
        container.innerHTML = '<div class="empty-state">No invoice cases yet. Upload a PDF to start processing.</div>';
        return;
    }

    let html = `<table>
        <thead><tr>
            <th>Vendor</th>
            <th>Invoice #</th>
            <th>Gross</th>
            <th>PO</th>
            <th>Decision</th>
            <th>Reason</th>
            <th>Created</th>
        </tr></thead><tbody>`;

    for (const c of cases) {
        const badge = getBadge(c.decision);
        const time = c.created_at ? new Date(c.created_at).toLocaleString() : '—';

        html += `<tr onclick="window.location='/case/${c.id}'">
            <td>${esc(c.vendor_name || '—')}</td>
            <td>${esc(c.invoice_number || '—')}</td>
            <td class="money">${c.gross_display || '—'}</td>
            <td>${esc(c.po_id || '—')}</td>
            <td>${badge}</td>
            <td>${esc(c.reason_code || '—')}</td>
            <td class="text-muted text-sm">${time}</td>
        </tr>`;
    }

    html += '</tbody></table>';
    container.innerHTML = html;
}

function filterCases() {
    const search = document.getElementById('searchInput').value.toLowerCase();
    const status = document.getElementById('statusFilter').value;

    let filtered = allCases;
    if (search) {
        filtered = filtered.filter(c =>
            (c.invoice_number || '').toLowerCase().includes(search) ||
            (c.id || '').toLowerCase().includes(search) ||
            (c.vendor_name || '').toLowerCase().includes(search)
        );
    }
    if (status) {
        filtered = filtered.filter(c => c.decision === status);
    }
    renderCases(filtered);
}

// ─── CSV Upload ──────────────────────────────────────────────────────
async function uploadCsv(file) {
    const status = document.getElementById('uploadStatus');
    status.hidden = false;
    status.className = 'upload-status processing';
    status.textContent = `Processing ${file.name} (CSV)…`;

    const formData = new FormData();
    formData.append('file', file);

    try {
        const resp = await fetch('/api/upload-csv', { method: 'POST', body: formData });
        const data = await resp.json();

        if (data.detail || data.error) {
            status.className = 'upload-status error';
            status.textContent = `Error: ${data.detail || data.error}`;
            return;
        }

        const s = data.summary;
        status.className = 'upload-status success';
        status.innerHTML = `CSV processed: ${s.total_rows} rows — ` +
            `${s.auto_approved} approved, ${s.needs_review} review, ` +
            `${s.needs_information} info needed, ${s.blocked} blocked` +
            (s.errors ? `, ${s.errors} errors` : '');

        // Show detailed CSV results panel
        renderCsvResults(data);
        loadDashboard();
    } catch (e) {
        status.className = 'upload-status error';
        status.textContent = `CSV upload failed: ${e.message}`;
    }
}

function renderCsvResults(data) {
    const panel = document.getElementById('csvResults');
    const body = document.getElementById('csvResultsBody');
    panel.hidden = false;

    const s = data.summary;
    let html = `
        <div style="display:flex;gap:24px;margin-bottom:16px;flex-wrap:wrap;">
            <div><strong>${s.total_rows}</strong> <span style="color:var(--text-muted)">Total rows</span></div>
            <div style="color:var(--approved)"><strong>${s.auto_approved}</strong> Approved</div>
            <div style="color:var(--review)"><strong>${s.needs_review}</strong> Needs Review</div>
            <div style="color:var(--info)"><strong>${s.needs_information}</strong> Info Needed</div>
            <div style="color:var(--blocked)"><strong>${s.blocked}</strong> Blocked</div>
            ${s.errors ? `<div style="color:var(--blocked)"><strong>${s.errors}</strong> Errors</div>` : ''}
        </div>
        <table style="width:100%;border-collapse:collapse;font-size:13px;">
            <thead><tr style="background:var(--surface-muted);">
                <th style="padding:8px;text-align:left;border-bottom:1px solid var(--border);">Row</th>
                <th style="padding:8px;text-align:left;border-bottom:1px solid var(--border);">Invoice #</th>
                <th style="padding:8px;text-align:left;border-bottom:1px solid var(--border);">Decision</th>
                <th style="padding:8px;text-align:left;border-bottom:1px solid var(--border);">Reason</th>
                <th style="padding:8px;text-align:left;border-bottom:1px solid var(--border);">Action</th>
            </tr></thead><tbody>`;

    for (const row of data.rows) {
        const badge = row.decision ? getBadge(row.decision) : `<span style="color:var(--blocked)">Error</span>`;
        const reason = esc(row.primary_reason_code || row.error || '—');
        const link = row.case_id ? `<a href="/case/${row.case_id}" style="color:var(--ip-blue-ink);">View →</a>` : '—';
        html += `<tr style="border-bottom:1px solid var(--divider);">
            <td style="padding:8px;">${row.row_number}</td>
            <td style="padding:8px;">${esc(row.invoice_number || '—')}</td>
            <td style="padding:8px;">${badge}</td>
            <td style="padding:8px;font-size:12px;">${reason}</td>
            <td style="padding:8px;">${link}</td>
        </tr>`;
    }
    html += '</tbody></table>';
    body.innerHTML = html;
}

// ─── Upload ──────────────────────────────────────────────────────────────
function setupUpload() {
    const area = document.getElementById('uploadArea');
    const input = document.getElementById('fileInput');
    const csvInput = document.getElementById('csvFileInput');

    area.addEventListener('dragover', (e) => {
        e.preventDefault();
        area.classList.add('drag-over');
    });

    area.addEventListener('dragleave', () => {
        area.classList.remove('drag-over');
    });

    area.addEventListener('drop', (e) => {
        e.preventDefault();
        area.classList.remove('drag-over');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            const file = files[0];
            if (file.name.toLowerCase().endsWith('.pdf')) {
                uploadFile(file);
            } else if (file.name.toLowerCase().endsWith('.csv')) {
                uploadCsv(file);
            }
        }
    });

    input.addEventListener('change', () => {
        if (input.files.length > 0) uploadFile(input.files[0]);
    });

    csvInput.addEventListener('change', () => {
        if (csvInput.files.length > 0) uploadCsv(csvInput.files[0]);
    });
}

async function uploadFile(file) {
    const status = document.getElementById('uploadStatus');
    status.hidden = false;
    status.className = 'upload-status processing';
    status.textContent = `Processing ${file.name}…`;

    const formData = new FormData();
    formData.append('file', file);

    try {
        const resp = await fetch('/api/upload', { method: 'POST', body: formData });

        // Always try to parse as JSON; if server returned HTML on 500, show a clean message
        let data;
        const contentType = resp.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
            data = await resp.json();
        } else {
            const text = await resp.text();
            data = { error: `Server error (${resp.status}). Please try again or check the server.` };
        }

        if (data.is_byte_duplicate) {
            status.className = 'upload-status warning';
            status.innerHTML = `Already submitted. <a href="/case/${data.duplicate_case_id || data.case_id}">View existing case →</a>`;
        } else if (data.error) {
            status.className = 'upload-status error';
            status.textContent = `Error: ${data.error}`;
        } else {
            status.className = 'upload-status success';
            status.innerHTML = `${data.decision || 'Processed'}: ${data.explanation || ''} <a href="/case/${data.case_id}">View case →</a>`;
            setTimeout(() => window.location = `/case/${data.case_id}`, 1000);
        }

        loadDashboard();
    } catch (e) {
        status.className = 'upload-status error';
        status.textContent = `Upload failed: ${e.message}`;
    }
}

// ─── Fixtures ───────────────────────────────────────────────────────────
let fixturesLoaded = false;

async function toggleFixtures() {
    const list = document.getElementById('fixturesList');
    if (list.hidden) {
        list.hidden = false;
        if (!fixturesLoaded) {
            await loadFixtures();
            fixturesLoaded = true;
        }
    } else {
        list.hidden = true;
    }
}

async function loadFixtures() {
    try {
        const resp = await fetch('/api/fixtures');
        const fixtures = await resp.json();
        const container = document.getElementById('fixturesList');

        if (fixtures.length === 0) {
            container.innerHTML = '<div class="empty-state">No fixtures available. Run: python scripts/generate_fixtures.py</div>';
            return;
        }

        let html = '';
        for (const f of fixtures) {
            html += `<div class="fixture-card">
                <div class="fixture-family">${esc(f.family)}</div>
                <div class="fixture-name">${esc(f.name)}</div>
                <div class="fixture-desc">${esc(f.description)}</div>
                <div class="fixture-expected">Expected: ${esc(f.expected)}</div>
                <a href="/api/fixtures/${encodeURIComponent(f.filename)}" class="btn btn-small" download>
                    Download
                </a>
            </div>`;
        }

        container.innerHTML = html;
    } catch (e) {
        document.getElementById('fixturesList').innerHTML = `<div class="error-state">${e.message}</div>`;
    }
}

// ─── Demo Reset ─────────────────────────────────────────────────────────
async function confirmReset() {
    if (!confirm('Reset all demo data? This will delete all processed invoices and restore the seed baseline.')) {
        return;
    }

    try {
        const resp = await fetch('/api/demo/reset', { method: 'POST' });
        const data = await resp.json();
        alert(data.message || 'Reset complete');
        window.location.reload();
    } catch (e) {
        alert('Reset failed: ' + e.message);
    }
}

// ─── Helpers ────────────────────────────────────────────────────────────
function esc(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function getBadge(decision) {
    const map = {
        'AUTO_APPROVED': ['badge-approved', 'Approved'],
        'NEEDS_REVIEW': ['badge-review', 'Review'],
        'NEEDS_INFORMATION': ['badge-info', 'Info Needed'],
        'BLOCKED': ['badge-blocked', 'Blocked'],
    };
    const [cls, label] = map[decision] || ['badge-processing', decision || 'Processing'];
    return `<span class="badge ${cls}">${label}</span>`;
}

function fmtMoney(cents) {
    if (cents === null || cents === undefined) return '—';
    return '$' + (cents / 100).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

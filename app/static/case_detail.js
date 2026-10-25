/* InvoicePilot Case Detail JavaScript */

let caseData = null;
let pollingInterval = null;

document.addEventListener('DOMContentLoaded', () => {
    const caseId = document.getElementById('caseDetail').dataset.caseId;
    loadCase(caseId);
    document.getElementById('auditExportLink').href = `/api/cases/${caseId}/audit`;
});

async function loadCase(caseId) {
    try {
        const resp = await fetch(`/api/cases/${caseId}`);
        if (!resp.ok) throw new Error('Case not found');
        caseData = await resp.json();
        renderCase(caseData);

        // If still processing, poll for updates
        const latestAttempt = caseData.attempts[caseData.attempts.length - 1];
        if (latestAttempt && latestAttempt.execution_state === 'RUNNING') {
            startPolling(caseId);
        }
    } catch (e) {
        document.getElementById('decisionBadge').textContent = 'Error';
        console.error(e);
    }
}

function startPolling(caseId) {
    if (pollingInterval) return;
    pollingInterval = setInterval(async () => {
        const resp = await fetch(`/api/cases/${caseId}/events`);
        const data = await resp.json();
        renderTimeline(data.events);
        if (data.execution_state !== 'RUNNING') {
            clearInterval(pollingInterval);
            pollingInterval = null;
            loadCase(caseId);
        }
    }, 800);
}

function renderCase(data) {
    const c = data.case;
    const latestAttempt = data.attempts[data.attempts.length - 1];

    // Decision badge
    const badge = document.getElementById('decisionBadge');
    badge.textContent = formatDecision(c.decision);
    badge.className = 'decision-badge ' + getBadgeClass(c.decision);

    // Decision content
    const latestDecision = data.decisions[data.decisions.length - 1];
    if (latestDecision) {
        renderDecision(latestDecision, c);
    }

    // Stage timeline
    if (latestAttempt) {
        renderTimeline(latestAttempt.events);
    }

    // Extracted data
    if (latestAttempt && latestAttempt.extracted_data) {
        renderExtractedData(latestAttempt.extracted_data, latestAttempt.field_evidences);
    }

    // PDF preview
    if (data.source_documents.length > 0) {
        renderPdfPreview(data.source_documents);
    }

    // Budget
    if (data.budget) {
        renderBudget(data.budget, c);
    }

    // Rules
    if (latestAttempt && latestAttempt.rules.length > 0) {
        renderRules(latestAttempt.rules);
    }

    // PO Selection (if NEEDS_REVIEW with PO_AMBIGUOUS)
    if (c.decision === 'NEEDS_REVIEW' && c.reason_code === 'PO_AMBIGUOUS' && latestAttempt) {
        showPOSelection(latestAttempt, c);
    }

    // Revision upload (if NEEDS_INFORMATION)
    if (c.decision === 'NEEDS_INFORMATION') {
        document.getElementById('revisionPanel').hidden = false;
    }

    // Review history
    if (data.review_actions.length > 0) {
        renderReviewHistory(data.review_actions);
    }
}

function renderDecision(decision, c) {
    const panel = document.getElementById('decisionContent');
    let html = `
        <div class="decision-explanation">${esc(decision.explanation)}</div>
        <div class="decision-next">
            <strong>Next Action:</strong> ${esc(decision.next_action)}<br>
            <span class="text-muted text-sm">Responsible: ${esc(decision.responsible_role)}</span>
        </div>
    `;

    if (decision.decision === 'AUTO_APPROVED') {
        html += '<div class="decision-note">⚠ No payment has been executed. This approval reserves PO capacity for AP processing only.</div>';
    }

    html += `<div class="text-muted text-sm mt-2">Policy: ${esc(decision.policy_version)} · ${new Date(decision.created_at).toLocaleString()}</div>`;

    panel.innerHTML = html;
}

function renderTimeline(events) {
    const container = document.getElementById('stageTimeline');
    if (!events || events.length === 0) {
        container.innerHTML = '<div class="empty-state">No events yet</div>';
        return;
    }

    const stageLabels = {
        'receive_validate': 'Receive & Validate PDF',
        'byte_duplicate_check': 'Byte Duplicate Check',
        'text_extraction': 'Text Extraction',
        'field_extraction': 'Field Extraction',
        'field_validation': 'Field Validation',
        'vendor_resolution': 'Vendor Resolution',
        'duplicate_detection': 'Duplicate Detection',
        'po_matching': 'PO Matching',
        'policy_evaluation': 'Policy Evaluation',
        'commit_decision': 'Commit Decision',
        'publish_results': 'Publish Results',
    };

    // Deduplicate: show latest status per stage
    const stageMap = {};
    for (const e of events) {
        const key = e.stage_name;
        if (!stageMap[key] || e.status !== 'STARTED') {
            stageMap[key] = e;
        }
    }

    let html = '';
    for (const e of Object.values(stageMap)) {
        const icon = e.status === 'COMPLETED' ? '✓' :
                     e.status === 'FAILED' ? '✗' :
                     e.status === 'SKIPPED' ? '○' :
                     e.status === 'STARTED' ? '◉' : '?';
        const duration = e.duration_ms !== null && e.duration_ms !== undefined
            ? `${e.duration_ms}ms` : '';
        const label = stageLabels[e.stage_name] || e.stage_name;

        html += `<div class="stage-item ${e.status.toLowerCase()}">
            <span class="stage-icon">${icon}</span>
            <span class="stage-name">${esc(label)}</span>
            <span class="stage-duration">${duration}</span>
        </div>`;
        if (e.message) {
            html += `<div class="stage-message" style="margin-left: 36px; margin-bottom: 4px;">${esc(e.message)}</div>`;
        }
    }

    container.innerHTML = html;
}

function renderExtractedData(ext, evidences) {
    const container = document.getElementById('extractedData');
    const fields = [
        ['Vendor', ext.vendor_name || ext.normalized_vendor],
        ['Tax ID', ext.vendor_tax_id],
        ['Invoice #', ext.invoice_number],
        ['Invoice Date', ext.invoice_date],
        ['Due Date', ext.due_date],
        ['Currency', ext.currency],
        ['PO Reference', ext.po_reference],
        ['Subtotal', fmtMoney(ext.subtotal_cents)],
        ['Tax', fmtMoney(ext.tax_cents)],
        ['Net Total', fmtMoney(ext.net_total_cents)],
        ['Gross Total', fmtMoney(ext.gross_total_cents)],
        ['Tax Treatment', ext.tax_treatment],
        ['Extraction Mode', ext.extraction_method],
    ];

    let html = '<table>';
    for (const [label, value] of fields) {
        const evidence = evidences.find(e => e.field_name === label.toLowerCase().replace(/[# ]/g, '_'));
        const evTag = evidence ? `<span class="evidence-tag">${evidence.method} · Page ${evidence.page_number || '?'}</span>` : '';
        const cls = value ? (value === 'MISSING' ? 'field-missing' : 'field-verified') : 'field-missing';

        html += `<tr>
            <td>${esc(label)}</td>
            <td class="${cls}">${esc(value || 'Not found')} ${evTag}</td>
        </tr>`;
    }

    // Line items
    if (ext.line_items && ext.line_items.length > 0) {
        html += '<tr><td colspan="2" style="font-weight:600; padding-top:8px">Line Items</td></tr>';
        for (const item of ext.line_items) {
            html += `<tr><td style="padding-left:16px">${esc(item.description || '—')}</td><td class="money">${item.amount_display || fmtMoney(item.amount_cents)}</td></tr>`;
        }
    }

    // Warnings
    if (ext.warnings && ext.warnings.length > 0) {
        html += '<tr><td colspan="2" style="padding-top:8px; color: var(--warning)">⚠ ' + ext.warnings.map(esc).join('<br>⚠ ') + '</td></tr>';
    }

    html += '</table>';
    container.innerHTML = html;
}

function renderPdfPreview(docs) {
    const container = document.getElementById('pdfPreview');
    const currentDoc = docs.find(d => d.is_current) || docs[0];
    if (!currentDoc) return;

    const pageCount = currentDoc.page_count || 1;
    let html = '';

    for (let p = 1; p <= pageCount; p++) {
        html += `<img src="/api/page-image/${currentDoc.id}/${p}" alt="Page ${p}"
                    onerror="this.alt='Page image not available'; this.style.minHeight='200px'; this.style.background='#f0f0f0';">`;
    }

    if (docs.length > 1) {
        html += '<div class="text-muted text-sm mt-2">Revision history: ';
        for (const d of docs) {
            html += `Rev ${d.revision_number} (${d.original_filename})${d.is_current ? ' ← current' : ''} · `;
        }
        html += '</div>';
    }

    container.innerHTML = html;
}

function renderBudget(budget, c) {
    const panel = document.getElementById('budgetPanel');
    panel.hidden = false;

    const invoiceNet = c.net_cents || 0;
    const projected = budget.committed_cents;
    const isOver = projected > budget.ceiling_cents;

    let html = `<table>
        <tr><td>PO Net Amount</td><td class="money">${budget.po_net_display}</td></tr>
        <tr><td>Allowed Overage</td><td class="money">+ ${budget.overage_display}</td></tr>
        <tr class="budget-row-total"><td>Permitted Ceiling</td><td class="money">${budget.ceiling_display}</td></tr>
        <tr><td>Current Commitments</td><td class="money">${budget.committed_display}</td></tr>
        <tr><td>Remaining Capacity</td><td class="money ${isOver ? 'budget-over' : 'budget-ok'}">${budget.remaining_display}</td></tr>
    </table>`;

    document.getElementById('budgetContent').innerHTML = html;
}

function renderRules(rules) {
    const container = document.getElementById('ruleResults');

    let html = '';
    for (const r of rules) {
        const cls = r.result === 'PASS' ? 'rule-pass' :
                    r.result === 'FAIL' ? 'rule-fail' :
                    r.result === 'WARN' ? 'rule-warn' : 'rule-na';
        const icon = r.result === 'PASS' ? '✓' :
                     r.result === 'FAIL' ? '✗' :
                     r.result === 'WARN' ? '⚠' : '—';

        html += `<div class="rule-item ${cls}">
            <div class="rule-icon">${icon}</div>
            <div class="rule-body">
                <div class="rule-name">${esc(r.rule_name)}</div>
                <div class="rule-explain">${esc(r.explanation)}</div>
                ${r.observed_value ? `<div class="rule-values">Observed: ${esc(r.observed_value)}</div>` : ''}
                ${r.expected_value ? `<div class="rule-values">Expected: ${esc(r.expected_value)}</div>` : ''}
            </div>
        </div>`;
    }

    container.innerHTML = html;
}

function showPOSelection(attempt, c) {
    const panel = document.getElementById('poSelectionPanel');
    panel.hidden = false;

    // Get PO candidates from the latest attempt's events
    const poEvent = attempt.events.find(e => e.stage_name === 'po_matching');
    const candidates = poEvent?.details?.candidates_data || [];

    // Fallback: try the API response
    let html = '<p class="text-sm text-muted mb-2">Select the correct PO and provide a reason for your selection:</p>';

    // We'll fetch candidates from the case detail's budget or directly
    html += '<div id="poCandidates">Loading candidates…</div>';
    html += '<div class="mt-2"><input type="text" id="poReason" placeholder="Reason for PO selection" class="input-field" style="width:100%"></div>';
    html += '<button class="btn btn-primary mt-2" onclick="submitPOSelection()">Re-evaluate with Selected PO</button>';

    document.getElementById('poSelectionContent').innerHTML = html;

    // Load PO candidates
    loadPOCandidates(c);
}

async function loadPOCandidates(c) {
    // Get eligible POs for this vendor
    try {
        const resp = await fetch(`/api/cases/${c.id}`);
        const data = await resp.json();
        const attempt = data.attempts[data.attempts.length - 1];
        const poEvent = attempt?.events?.find(e => e.stage_name === 'po_matching');

        // Get candidate PO IDs from details
        const candidateCount = poEvent?.details?.candidates || 0;

        // For now, show simple PO input
        let html = '';
        if (candidateCount > 0) {
            html = '<p class="text-sm">Enter the PO ID (e.g., PO-1005 or PO-1006):</p>';
        }
        html += `<input type="text" id="poIdInput" placeholder="PO-XXXX" class="input-field" style="width:200px">`;
        document.getElementById('poCandidates').innerHTML = html;
    } catch (e) {
        document.getElementById('poCandidates').innerHTML = '<input type="text" id="poIdInput" placeholder="PO-XXXX" class="input-field">';
    }
}

async function submitPOSelection() {
    const caseId = document.getElementById('caseDetail').dataset.caseId;
    const poId = document.getElementById('poIdInput').value.trim();
    const reason = document.getElementById('poReason').value.trim();

    if (!poId || !reason) {
        alert('Please provide both a PO ID and a reason.');
        return;
    }

    const formData = new FormData();
    formData.append('po_id', poId);
    formData.append('reason', reason);

    try {
        const resp = await fetch(`/api/cases/${caseId}/review/select-po`, {
            method: 'POST', body: formData
        });
        const data = await resp.json();
        if (data.error) {
            alert('Error: ' + data.error);
        } else {
            window.location.reload();
        }
    } catch (e) {
        alert('Failed: ' + e.message);
    }
}

async function attachRevision() {
    const caseId = document.getElementById('caseDetail').dataset.caseId;
    const fileInput = document.getElementById('revisionFile');
    const reason = document.getElementById('revisionReason').value.trim();

    if (!fileInput.files.length) {
        alert('Please select a PDF file.');
        return;
    }

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    formData.append('reason', reason || 'Corrected document');

    try {
        const resp = await fetch(`/api/cases/${caseId}/review/attach-revision`, {
            method: 'POST', body: formData
        });
        const data = await resp.json();
        window.location.reload();
    } catch (e) {
        alert('Failed: ' + e.message);
    }
}

function renderReviewHistory(reviews) {
    const panel = document.getElementById('reviewHistoryPanel');
    panel.hidden = false;

    let html = '';
    for (const r of reviews) {
        html += `<div class="review-item">
            <span class="review-actor">${esc(r.actor)}</span>
            <span class="text-muted"> · ${esc(r.action_type)}</span>
            <span class="review-time"> · ${new Date(r.created_at).toLocaleString()}</span>
            ${r.reason ? `<div class="text-sm">${esc(r.reason)}</div>` : ''}
            ${r.before_value || r.after_value ? `<div class="text-sm text-muted">${esc(r.before_value || '—')} → ${esc(r.after_value || '—')}</div>` : ''}
        </div>`;
    }

    document.getElementById('reviewHistory').innerHTML = html;
}

// ─── Helpers ────────────────────────────────────────────────────────────
function esc(str) {
    if (str === null || str === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}

function fmtMoney(cents) {
    if (cents === null || cents === undefined) return '—';
    return '$' + (cents / 100).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatDecision(d) {
    const map = {
        'AUTO_APPROVED': 'Auto-Approved',
        'NEEDS_REVIEW': 'Needs Review',
        'NEEDS_INFORMATION': 'Needs Information',
        'BLOCKED': 'Blocked',
    };
    return map[d] || d || 'Processing…';
}

function getBadgeClass(d) {
    const map = {
        'AUTO_APPROVED': 'badge-approved',
        'NEEDS_REVIEW': 'badge-review',
        'NEEDS_INFORMATION': 'badge-info',
        'BLOCKED': 'badge-blocked',
    };
    return map[d] || 'badge-processing';
}

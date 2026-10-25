# UI Redesign Plan

## Scope
Redesign all 4 templates and CSS for a polished Zamp-inspired AP workbench.
No backend changes. No new routes. No framework migration.

## Files to Change
- `app/static/style.css` — Complete rewrite with Zamp-derived design system
- `app/templates/base.html` — Dark sidebar nav, refined shell
- `app/templates/dashboard.html` — Restructured metrics, upload, table
- `app/templates/case_detail.html` — Enhanced live-run view and evidence workspace
- `app/templates/health.html` — Polished health view
- `app/static/dashboard.js` — Preserve all logic, update HTML output for new classes
- `app/static/case_detail.js` — Preserve all logic, update HTML output for new classes

## Preservation Checklist
- [x] All API endpoints unchanged
- [x] Form field names (file, po_id, reason) unchanged
- [x] Element IDs referenced by JS unchanged
- [x] Upload/drag-drop behavior unchanged
- [x] Polling interval and event transport unchanged
- [x] No new runtime dependencies
- [x] No backend code changes

# UI Brand Reference — Zamp.ai Inspection

**Source**: https://www.zamp.ai/
**Observed**: 2026-10-25 via Playwright headless Chromium
**Method**: Computed style extraction from rendered page

## Observed Values

| Token | Observed Value | Source Element |
|---|---|---|
| Body background | `rgb(255, 255, 255)` (#FFFFFF) | `body` |
| Body text | `rgb(0, 0, 0)` (#000000) | `body` |
| Body font | `ui-sans-serif, system-ui, sans-serif` | `body` |
| Heading color | `rgb(23, 23, 23)` (#171717) | `h1` |
| Heading font | `Geist, system-ui, arial` | `h1` |
| Heading weight | 500 | `h1` |
| Button background | `rgb(0, 0, 0)` (#000000) | First CTA link |
| Button text | `rgb(245, 245, 245)` (#F5F5F5) | First CTA link |
| Button radius | Fully rounded (pill) | First CTA link |
| Button padding | `0px 24px` | First CTA link |
| Button font-weight | 500 | First CTA link |
| Dark section bg | `rgb(45, 45, 45)` (#2D2D2D) | Section backgrounds |
| Accent green | `rgb(0, 61, 41)` (#003D29) | Section background |
| Muted surface | `rgb(245, 245, 245)` (#F5F5F5) | Cards/sections |
| Nav background | Transparent (white page) | `nav` |
| Muted text | `rgba(45, 45, 45, 0.82)` | Secondary content |

## Derived Application Tokens (InvoicePilot adaptations)

The Zamp site uses a stark black/white palette with green accents.
For a dense financial operations UI, I've derived accessible working variants:

| App Token | Value | Rationale |
|---|---|---|
| `--brand-primary` | `#003D29` (Zamp forest green) | CTA actions, nav accent |
| `--brand-primary-hover` | `#00291B` | Darker green for hover |
| `--brand-primary-fg` | `#FFFFFF` | White on green |
| `--surface` | `#FFFFFF` | Cards and panels |
| `--canvas` | `#F7F7F5` | Page background (warm neutral) |
| `--elevated` | `#FFFFFF` | Elevated cards |
| `--text-primary` | `#171717` | Heading/body text |
| `--text-secondary` | `#404040` | Secondary descriptions |
| `--text-muted` | `#737373` | Captions and labels |
| `--border` | `#E5E5E5` | Dividers and borders |
| `--nav-bg` | `#171717` | Dark sidebar (Zamp dark sections) |
| `--nav-text` | `#F5F5F5` | Nav text on dark bg |

## Font Substitution

Zamp uses "Geist" which is a proprietary Vercel font. Not lawfully bundled.
**Substitution**: System UI stack (`system-ui, -apple-system, 'Segoe UI', sans-serif`).
This is visually similar — clean, geometric sans-serif with neutral character.
Tabular numerals via `font-variant-numeric: tabular-nums` for financial data.

## Screenshot Evidence

- `qa/evidence/ui_redesign/zamp_homepage.png` — Homepage capture
- `qa/evidence/ui_redesign/zamp_brand_colors.json` — Raw computed styles

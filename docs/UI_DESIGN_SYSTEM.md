# InvoicePilot — Design System v2

## Palette Identity

Three blended sources:
1. **Zamp.ai accent** (`#003D29` forest green) — verified from computed styles, used for primary actions
2. **InvoicePilot electric blue** (`#65B8FF` / `#0758A8`) — original product accent for information, selection, and active processing
3. **Light workspace** (`#F7FAFF` canvas) — cool white environment, Apple-inspired spacing and control refinement

## Color Tokens

### Brand (from Zamp.ai — verified 2026-10-25)
| Token | Value | Contrast | Usage |
|---|---|---|---|
| `--brand` | `#003D29` | 12.8:1 on white | Primary buttons, nav brand icon |
| `--brand-hover` | `#00523A` | 10.1:1 on white | Button hover |
| `--brand-light` | `#E4F2EC` | — | Brand-tinted subtle backgrounds |

### InvoicePilot Blue (product choice, not claimed from any brand)
| Token | Value | Contrast | Usage |
|---|---|---|---|
| `--ip-blue` | `#65B8FF` | 2.6:1 on white | Active stage border, decorative |
| `--ip-blue-soft` | `#E8F4FF` | — | Active stage bg, upload drag-over, table hover |
| `--ip-blue-ink` | `#0758A8` | 6.4:1 on white | Focus ring, evidence tags, blue text (AA pass) |
| `--ip-blue-border` | `#B3D9F7` | — | Decorative blue dividers |

### Canvas & Surfaces
| Token | Value | Usage |
|---|---|---|
| `--canvas` | `#F7FAFF` | Page background (cool blue-white) |
| `--surface` | `#FFFFFF` | Cards, panels, table rows |
| `--surface-muted` | `#F0F5FC` | Table headers, hover, input areas |

### Text (WCAG AA verified against `#FFFFFF`)
| Token | Value | Ratio | Usage |
|---|---|---|---|
| `--text-primary` | `#172033` | 14.3:1 | Headings, primary content |
| `--text-secondary` | `#3D4F63` | 7.1:1 | Table cells, descriptions |
| `--text-muted` | `#697A8D` | 4.6:1 | Labels, captions, timestamps |

### Navigation (dark sidebar — Zamp-derived dark sections)
| Token | Value | Usage |
|---|---|---|
| `--nav-bg` | `#1A1F2E` | Sidebar background (cool dark navy) |
| `--nav-surface` | `#252B3B` | Active nav item, hover |
| `--nav-accent` | `#34D399` | System status dots |

### Status (semantic product colors)
| Decision | Text | Background | Border |
|---|---|---|---|
| Approved | `#16A34A` | `#F0FDF4` | `#BBF7D0` |
| Review | `#CA8A04` | `#FEFCE8` | `#FDE68A` |
| Information | `#0284C7` | `#F0F9FF` | `#BAE6FD` |
| Blocked | `#DC2626` | `#FEF2F2` | `#FECACA` |

## Typography
- **Font**: `-apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif`
- **Mono**: `ui-monospace, "SF Mono", "Cascadia Code", "Consolas", monospace`
- **Body**: 14px, line-height 1.55
- **Tabular figures**: `font-variant-numeric: tabular-nums` on body (monetary alignment)
- **Heading weight**: 600–650 with negative letter-spacing

## Control Sizes
- Button height: 40px (default), 32px (small), 46px (large)
- Input height: 40px
- Border radius: 10px controls, 14px panels, 8px small elements
- Focus ring: `box-shadow: 0 0 0 3px rgba(7,88,168,0.15)` (blue, not green — focus ≠ brand action)

## What Was NOT Claimed As Brand
- Electric blue is an InvoicePilot design choice
- Status colors are semantic product decisions
- Typography and spacing refinements are design quality choices
- The dark sidebar is derived from Zamp's dark sections, not copied exactly

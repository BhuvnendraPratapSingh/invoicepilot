"""Generate realistic synthetic PDF invoice fixtures using ReportLab.

Each fixture is a genuine PDF with real text content — not a template lookup.
Three distinct vendor layouts with different label arrangements.
"""

import os
import sys
from pathlib import Path
from decimal import Decimal
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_LEFT, TA_CENTER

# Ensure Pillow and ReportLab are available
try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
except ImportError:
    print("Pillow is required: pip install Pillow")
    sys.exit(1)

FIXTURE_DIR = Path("data/fixtures")
FIXTURE_DIR.mkdir(parents=True, exist_ok=True)


def fmt_money(cents: int) -> str:
    """Format cents as dollar string."""
    d = Decimal(cents) / Decimal(100)
    return f"${d:,.2f}"


# ─── Layout 1: Apex Digital - Modern Clean Layout ────────────────────────

def generate_happy_path():
    """Happy path: Apex Digital Solutions, PO-1001, $2,500.00 net."""
    path = FIXTURE_DIR / "happy_path_apex_invoice.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=letter,
                            leftMargin=0.75*inch, rightMargin=0.75*inch,
                            topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []

    # Company header
    header_style = ParagraphStyle('Header', parent=styles['Title'], fontSize=18,
                                   textColor=colors.HexColor('#1a5276'))
    story.append(Paragraph("APEX DIGITAL SOLUTIONS", header_style))
    story.append(Paragraph("100 Innovation Drive, Austin, TX 78701", styles['Normal']))
    story.append(Paragraph("Tax ID: 84-2917365", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))

    # Invoice title
    inv_title = ParagraphStyle('InvTitle', parent=styles['Heading1'], fontSize=24,
                                textColor=colors.HexColor('#2c3e50'))
    story.append(Paragraph("INVOICE", inv_title))
    story.append(Spacer(1, 0.15*inch))

    # Invoice details table
    detail_data = [
        ["Invoice Number:", "INV-2026-0451", "Invoice Date:", "March 10, 2026"],
        ["Due Date:", "April 9, 2026", "Currency:", "USD"],
        ["PO Reference:", "PO-1001", "Payment Terms:", "Net 30"],
    ]
    detail_table = Table(detail_data, colWidths=[1.5*inch, 2*inch, 1.5*inch, 2*inch])
    detail_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(detail_table)
    story.append(Spacer(1, 0.2*inch))

    # Bill To
    story.append(Paragraph("<b>Bill To:</b>", styles['Normal']))
    story.append(Paragraph("Acme Corporation", styles['Normal']))
    story.append(Paragraph("500 Business Park, Suite 200, Dallas, TX 75201", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))

    # Service description
    story.append(Paragraph("<b>Service Description:</b> UI/UX design and frontend development for corporate website refresh", styles['Normal']))
    story.append(Spacer(1, 0.15*inch))

    # Line items
    line_data = [
        ["#", "Description", "Qty", "Unit Price", "Amount"],
        ["1", "UX Research & Wireframing", "40 hrs", "$50.00", "$2,000.00"],
        ["2", "Visual Design Mockups", "10 hrs", "$50.00", "$500.00"],
    ]
    line_table = Table(line_data, colWidths=[0.4*inch, 3.2*inch, 0.8*inch, 1.1*inch, 1.1*inch])
    line_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 0.15*inch))

    # Totals
    right_style = ParagraphStyle('Right', parent=styles['Normal'], alignment=TA_RIGHT)
    totals_data = [
        ["", "", "Subtotal:", "$2,500.00"],
        ["", "", "Tax (8%):", "$200.00"],
        ["", "", "Total Due:", "$2,700.00"],
    ]
    totals_table = Table(totals_data, colWidths=[2*inch, 2*inch, 1.5*inch, 1.2*inch])
    totals_table.setStyle(TableStyle([
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('LINEABOVE', (2, -1), (-1, -1), 1.5, colors.black),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(totals_table)
    story.append(Spacer(1, 0.3*inch))

    # Footer
    story.append(Paragraph("Thank you for your business.", styles['Normal']))
    story.append(Paragraph("Please remit payment to: Apex Digital Solutions, Bank: First National, Acct: XXXX-7890", styles['Normal']))

    doc.build(story)
    print(f"  ✓ Happy path: {path}")
    return path


# ─── Layout 2: Meridian Consulting - Different label order ──────────────

def generate_duplicate_original():
    """Seeded approved invoice for duplicate testing. Meridian Consulting layout."""
    path = FIXTURE_DIR / "duplicate_original_meridian.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=letter,
                            leftMargin=0.75*inch, rightMargin=0.75*inch,
                            topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []

    # Different layout: right-aligned header
    header_style = ParagraphStyle('Header', parent=styles['Title'], fontSize=16,
                                   alignment=TA_RIGHT, textColor=colors.HexColor('#8b0000'))
    story.append(Paragraph("Meridian Consulting Group", header_style))
    addr_right = ParagraphStyle('AddrRight', parent=styles['Normal'], alignment=TA_RIGHT)
    story.append(Paragraph("250 Commerce Blvd, Suite 400, Chicago, IL 60601", addr_right))
    story.append(Paragraph("EIN: 37-8104926", addr_right))
    story.append(Spacer(1, 0.3*inch))

    # Invoice label and details (different order from Layout 1)
    inv_title = ParagraphStyle('InvTitle', parent=styles['Heading2'], fontSize=20)
    story.append(Paragraph("TAX INVOICE", inv_title))
    story.append(Spacer(1, 0.1*inch))

    # Note: Labels in different order
    detail_data = [
        ["Date of Invoice:", "February 15, 2026"],
        ["Invoice Ref:", "MCG-2026-0088"],
        ["Purchase Order:", "PO-1002"],
        ["Currency:", "USD"],
        ["Terms:", "Net 45"],
    ]
    detail_table = Table(detail_data, colWidths=[2*inch, 4*inch])
    detail_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(detail_table)
    story.append(Spacer(1, 0.2*inch))

    # Client info
    story.append(Paragraph("<b>Client:</b> Acme Corporation", styles['Normal']))
    story.append(Spacer(1, 0.15*inch))

    # Bundled service line (no qty/unit price breakdown)
    story.append(Paragraph("<b>Services Rendered:</b>", styles['Normal']))
    line_data = [
        ["Description", "Amount"],
        ["Strategic consulting services - Q1 2026 Phase 1\nOrganizational restructuring assessment and roadmap", "$3,500.00"],
    ]
    line_table = Table(line_data, colWidths=[5*inch, 1.5*inch])
    line_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8b0000')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 0.15*inch))

    # Totals (different format)
    totals_data = [
        ["Subtotal", "$3,500.00"],
        ["Sales Tax (8%)", "$280.00"],
        ["TOTAL DUE", "$3,780.00"],
    ]
    totals_table = Table(totals_data, colWidths=[5*inch, 1.5*inch])
    totals_table.setStyle(TableStyle([
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('LINEABOVE', (0, -1), (-1, -1), 1.5, colors.black),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(totals_table)

    doc.build(story)
    print(f"  ✓ Duplicate original (Meridian): {path}")
    return path


def generate_duplicate_reissued():
    """Same vendor/invoice#/amounts as original but different PDF bytes. For BLOCKED test."""
    path = FIXTURE_DIR / "duplicate_reissued_meridian.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=letter,
                            leftMargin=0.8*inch, rightMargin=0.8*inch,
                            topMargin=0.6*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []

    # Slightly different layout but same business data
    header_style = ParagraphStyle('Header', parent=styles['Title'], fontSize=15,
                                   textColor=colors.HexColor('#8b0000'))
    story.append(Paragraph("MERIDIAN CONSULTING GROUP", header_style))
    story.append(Paragraph("250 Commerce Blvd, Suite 400, Chicago, IL 60601 | EIN: 37-8104926", styles['Normal']))
    story.append(Spacer(1, 0.25*inch))

    story.append(Paragraph("<b>INVOICE</b>", ParagraphStyle('Big', parent=styles['Normal'], fontSize=18)))
    story.append(Spacer(1, 0.1*inch))

    # Same data, different table format
    detail_data = [
        ["Invoice #: MCG-2026-0088", "Date: February 15, 2026"],
        ["PO: PO-1002", "Due: April 1, 2026"],
        ["Currency: USD", "Terms: Net 45"],
    ]
    detail_table = Table(detail_data, colWidths=[3.3*inch, 3.3*inch])
    detail_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(detail_table)
    story.append(Spacer(1, 0.2*inch))

    story.append(Paragraph("Bill To: Acme Corporation", styles['Normal']))
    story.append(Spacer(1, 0.15*inch))

    line_data = [
        ["Service", "Total"],
        ["Strategic consulting - Q1 2026 Phase 1 (restructuring assessment)", "$3,500.00"],
    ]
    line_table = Table(line_data, colWidths=[5*inch, 1.5*inch])
    line_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 0.15*inch))

    totals_data = [
        ["Subtotal:", "$3,500.00"],
        ["Tax:", "$280.00"],
        ["Amount Due:", "$3,780.00"],
    ]
    totals_table = Table(totals_data, colWidths=[5*inch, 1.5*inch])
    totals_table.setStyle(TableStyle([
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),
    ]))
    story.append(totals_table)

    doc.build(story)
    print(f"  ✓ Duplicate reissued: {path}")
    return path


def generate_duplicate_collision():
    """Same vendor/invoice# but DIFFERENT amounts. Identity collision."""
    path = FIXTURE_DIR / "duplicate_collision_meridian.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=letter,
                            leftMargin=0.75*inch, rightMargin=0.75*inch,
                            topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []

    header_style = ParagraphStyle('Header', parent=styles['Title'], fontSize=16,
                                   alignment=TA_RIGHT, textColor=colors.HexColor('#8b0000'))
    story.append(Paragraph("Meridian Consulting Group", header_style))
    addr_right = ParagraphStyle('AddrRight', parent=styles['Normal'], alignment=TA_RIGHT)
    story.append(Paragraph("250 Commerce Blvd, Suite 400, Chicago, IL 60601", addr_right))
    story.append(Paragraph("EIN: 37-8104926", addr_right))
    story.append(Spacer(1, 0.3*inch))

    story.append(Paragraph("REVISED INVOICE", ParagraphStyle('Big', parent=styles['Heading2'], fontSize=20)))
    story.append(Spacer(1, 0.1*inch))

    detail_data = [
        ["Invoice Ref:", "MCG-2026-0088"],  # Same invoice number!
        ["Date:", "February 20, 2026"],
        ["Purchase Order:", "PO-1002"],
        ["Currency:", "USD"],
    ]
    detail_table = Table(detail_data, colWidths=[2*inch, 4*inch])
    detail_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
    ]))
    story.append(detail_table)
    story.append(Spacer(1, 0.15*inch))

    line_data = [
        ["Description", "Amount"],
        ["Strategic consulting - Q1 2026 Phase 1 (revised scope)", "$3,800.00"],  # Different amount!
    ]
    line_table = Table(line_data, colWidths=[5*inch, 1.5*inch])
    line_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8b0000')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 0.15*inch))

    totals_data = [
        ["Subtotal", "$3,800.00"],
        ["Tax (8%)", "$304.00"],
        ["TOTAL", "$4,104.00"],
    ]
    totals_table = Table(totals_data, colWidths=[5*inch, 1.5*inch])
    totals_table.setStyle(TableStyle([
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('LINEABOVE', (0, -1), (-1, -1), 1.5, colors.black),
    ]))
    story.append(totals_table)

    doc.build(story)
    print(f"  ✓ Duplicate collision: {path}")
    return path


# ─── Edge Family 2: Cumulative tolerance ─────────────────────────────────

def generate_cumulative_a():
    """Invoice A: net $4,040.00 against PO-1002 ($10k PO, $6k committed). Should auto-approve."""
    path = FIXTURE_DIR / "cumulative_a_meridian.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=letter,
                            leftMargin=0.75*inch, rightMargin=0.75*inch,
                            topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []

    header_style = ParagraphStyle('Header', parent=styles['Title'], fontSize=16,
                                   alignment=TA_RIGHT, textColor=colors.HexColor('#8b0000'))
    story.append(Paragraph("Meridian Consulting Group", header_style))
    story.append(Paragraph("250 Commerce Blvd, Suite 400, Chicago, IL 60601",
                           ParagraphStyle('R', parent=styles['Normal'], alignment=TA_RIGHT)))
    story.append(Paragraph("EIN: 37-8104926",
                           ParagraphStyle('R', parent=styles['Normal'], alignment=TA_RIGHT)))
    story.append(Spacer(1, 0.3*inch))

    story.append(Paragraph("INVOICE", ParagraphStyle('Big', parent=styles['Heading2'], fontSize=20)))
    story.append(Spacer(1, 0.1*inch))

    detail_data = [
        ["Invoice Number:", "MCG-2026-0201"],
        ["Date:", "March 5, 2026"],
        ["Purchase Order:", "PO-1002"],
        ["Currency:", "USD"],
    ]
    detail_table = Table(detail_data, colWidths=[2*inch, 4*inch])
    detail_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
    ]))
    story.append(detail_table)
    story.append(Spacer(1, 0.2*inch))

    line_data = [
        ["Description", "Amount"],
        ["Q1 consulting services - Phase 2 organizational restructuring", "$4,040.00"],
    ]
    line_table = Table(line_data, colWidths=[5*inch, 1.5*inch])
    line_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8b0000')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 0.15*inch))

    totals_data = [
        ["Subtotal", "$4,040.00"],
        ["Tax (8%)", "$323.20"],
        ["Total Due", "$4,363.20"],
    ]
    totals_table = Table(totals_data, colWidths=[5*inch, 1.5*inch])
    totals_table.setStyle(TableStyle([
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('LINEABOVE', (0, -1), (-1, -1), 1.5, colors.black),
    ]))
    story.append(totals_table)

    doc.build(story)
    print(f"  ✓ Cumulative A (within tolerance): {path}")
    return path


def generate_cumulative_b():
    """Invoice B: net $4,060.00. From fresh reset, projected $10,060 > ceiling $10,050."""
    path = FIXTURE_DIR / "cumulative_b_meridian.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=letter,
                            leftMargin=0.75*inch, rightMargin=0.75*inch,
                            topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []

    header_style = ParagraphStyle('Header', parent=styles['Title'], fontSize=16,
                                   alignment=TA_RIGHT, textColor=colors.HexColor('#8b0000'))
    story.append(Paragraph("Meridian Consulting Group", header_style))
    story.append(Paragraph("250 Commerce Blvd, Suite 400, Chicago, IL 60601",
                           ParagraphStyle('R', parent=styles['Normal'], alignment=TA_RIGHT)))
    story.append(Paragraph("EIN: 37-8104926",
                           ParagraphStyle('R', parent=styles['Normal'], alignment=TA_RIGHT)))
    story.append(Spacer(1, 0.3*inch))

    story.append(Paragraph("INVOICE", ParagraphStyle('Big', parent=styles['Heading2'], fontSize=20)))
    story.append(Spacer(1, 0.1*inch))

    detail_data = [
        ["Invoice Number:", "MCG-2026-0202"],
        ["Date:", "March 8, 2026"],
        ["Purchase Order:", "PO-1002"],
        ["Currency:", "USD"],
    ]
    detail_table = Table(detail_data, colWidths=[2*inch, 4*inch])
    detail_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
    ]))
    story.append(detail_table)
    story.append(Spacer(1, 0.2*inch))

    line_data = [
        ["Description", "Amount"],
        ["Q1 consulting services - Phase 2 restructuring execution", "$4,060.00"],
    ]
    line_table = Table(line_data, colWidths=[5*inch, 1.5*inch])
    line_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8b0000')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 0.15*inch))

    totals_data = [
        ["Subtotal", "$4,060.00"],
        ["Tax (8%)", "$324.80"],
        ["Total Due", "$4,384.80"],
    ]
    totals_table = Table(totals_data, colWidths=[5*inch, 1.5*inch])
    totals_table.setStyle(TableStyle([
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('LINEABOVE', (0, -1), (-1, -1), 1.5, colors.black),
    ]))
    story.append(totals_table)

    doc.build(story)
    print(f"  ✓ Cumulative B (exceeds tolerance): {path}")
    return path


def generate_cumulative_c():
    """Invoice C: net $20.00. Small amount that tips cumulative past ceiling after A."""
    path = FIXTURE_DIR / "cumulative_c_meridian.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=letter,
                            leftMargin=0.75*inch, rightMargin=0.75*inch,
                            topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []

    header_style = ParagraphStyle('Header', parent=styles['Title'], fontSize=16,
                                   alignment=TA_RIGHT, textColor=colors.HexColor('#8b0000'))
    story.append(Paragraph("Meridian Consulting Group", header_style))
    story.append(Paragraph("250 Commerce Blvd, Suite 400, Chicago, IL 60601",
                           ParagraphStyle('R', parent=styles['Normal'], alignment=TA_RIGHT)))
    story.append(Paragraph("EIN: 37-8104926",
                           ParagraphStyle('R', parent=styles['Normal'], alignment=TA_RIGHT)))
    story.append(Spacer(1, 0.25*inch))

    story.append(Paragraph("INVOICE", ParagraphStyle('Big', parent=styles['Heading2'], fontSize=20)))
    story.append(Spacer(1, 0.1*inch))

    detail_data = [
        ["Invoice Number:", "MCG-2026-0203"],
        ["Date:", "March 12, 2026"],
        ["Purchase Order:", "PO-1002"],
        ["Currency:", "USD"],
    ]
    detail_table = Table(detail_data, colWidths=[2*inch, 4*inch])
    detail_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
    ]))
    story.append(detail_table)
    story.append(Spacer(1, 0.15*inch))

    line_data = [
        ["Description", "Amount"],
        ["Additional consulting follow-up - minor scope clarification", "$20.00"],
    ]
    line_table = Table(line_data, colWidths=[5*inch, 1.5*inch])
    line_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8b0000')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 0.1*inch))

    totals_data = [
        ["Subtotal", "$20.00"],
        ["Tax (8%)", "$1.60"],
        ["Total Due", "$21.60"],
    ]
    totals_table = Table(totals_data, colWidths=[5*inch, 1.5*inch])
    totals_table.setStyle(TableStyle([
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),
    ]))
    story.append(totals_table)

    doc.build(story)
    print(f"  ✓ Cumulative C (small follow-up): {path}")
    return path


# ─── Edge Family 3: Ambiguous PO ─────────────────────────────────────────

def generate_ambiguous_po():
    """Invoice from Brightwave with no PO ref. Two plausible POs exist."""
    path = FIXTURE_DIR / "ambiguous_po_brightwave.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=letter,
                            leftMargin=0.75*inch, rightMargin=0.75*inch,
                            topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []

    # Layout 3: Brightwave - centered header
    header_style = ParagraphStyle('Header', parent=styles['Title'], fontSize=17,
                                   alignment=TA_CENTER, textColor=colors.HexColor('#2e86c1'))
    story.append(Paragraph("Brightwave Analytics Inc", header_style))
    center_style = ParagraphStyle('Center', parent=styles['Normal'], alignment=TA_CENTER)
    story.append(Paragraph("320 Data Lane, San Francisco, CA 94105", center_style))
    story.append(Paragraph("Tax ID: 52-3908174", center_style))
    story.append(Spacer(1, 0.3*inch))

    # Note: NO PO reference in this invoice
    inv_style = ParagraphStyle('InvLabel', parent=styles['Normal'], fontSize=14,
                                textColor=colors.HexColor('#2e86c1'))
    story.append(Paragraph("Invoice No: BW-INV-2026-055", inv_style))
    story.append(Spacer(1, 0.1*inch))

    detail_data = [
        ["Invoice Date:", "March 11, 2026"],
        ["Due Date:", "April 10, 2026"],
        ["Currency:", "USD"],
        ["Client:", "Acme Corporation"],
    ]
    detail_table = Table(detail_data, colWidths=[1.5*inch, 5*inch])
    detail_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(detail_table)
    story.append(Spacer(1, 0.2*inch))

    # Bundled service description that could match either PO
    line_data = [
        ["Service Description", "Net Amount"],
        ["Data analytics and reporting services - Q1 2026\nPipeline optimization and dashboard development", "$1,500.00"],
    ]
    line_table = Table(line_data, colWidths=[5*inch, 1.5*inch])
    line_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2e86c1')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 0.15*inch))

    totals_data = [
        ["Subtotal:", "$1,500.00"],
        ["Sales Tax (8%):", "$120.00"],
        ["Total:", "$1,620.00"],
    ]
    totals_table = Table(totals_data, colWidths=[5*inch, 1.5*inch])
    totals_table.setStyle(TableStyle([
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('LINEABOVE', (0, -1), (-1, -1), 1.5, colors.black),
    ]))
    story.append(totals_table)

    doc.build(story)
    print(f"  ✓ Ambiguous PO (Brightwave): {path}")
    return path


# ─── Edge Family 4: Scanned / Missing Invoice Number ────────────────────

def generate_scanned_missing_number():
    """Create a genuine raster-only scanned PDF with NO invoice number.
    
    This generates an image of an invoice, adds realistic scan artifacts,
    and embeds it in a PDF with NO text layer.
    """
    path = FIXTURE_DIR / "scanned_missing_number_pinnacle.pdf"
    img_path = FIXTURE_DIR / "_temp_scan.png"

    # Create invoice image
    width, height = 2550, 3300  # 300 DPI letter size
    img = Image.new('RGB', (width, height), '#f8f8f0')  # Slightly off-white
    draw = ImageDraw.Draw(img)

    # Use a basic font (no system font dependency)
    try:
        font_large = ImageFont.truetype("arial.ttf", 60)
        font_medium = ImageFont.truetype("arial.ttf", 40)
        font_normal = ImageFont.truetype("arial.ttf", 32)
        font_bold = ImageFont.truetype("arialbd.ttf", 36)
    except (IOError, OSError):
        font_large = ImageFont.load_default()
        font_medium = font_large
        font_normal = font_large
        font_bold = font_large

    # Draw invoice content (NO invoice number anywhere)
    y = 150
    draw.text((150, y), "PINNACLE CLOUD SERVICES", fill='#1a5276', font=font_large)
    y += 80
    draw.text((150, y), "1800 Tech Park Way, Seattle, WA 98101", fill='#333', font=font_normal)
    y += 50
    draw.text((150, y), "Tax ID: 61-5283047", fill='#333', font=font_normal)
    y += 100

    draw.text((150, y), "INVOICE", fill='#2c3e50', font=font_large)
    y += 100

    # Note: deliberately NO invoice number field
    draw.text((150, y), "Date: March 13, 2026", fill='#333', font=font_normal)
    y += 50
    draw.text((150, y), "Purchase Order: PO-1003", fill='#333', font=font_normal)
    y += 50
    draw.text((150, y), "Currency: USD", fill='#333', font=font_normal)
    y += 50
    draw.text((150, y), "Terms: Net 30", fill='#333', font=font_normal)
    y += 80

    draw.text((150, y), "Bill To: Acme Corporation", fill='#333', font=font_bold)
    y += 70

    # Table header
    draw.rectangle([(150, y), (2400, y+55)], fill='#2c3e50')
    draw.text((170, y+10), "Description", fill='white', font=font_bold)
    draw.text((1900, y+10), "Amount", fill='white', font=font_bold)
    y += 55

    # Line item
    draw.rectangle([(150, y), (2400, y+60)], outline='#ccc')
    draw.text((170, y+12), "Cloud infrastructure migration services - Phase 1", fill='#333', font=font_normal)
    draw.text((1920, y+12), "$800.00", fill='#333', font=font_normal)
    y += 100

    # Totals
    draw.text((1600, y), "Subtotal:", fill='#333', font=font_bold)
    draw.text((1920, y), "$800.00", fill='#333', font=font_normal)
    y += 50
    draw.text((1600, y), "Tax (8%):", fill='#333', font=font_bold)
    draw.text((1920, y), "$64.00", fill='#333', font=font_normal)
    y += 50
    draw.line([(1600, y), (2400, y)], fill='#333', width=2)
    y += 10
    draw.text((1600, y), "Total Due:", fill='#333', font=font_bold)
    draw.text((1920, y), "$864.00", fill='#333', font=font_bold)

    # Add scan artifacts: slight rotation, noise, blur
    img = img.rotate(0.5, fillcolor='#f8f8f0', expand=False)
    img = img.filter(ImageFilter.GaussianBlur(radius=1))

    # Add some noise dots
    import random
    random.seed(42)  # Deterministic
    for _ in range(500):
        x = random.randint(0, width-1)
        y_noise = random.randint(0, height-1)
        gray = random.randint(180, 220)
        draw = ImageDraw.Draw(img)
        draw.point((x, y_noise), fill=(gray, gray, gray))

    img.save(str(img_path), 'PNG', dpi=(300, 300))

    # Create PDF with just the image — NO text layer
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(path), pagesize=letter)
    c.drawImage(str(img_path), 0, 0, width=letter[0], height=letter[1])
    c.save()

    # Clean up temp image
    img_path.unlink(missing_ok=True)

    print(f"  ✓ Scanned missing number (Pinnacle): {path}")
    return path


def generate_scanned_corrected():
    """Corrected version of scanned invoice WITH an invoice number added."""
    path = FIXTURE_DIR / "scanned_corrected_pinnacle.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=letter,
                            leftMargin=0.75*inch, rightMargin=0.75*inch,
                            topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []

    header_style = ParagraphStyle('Header', parent=styles['Title'], fontSize=18,
                                   textColor=colors.HexColor('#1a5276'))
    story.append(Paragraph("PINNACLE CLOUD SERVICES", header_style))
    story.append(Paragraph("1800 Tech Park Way, Seattle, WA 98101", styles['Normal']))
    story.append(Paragraph("Tax ID: 61-5283047", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))

    story.append(Paragraph("INVOICE", ParagraphStyle('Big', parent=styles['Heading1'], fontSize=24,
                                                      textColor=colors.HexColor('#2c3e50'))))
    story.append(Spacer(1, 0.15*inch))

    # NOW includes invoice number
    detail_data = [
        ["Invoice Number:", "PCS-2026-0312"],  # Added!
        ["Date:", "March 13, 2026"],
        ["Purchase Order:", "PO-1003"],
        ["Currency:", "USD"],
    ]
    detail_table = Table(detail_data, colWidths=[2*inch, 4*inch])
    detail_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
    ]))
    story.append(detail_table)
    story.append(Spacer(1, 0.2*inch))

    story.append(Paragraph("<b>Bill To:</b> Acme Corporation", styles['Normal']))
    story.append(Spacer(1, 0.15*inch))

    line_data = [
        ["Description", "Amount"],
        ["Cloud infrastructure migration services - Phase 1", "$800.00"],
    ]
    line_table = Table(line_data, colWidths=[5*inch, 1.5*inch])
    line_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 0.15*inch))

    totals_data = [
        ["Subtotal:", "$800.00"],
        ["Tax (8%):", "$64.00"],
        ["Total Due:", "$864.00"],
    ]
    totals_table = Table(totals_data, colWidths=[5*inch, 1.5*inch])
    totals_table.setStyle(TableStyle([
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('LINEABOVE', (0, -1), (-1, -1), 1.5, colors.black),
    ]))
    story.append(totals_table)

    doc.build(story)
    print(f"  ✓ Scanned corrected (Pinnacle): {path}")
    return path


def main():
    print("Generating InvoicePilot PDF fixtures...")
    print()

    # Happy path
    generate_happy_path()

    # Edge family 1: Duplicates
    generate_duplicate_original()
    generate_duplicate_reissued()
    generate_duplicate_collision()

    # Edge family 2: Cumulative tolerance
    generate_cumulative_a()
    generate_cumulative_b()
    generate_cumulative_c()

    # Edge family 3: Ambiguous PO
    generate_ambiguous_po()

    # Edge family 4: Scanned / missing number
    generate_scanned_missing_number()
    generate_scanned_corrected()

    print()
    print(f"All fixtures generated in {FIXTURE_DIR}/")


if __name__ == "__main__":
    main()

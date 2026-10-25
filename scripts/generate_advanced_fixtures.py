"""Generate PDF fixtures for the four advanced edge-case scenarios."""
import random
from pathlib import Path
from decimal import Decimal
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from reportlab.pdfgen import canvas
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FIXTURE_DIR = Path("data/fixtures")
FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

def fmt(cents):
    return "${:,.2f}".format(Decimal(cents) / Decimal(100))

# ═══════════════════════════════════════════════════
# SCENARIO A: Stale review — two invoices for V-002
# ═══════════════════════════════════════════════════

def gen_scenario_a_invoice_a():
    """Invoice A: V-002 Meridian, NO PO reference, $4,000 net. Gets PO_AMBIGUOUS."""
    path = FIXTURE_DIR / "adv_stale_review_a.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=letter, leftMargin=0.75*inch, rightMargin=0.75*inch,
                            topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []
    hdr = ParagraphStyle('H', parent=styles['Title'], fontSize=16, alignment=TA_RIGHT,
                          textColor=colors.HexColor('#8b0000'))
    story.append(Paragraph("Meridian Consulting Group", hdr))
    rs = ParagraphStyle('R', parent=styles['Normal'], alignment=TA_RIGHT)
    story.append(Paragraph("250 Commerce Blvd, Suite 400, Chicago, IL 60601", rs))
    story.append(Paragraph("EIN: 37-8104926", rs))
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph("INVOICE", ParagraphStyle('B', parent=styles['Heading2'], fontSize=20)))
    story.append(Spacer(1, 0.1*inch))
    # NO PO reference — this is the key for ambiguity
    det = [["Invoice Number:", "MCG-2026-0500"], ["Date:", "March 12, 2026"],
           ["Currency:", "USD"]]
    t = Table(det, colWidths=[2*inch, 4*inch])
    t.setStyle(TableStyle([('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),10)]))
    story.append(t)
    story.append(Spacer(1, 0.2*inch))
    lt = Table([["Description","Amount"],
                ["Strategic consulting services — Q1 organizational restructuring Phase 2", "$4,000.00"]],
               colWidths=[5*inch, 1.5*inch])
    lt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#8b0000')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),0.5,colors.grey),
        ('ALIGN',(1,0),(1,-1),'RIGHT'),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
    story.append(lt)
    story.append(Spacer(1, 0.15*inch))
    tt = Table([["Subtotal","$4,000.00"],["Tax (8%)","$320.00"],["Total Due","$4,320.00"]],
               colWidths=[5*inch, 1.5*inch])
    tt.setStyle(TableStyle([('FONTNAME',(0,-1),(-1,-1),'Helvetica-Bold'),
        ('ALIGN',(1,0),(1,-1),'RIGHT'),('LINEABOVE',(0,-1),(-1,-1),1.5,colors.black)]))
    story.append(tt)
    doc.build(story)
    print(f"  A-a: {path.name}")

def gen_scenario_a_invoice_b():
    """Invoice B: V-002 Meridian, explicit PO-1002, $200 net. Will auto-approve."""
    path = FIXTURE_DIR / "adv_stale_review_b.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=letter, leftMargin=0.75*inch, rightMargin=0.75*inch,
                            topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []
    hdr = ParagraphStyle('H', parent=styles['Title'], fontSize=16, alignment=TA_RIGHT,
                          textColor=colors.HexColor('#8b0000'))
    story.append(Paragraph("Meridian Consulting Group", hdr))
    rs = ParagraphStyle('R', parent=styles['Normal'], alignment=TA_RIGHT)
    story.append(Paragraph("250 Commerce Blvd, Suite 400, Chicago, IL 60601", rs))
    story.append(Paragraph("EIN: 37-8104926", rs))
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph("INVOICE", ParagraphStyle('B', parent=styles['Heading2'], fontSize=20)))
    story.append(Spacer(1, 0.1*inch))
    det = [["Invoice Number:", "MCG-2026-0501"], ["Date:", "March 13, 2026"],
           ["Purchase Order:", "PO-1002"], ["Currency:", "USD"]]
    t = Table(det, colWidths=[2*inch, 4*inch])
    t.setStyle(TableStyle([('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),10)]))
    story.append(t)
    story.append(Spacer(1, 0.2*inch))
    lt = Table([["Description","Amount"],["Additional consulting follow-up — minor advisory","$200.00"]],
               colWidths=[5*inch, 1.5*inch])
    lt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#8b0000')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),0.5,colors.grey),
        ('ALIGN',(1,0),(1,-1),'RIGHT'),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
    story.append(lt)
    story.append(Spacer(1, 0.15*inch))
    tt = Table([["Subtotal","$200.00"],["Tax (8%)","$16.00"],["Total Due","$216.00"]],
               colWidths=[5*inch, 1.5*inch])
    tt.setStyle(TableStyle([('FONTNAME',(0,-1),(-1,-1),'Helvetica-Bold'),
        ('ALIGN',(1,0),(1,-1),'RIGHT'),('LINEABOVE',(0,-1),(-1,-1),1.5,colors.black)]))
    story.append(tt)
    doc.build(story)
    print(f"  A-b: {path.name}")

# ═══════════════════════════════════════════════════
# SCENARIO B: Correction after approval — V-001 Apex
# ═══════════════════════════════════════════════════

def gen_scenario_b_original():
    """Original invoice ADV-CORR-1042: Apex, PO-1001, $2,000 net."""
    path = FIXTURE_DIR / "adv_correction_original.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=letter, leftMargin=0.75*inch, rightMargin=0.75*inch,
                            topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph("APEX DIGITAL SOLUTIONS", ParagraphStyle('H', parent=styles['Title'],
                 fontSize=18, textColor=colors.HexColor('#1a5276'))))
    story.append(Paragraph("100 Innovation Drive, Austin, TX 78701", styles['Normal']))
    story.append(Paragraph("Tax ID: 84-2917365", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph("INVOICE", ParagraphStyle('T', parent=styles['Heading1'], fontSize=24,
                 textColor=colors.HexColor('#2c3e50'))))
    story.append(Spacer(1, 0.15*inch))
    det = [["Invoice Number:", "ADV-CORR-1042", "Invoice Date:", "March 8, 2026"],
           ["PO Reference:", "PO-1001", "Currency:", "USD"]]
    t = Table(det, colWidths=[1.5*inch, 2*inch, 1.5*inch, 2*inch])
    t.setStyle(TableStyle([('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),
        ('FONTNAME',(2,0),(2,-1),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),10)]))
    story.append(t)
    story.append(Spacer(1, 0.2*inch))
    lt = Table([["#","Description","Amount"],["1","UX Research — Phase 1","$2,000.00"]],
               colWidths=[0.4*inch, 4.5*inch, 1.5*inch])
    lt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#2c3e50')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('GRID',(0,0),(-1,-1),0.5,colors.grey),('ALIGN',(2,0),(2,-1),'RIGHT'),
        ('BOTTOMPADDING',(0,0),(-1,-1),8)]))
    story.append(lt)
    story.append(Spacer(1, 0.15*inch))
    tt = Table([["Subtotal:","$2,000.00"],["Tax (8%):","$160.00"],["Total Due:","$2,160.00"]],
               colWidths=[5*inch, 1.5*inch])
    tt.setStyle(TableStyle([('FONTNAME',(0,-1),(-1,-1),'Helvetica-Bold'),
        ('ALIGN',(1,0),(1,-1),'RIGHT'),('LINEABOVE',(0,-1),(-1,-1),1.5,colors.black)]))
    story.append(tt)
    doc.build(story)
    print(f"  B-orig: {path.name}")

def gen_scenario_b_correction():
    """Correction of ADV-CORR-1042: same invoice#, $2,300 net (different amount)."""
    path = FIXTURE_DIR / "adv_correction_revised.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=letter, leftMargin=0.75*inch, rightMargin=0.75*inch,
                            topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph("APEX DIGITAL SOLUTIONS", ParagraphStyle('H', parent=styles['Title'],
                 fontSize=18, textColor=colors.HexColor('#1a5276'))))
    story.append(Paragraph("100 Innovation Drive, Austin, TX 78701", styles['Normal']))
    story.append(Paragraph("Tax ID: 84-2917365", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph("CORRECTED INVOICE", ParagraphStyle('T', parent=styles['Heading1'], fontSize=24,
                 textColor=colors.HexColor('#c0392b'))))
    story.append(Spacer(1, 0.15*inch))
    det = [["Invoice Number:", "ADV-CORR-1042", "Invoice Date:", "March 14, 2026"],
           ["PO Reference:", "PO-1001", "Currency:", "USD"]]
    t = Table(det, colWidths=[1.5*inch, 2*inch, 1.5*inch, 2*inch])
    t.setStyle(TableStyle([('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),
        ('FONTNAME',(2,0),(2,-1),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),10)]))
    story.append(t)
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph("<b>Note:</b> This corrected invoice supersedes the original submission.", styles['Normal']))
    story.append(Spacer(1, 0.1*inch))
    lt = Table([["#","Description","Amount"],["1","UX Research — Phase 1 (revised scope)","$2,300.00"]],
               colWidths=[0.4*inch, 4.5*inch, 1.5*inch])
    lt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#2c3e50')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('GRID',(0,0),(-1,-1),0.5,colors.grey),('ALIGN',(2,0),(2,-1),'RIGHT'),
        ('BOTTOMPADDING',(0,0),(-1,-1),8)]))
    story.append(lt)
    story.append(Spacer(1, 0.15*inch))
    tt = Table([["Subtotal:","$2,300.00"],["Tax (8%):","$184.00"],["Total Due:","$2,484.00"]],
               colWidths=[5*inch, 1.5*inch])
    tt.setStyle(TableStyle([('FONTNAME',(0,-1),(-1,-1),'Helvetica-Bold'),
        ('ALIGN',(1,0),(1,-1),'RIGHT'),('LINEABOVE',(0,-1),(-1,-1),1.5,colors.black)]))
    story.append(tt)
    doc.build(story)
    print(f"  B-corr: {path.name}")

# ═══════════════════════════════════════════════════
# SCENARIO C: PO belongs to another vendor
# ═══════════════════════════════════════════════════

def gen_scenario_c():
    """Invoice from Apex (V-001) citing PO-1002 which belongs to Meridian (V-002)."""
    path = FIXTURE_DIR / "adv_wrong_vendor_po.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=letter, leftMargin=0.75*inch, rightMargin=0.75*inch,
                            topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph("APEX DIGITAL SOLUTIONS", ParagraphStyle('H', parent=styles['Title'],
                 fontSize=18, textColor=colors.HexColor('#1a5276'))))
    story.append(Paragraph("100 Innovation Drive, Austin, TX 78701", styles['Normal']))
    story.append(Paragraph("Tax ID: 84-2917365", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph("INVOICE", ParagraphStyle('T', parent=styles['Heading1'], fontSize=24,
                 textColor=colors.HexColor('#2c3e50'))))
    story.append(Spacer(1, 0.15*inch))
    # PO-1002 belongs to V-002 Meridian, NOT V-001 Apex
    det = [["Invoice Number:", "APX-2026-0777", "Invoice Date:", "March 10, 2026"],
           ["PO Reference:", "PO-1002", "Currency:", "USD"]]
    t = Table(det, colWidths=[1.5*inch, 2*inch, 1.5*inch, 2*inch])
    t.setStyle(TableStyle([('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),
        ('FONTNAME',(2,0),(2,-1),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),10)]))
    story.append(t)
    story.append(Spacer(1, 0.2*inch))
    lt = Table([["#","Description","Amount"],["1","Consulting services","$500.00"]],
               colWidths=[0.4*inch, 4.5*inch, 1.5*inch])
    lt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#2c3e50')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('GRID',(0,0),(-1,-1),0.5,colors.grey),('ALIGN',(2,0),(2,-1),'RIGHT'),
        ('BOTTOMPADDING',(0,0),(-1,-1),8)]))
    story.append(lt)
    story.append(Spacer(1, 0.15*inch))
    tt = Table([["Subtotal:","$500.00"],["Tax (8%):","$40.00"],["Total Due:","$540.00"]],
               colWidths=[5*inch, 1.5*inch])
    tt.setStyle(TableStyle([('FONTNAME',(0,-1),(-1,-1),'Helvetica-Bold'),
        ('ALIGN',(1,0),(1,-1),'RIGHT'),('LINEABOVE',(0,-1),(-1,-1),1.5,colors.black)]))
    story.append(tt)
    doc.build(story)
    print(f"  C: {path.name}")

# ═══════════════════════════════════════════════════
# SCENARIO D: OCR with distractor identifiers
# ═══════════════════════════════════════════════════

def gen_scenario_d_missing():
    """Scanned image-only PDF: has account#, service ref, PO, but NO invoice number."""
    path = FIXTURE_DIR / "adv_ocr_distractors.pdf"
    width, height = 2550, 3300
    img = Image.new('RGB', (width, height), '#f9f9f2')
    draw = ImageDraw.Draw(img)
    try:
        font_large = ImageFont.truetype("arial.ttf", 56)
        font_med = ImageFont.truetype("arial.ttf", 38)
        font_norm = ImageFont.truetype("arial.ttf", 30)
        font_bold = ImageFont.truetype("arialbd.ttf", 34)
    except (IOError, OSError):
        font_large = ImageFont.load_default()
        font_med = font_large; font_norm = font_large; font_bold = font_large

    y = 140
    draw.text((150, y), "PINNACLE CLOUD SERVICES", fill='#1a5276', font=font_large); y += 75
    draw.text((150, y), "1800 Tech Park Way, Seattle, WA 98101", fill='#333', font=font_norm); y += 45
    draw.text((150, y), "Tax ID: 61-5283047", fill='#333', font=font_norm); y += 90
    draw.text((150, y), "INVOICE", fill='#2c3e50', font=font_large); y += 90
    # Distractor: account number (NOT an invoice number)
    draw.text((150, y), "Customer Account: ACCT-88421", fill='#333', font=font_norm); y += 45
    # Distractor: service reference
    draw.text((150, y), "Service Reference: SVC-REF-2026-Q1", fill='#333', font=font_norm); y += 45
    # Real PO reference
    draw.text((150, y), "Purchase Order: PO-1003", fill='#333', font=font_norm); y += 45
    draw.text((150, y), "Date: March 14, 2026", fill='#333', font=font_norm); y += 45
    draw.text((150, y), "Currency: USD", fill='#333', font=font_norm); y += 70
    draw.text((150, y), "Bill To: Acme Corporation", fill='#333', font=font_bold); y += 60
    # Table
    draw.rectangle([(150, y), (2400, y+50)], fill='#2c3e50')
    draw.text((170, y+10), "Description", fill='white', font=font_bold)
    draw.text((1900, y+10), "Amount", fill='white', font=font_bold); y += 50
    draw.rectangle([(150, y), (2400, y+55)], outline='#ccc')
    draw.text((170, y+10), "Cloud infrastructure migration - Phase 1", fill='#333', font=font_norm)
    draw.text((1920, y+10), "$800.00", fill='#333', font=font_norm); y += 90
    draw.text((1600, y), "Subtotal:", fill='#333', font=font_bold)
    draw.text((1920, y), "$800.00", fill='#333', font=font_norm); y += 45
    draw.text((1600, y), "Tax (8%):", fill='#333', font=font_bold)
    draw.text((1920, y), "$64.00", fill='#333', font=font_norm); y += 45
    draw.line([(1600, y), (2400, y)], fill='#333', width=2); y += 8
    draw.text((1600, y), "Total Due:", fill='#333', font=font_bold)
    draw.text((1920, y), "$864.00", fill='#333', font=font_bold)

    # Scan artifacts
    img = img.rotate(0.4, fillcolor='#f9f9f2', expand=False)
    img = img.filter(ImageFilter.GaussianBlur(radius=0.8))
    random.seed(99)
    draw2 = ImageDraw.Draw(img)
    for _ in range(400):
        x, yn = random.randint(0, width-1), random.randint(0, height-1)
        g = random.randint(185, 225)
        draw2.point((x, yn), fill=(g, g, g))

    img_path = FIXTURE_DIR / "_temp_d.png"
    img.save(str(img_path), 'PNG', dpi=(300, 300))
    c = canvas.Canvas(str(path), pagesize=letter)
    c.drawImage(str(img_path), 0, 0, width=letter[0], height=letter[1])
    c.save()
    img_path.unlink(missing_ok=True)
    print(f"  D-missing: {path.name}")

def gen_scenario_d_corrected():
    """Corrected version WITH an invoice number added."""
    path = FIXTURE_DIR / "adv_ocr_distractors_corrected.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=letter, leftMargin=0.75*inch, rightMargin=0.75*inch,
                            topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph("PINNACLE CLOUD SERVICES", ParagraphStyle('H', parent=styles['Title'],
                 fontSize=18, textColor=colors.HexColor('#1a5276'))))
    story.append(Paragraph("1800 Tech Park Way, Seattle, WA 98101", styles['Normal']))
    story.append(Paragraph("Tax ID: 61-5283047", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph("INVOICE", ParagraphStyle('T', parent=styles['Heading1'], fontSize=24,
                 textColor=colors.HexColor('#2c3e50'))))
    story.append(Spacer(1, 0.15*inch))
    det = [["Invoice Number:", "PCS-ADV-2026-0099"],
           ["Customer Account:", "ACCT-88421"],
           ["Service Reference:", "SVC-REF-2026-Q1"],
           ["Purchase Order:", "PO-1003"],
           ["Date:", "March 14, 2026"], ["Currency:", "USD"]]
    t = Table(det, colWidths=[2*inch, 4*inch])
    t.setStyle(TableStyle([('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),10)]))
    story.append(t)
    story.append(Spacer(1, 0.2*inch))
    lt = Table([["Description","Amount"],["Cloud infrastructure migration - Phase 1","$800.00"]],
               colWidths=[5*inch, 1.5*inch])
    lt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#2c3e50')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),0.5,colors.grey),
        ('ALIGN',(1,0),(1,-1),'RIGHT'),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
    story.append(lt)
    story.append(Spacer(1, 0.15*inch))
    tt = Table([["Subtotal:","$800.00"],["Tax (8%):","$64.00"],["Total Due:","$864.00"]],
               colWidths=[5*inch, 1.5*inch])
    tt.setStyle(TableStyle([('FONTNAME',(0,-1),(-1,-1),'Helvetica-Bold'),
        ('ALIGN',(1,0),(1,-1),'RIGHT'),('LINEABOVE',(0,-1),(-1,-1),1.5,colors.black)]))
    story.append(tt)
    doc.build(story)
    print(f"  D-corrected: {path.name}")


if __name__ == "__main__":
    print("Generating advanced edge-case fixtures...")
    gen_scenario_a_invoice_a()
    gen_scenario_a_invoice_b()
    gen_scenario_b_original()
    gen_scenario_b_correction()
    gen_scenario_c()
    gen_scenario_d_missing()
    gen_scenario_d_corrected()
    print("Done.")

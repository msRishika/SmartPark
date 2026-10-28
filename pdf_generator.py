"""
pdf_generator.py
Generates professional, printable PDF parking receipts and tax invoices
for SmartPark using ReportLab.
"""

import io
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A5
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# Brand Palette: Midnight Navy (#061A33) and Teal (#00CBB0)
COLOR_NAVY_DARK = colors.HexColor("#061A33")
COLOR_NAVY_SURFACE = colors.HexColor("#0C2340")
COLOR_TEAL = colors.HexColor("#00CBB0")
COLOR_TEAL_DARK = colors.HexColor("#009688")
COLOR_TEXT_MAIN = colors.HexColor("#0F172A")
COLOR_TEXT_MUTED = colors.HexColor("#64748B")
COLOR_BORDER = colors.HexColor("#CBD5E1")
COLOR_PAID_BG = colors.HexColor("#ECFDF5")
COLOR_PAID_TEXT = colors.HexColor("#065F46")
COLOR_PAID_BORDER = colors.HexColor("#10B981")


def generate_receipt_pdf(bill_data: dict) -> io.BytesIO:
    """
    Builds a professional A5 receipt invoice PDF from bill details.
    
    Expected bill_data dictionary keys:
      - id / receipt_id: int or str (Receipt sequence or history ID)
      - vehicle_number: str (e.g. 'ABCD1234')
      - category: str (e.g. 'Four-Wheeler')
      - slot_number: str (e.g. 'S-07')
      - entry_time: str ('YYYY-MM-DD HH:MM:SS')
      - exit_time: str ('YYYY-MM-DD HH:MM:SS')
      - duration_minutes: int
      - duration_formatted: str (optional, e.g. '45 mins')
      - base_fee: float (optional)
      - hourly_rate: float (optional)
      - hours_billed: int (optional)
      - fee / total_fee: float
      - driver_contact: str (optional)
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A5,
        leftMargin=24,
        rightMargin=24,
        topMargin=24,
        bottomMargin=24
    )

    styles = getSampleStyleSheet()

    # Custom typography styles
    title_style = ParagraphStyle(
        "BrandTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=COLOR_NAVY_DARK,
        alignment=TA_LEFT
    )

    subtitle_style = ParagraphStyle(
        "BrandSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=COLOR_TEXT_MUTED,
        alignment=TA_LEFT
    )

    invoice_badge_style = ParagraphStyle(
        "InvoiceBadge",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=COLOR_PAID_TEXT,
        alignment=TA_RIGHT
    )

    plate_style = ParagraphStyle(
        "LicensePlate",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        textColor=COLOR_NAVY_DARK,
        alignment=TA_CENTER
    )

    label_style = ParagraphStyle(
        "RowLabel",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=COLOR_TEXT_MUTED
    )

    value_style = ParagraphStyle(
        "RowValue",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=13,
        textColor=COLOR_TEXT_MAIN,
        alignment=TA_RIGHT
    )

    total_label_style = ParagraphStyle(
        "TotalLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=COLOR_NAVY_DARK
    )

    total_value_style = ParagraphStyle(
        "TotalValue",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=COLOR_TEAL_DARK,
        alignment=TA_RIGHT
    )

    footer_style = ParagraphStyle(
        "FooterNote",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=COLOR_TEXT_MUTED,
        alignment=TA_CENTER
    )

    elements = []

    # 1. Header with Brand & Paid Stamp
    receipt_id = bill_data.get("id") or bill_data.get("receipt_id") or "1"
    receipt_num_str = f"INV-SP-{int(receipt_id):05d}" if str(receipt_id).isdigit() else f"INV-{receipt_id}"

    header_table = Table(
        [
            [
                Paragraph("<b>SmartPark</b>", title_style),
                Paragraph("<b>PAID &amp; COMPLETED</b>", invoice_badge_style)
            ],
            [
                Paragraph(f"Official Parking Fee Invoice &bull; {receipt_num_str}", subtitle_style),
                Paragraph(f"Date: {bill_data.get('exit_time', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}", ParagraphStyle("SubDate", parent=subtitle_style, alignment=TA_RIGHT))
            ]
        ],
        colWidths=[240, 150]
    )
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(header_table)

    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=COLOR_NAVY_DARK, spaceBefore=2, spaceAfter=12))

    # 2. License Plate Callout Box
    veh_num = bill_data.get("vehicle_number", "UNKNOWN")
    plate_table = Table(
        [
            [Paragraph(f"&nbsp;&nbsp;<b>[ IND ] &nbsp; {veh_num}</b>&nbsp;&nbsp;", plate_style)]
        ],
        colWidths=[390]
    )
    plate_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ('BORDER', (0, 0), (-1, -1), 1.5, COLOR_NAVY_DARK),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(plate_table)
    elements.append(Spacer(1, 14))

    # 3. Details Table
    category = bill_data.get("category", "Four-Wheeler")
    slot_num = bill_data.get("slot_number", "N/A")
    entry_time = bill_data.get("entry_time", "N/A")
    exit_time = bill_data.get("exit_time", "N/A")
    
    # Duration formatting
    duration_minutes = int(bill_data.get("duration_minutes", 1))
    hours_billed = bill_data.get("hours_billed")
    if not hours_billed:
        hours_billed = max(1, (duration_minutes + 59) // 60)

    hrs_part = duration_minutes // 60
    mins_part = duration_minutes % 60
    if hrs_part > 0 and mins_part > 0:
        duration_str = f"{hrs_part}h {mins_part}m ({duration_minutes} mins)"
    elif hrs_part > 0:
        duration_str = f"{hrs_part} hour{'s' if hrs_part > 1 else ''} ({duration_minutes} mins)"
    else:
        duration_str = f"{duration_minutes} minute{'s' if duration_minutes > 1 else ''}"

    # Rate info
    rates_map = {
        "Two-Wheeler": {"base_fee": 10.0, "hourly_rate": 15.0},
        "Four-Wheeler": {"base_fee": 20.0, "hourly_rate": 30.0},
        "EV Charging": {"base_fee": 25.0, "hourly_rate": 40.0},
        "Reserved": {"base_fee": 30.0, "hourly_rate": 50.0}
    }
    cat_rates = rates_map.get(category, {"base_fee": 20.0, "hourly_rate": 30.0})
    base_fee = bill_data.get("base_fee", cat_rates["base_fee"])
    hourly_rate = bill_data.get("hourly_rate", cat_rates["hourly_rate"])
    total_fee = bill_data.get("fee", bill_data.get("total_fee", 0.0))

    contact = bill_data.get("driver_contact", "")

    detail_rows = [
        [Paragraph("Assigned Slot", label_style), Paragraph(f"Slot {slot_num}", value_style)],
        [Paragraph("Vehicle Category", label_style), Paragraph(f"{category}", value_style)],
    ]
    if contact:
        detail_rows.append([Paragraph("Driver Contact", label_style), Paragraph(f"{contact}", value_style)])

    detail_rows.extend([
        [Paragraph("Entry Timestamp", label_style), Paragraph(f"{entry_time}", value_style)],
        [Paragraph("Exit Timestamp", label_style), Paragraph(f"{exit_time}", value_style)],
        [Paragraph("Parking Duration", label_style), Paragraph(f"{duration_str}", value_style)],
        [Paragraph("Applicable Tariff", label_style), Paragraph(f"Base Rs. {base_fee:.2f} + Rs. {hourly_rate:.2f}/hr", value_style)],
        [Paragraph("Billed Billable Hours", label_style), Paragraph(f"{hours_billed} hr(s) calculation", value_style)]
    ])

    details_table = Table(detail_rows, colWidths=[180, 210])
    details_table.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(details_table)

    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=COLOR_NAVY_DARK, spaceBefore=4, spaceAfter=8))

    # 4. Total Amount Paid Row
    total_table = Table(
        [
            [Paragraph("<b>TOTAL CHARGE PAID</b>", total_label_style), Paragraph(f"<b>Rs. {float(total_fee):,.2f}</b>", total_value_style)]
        ],
        colWidths=[200, 190]
    )
    total_table.setStyle(TableStyle([
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(total_table)

    elements.append(Spacer(1, 14))

    # 5. Footer Information
    footer_text = (
        "Thank you for using SmartPark Automated Parking Facility.<br/>"
        "Retain this receipt for your records. Standard GST & municipal parking tariff applied.<br/>"
        "System Generated Digital Tax Invoice &bull; No physical signature required."
    )
    elements.append(Paragraph(footer_text, footer_style))

    doc.build(elements)
    buffer.seek(0)
    return buffer

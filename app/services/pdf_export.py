# PDF export utility for generating standardized radiology report documents using ReportLab.
import io
from datetime import datetime
from pathlib import Path
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models import Report


def generate_report_pdf(report: Report, approver_username: str) -> bytes:
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    # Custom typography styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#1e3a8a"),
    )

    h2_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=4,
    )

    body_style = ParagraphStyle(
        "BodyTextCustom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#334155"),
    )

    meta_label = ParagraphStyle(
        "MetaLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#475569"),
    )

    meta_value = ParagraphStyle(
        "MetaValue",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#0f172a"),
    )

    banner_style = ParagraphStyle(
        "BannerText",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#854d0e"),
        alignment=1,  # Centered
    )

    footer_style = ParagraphStyle(
        "FooterText",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#64748b"),
        alignment=1,  # Centered
    )

    story = []

    # 1. Mandatory Safety Banner Box
    safety_disclaimer = (
        "AI-generated DRAFT. Must be reviewed and approved by a qualified radiologist. Not a final diagnosis."
    )
    banner_table = Table(
        [[Paragraph(safety_disclaimer, banner_style)]],
        colWidths=[532],
    )
    banner_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fef9c3")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#fde047")),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ])
    )
    story.append(banner_table)
    story.append(Spacer(1, 16))

    # 2. Document Title & Header
    story.append(Paragraph("Chest X-Ray Report", title_style))
    story.append(Spacer(1, 10))

    # 3. Metadata Table
    created_date = (
        report.created_at.strftime("%Y-%m-%d %H:%M UTC")
        if report.created_at
        else datetime.utcnow().strftime("%Y-%m-%d")
    )
    approved_date = (
        report.approved_at.strftime("%Y-%m-%d %H:%M UTC")
        if report.approved_at
        else created_date
    )

    meta_data = [
        [
            Paragraph("Report ID:", meta_label),
            Paragraph(f"#{report.id}", meta_value),
            Paragraph("Date Created:", meta_label),
            Paragraph(created_date, meta_value),
        ],
        [
            Paragraph("Original File:", meta_label),
            Paragraph(report.original_filename, meta_value),
            Paragraph("Approved By:", meta_label),
            Paragraph(f"{approver_username} on {approved_date}", meta_value),
        ],
    ]

    meta_table = Table(meta_data, colWidths=[90, 176, 90, 176])
    meta_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    story.append(meta_table)
    story.append(Spacer(1, 14))

    # 4. Image Preview & Overview Layout
    image_element = None
    if report.image_path and Path(report.image_path).exists():
        try:
            # Display image in clean square proportions (2.0 x 2.0 inches)
            image_element = RLImage(report.image_path, width=2.0 * inch, height=2.0 * inch)
        except Exception:
            image_element = None

    if image_element:
        # Side-by-side with basic radiographic info
        summary_text = [
            Paragraph("Clinical Findings & Impression", h2_style),
            Paragraph("The radiographic findings below have been reviewed, edited, and approved by the reporting radiologist.", body_style),
            Spacer(1, 8),
            Paragraph(f"<b>Engine:</b> {report.engine_name}", meta_value),
        ]
        layout_table = Table([[image_element, summary_text]], colWidths=[2.2 * inch, 5.2 * inch - 2.2 * inch])
        layout_table.setStyle(
            TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ])
        )
        story.append(layout_table)
        story.append(Spacer(1, 14))

    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceAfter=14))

    # 5. Findings Section
    story.append(Paragraph("Findings", h2_style))
    story.append(Paragraph(report.final_findings or report.ai_findings or "No findings recorded.", body_style))
    story.append(Spacer(1, 14))

    # 6. Impression Section
    story.append(Paragraph("Impression", h2_style))
    story.append(Paragraph(report.final_impression or report.ai_impression or "No impression recorded.", body_style))
    story.append(Spacer(1, 24))

    # 7. Bottom Footnote
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0"), spaceAfter=8))
    story.append(Paragraph("AI-assisted draft. Reviewed and approved by a qualified radiologist.", footer_style))

    # Background canvas callback: Watermark if is_mock is true
    def draw_page_decorations(canvas_obj: canvas.Canvas, doc_obj):
        if report.is_mock:
            canvas_obj.saveState()
            canvas_obj.setFont("Helvetica-Bold", 60)
            canvas_obj.setFillColor(colors.HexColor("#ef4444"), alpha=0.15)
            canvas_obj.translate(300, 380)
            canvas_obj.rotate(45)
            canvas_obj.drawCentredString(0, 0, "MOCK SAMPLE")
            canvas_obj.restoreState()

    doc.build(story, onFirstPage=draw_page_decorations, onLaterPages=draw_page_decorations)

    return buffer.getvalue()

#!/usr/bin/env python3
"""
Generate a PDF CV/Portfolio
"""

import json

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

MONO_FONT = "Courier"
MONO_BOLD = "Courier-Bold"


def load_cv_data(json_file="info.json"):
    """Load CV data from JSON file"""
    with open(json_file, "r", encoding="utf-8") as f:
        return json.load(f)


def create_terminal_cv(json_file="info.json"):
    """Create a terminal-themed PDF CV"""

    cv_data = load_cv_data(json_file)

    filename = "horduntech.pdf"
    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    # Container for the 'Flowable' objects
    elements = []
    styles = getSampleStyleSheet()

    title_style = styles["Heading1"]
    title_style.fontName = MONO_BOLD
    title_style.fontSize = 20
    title_style.textColor = HexColor("#000000")  # Black
    title_style.leading = 24
    title_style.spaceAfter = 8

    heading_style = styles["Heading2"]
    heading_style.fontName = MONO_BOLD
    heading_style.fontSize = 13
    heading_style.textColor = HexColor("#000000")  # Black
    heading_style.leading = 16
    heading_style.spaceAfter = 6
    heading_style.spaceBefore = 14

    body_style = styles["Normal"]
    body_style.fontName = MONO_FONT
    body_style.fontSize = 11
    body_style.textColor = HexColor("#000000")  # Black
    body_style.leading = 15
    body_style.spaceAfter = 6

    summary = cv_data["summary"]
    header_text = f"<b>{summary['name']}</b><br/>{summary['role']}"
    elements.append(Paragraph(header_text, title_style))

    contact_info = (
        f"{summary['email']} | {summary['location']} | {summary['website']}"
    )
    elements.append(Paragraph(contact_info, body_style))
    elements.append(Spacer(1, 8))

    # Professional Summary
    elements.append(Paragraph("SUMMARY", heading_style))
    summary_text = summary.get(
        "bio",
        f"{summary['role']} with expertise in software development and system architecture.",
    )
    elements.append(Paragraph(summary_text, body_style))
    elements.append(Spacer(1, 8))

    elements.append(Paragraph("TECHNICAL SKILLS", heading_style))
    skills = cv_data["skills"]

    skills_content = []
    skills_content.append(
        f"<b>Languages:</b> {', '.join(skills['programming_languages'])}"
    )
    skills_content.append(
        f"<b>Frameworks:</b> {', '.join(skills['frameworks_libraries'])}"
    )
    skills_content.append(
        f"<b>Tools:</b> {', '.join(skills['tools_technologies'])}"
    )

    for skill_line in skills_content:
        elements.append(Paragraph(skill_line, body_style))
    elements.append(Spacer(1, 8))

    elements.append(Paragraph("PROFESSIONAL EXPERIENCE", heading_style))

    work_exp = cv_data["work_experience"]
    for exp in work_exp:
        exp_header = (
            f"<b>{exp['title']}</b> | {exp['company']} | {exp['period']}"
        )
        elements.append(Paragraph(exp_header, body_style))
        for resp in exp["responsibilities"]:
            elements.append(Paragraph(f"  • {resp}", body_style))
        elements.append(Spacer(1, 6))

    elements.append(Paragraph("PROJECTS", heading_style))
    projects = cv_data["projects"]
    for project in projects:
        proj_header = f"<b>{project['name']}</b> | {project['tech']}"
        elements.append(Paragraph(proj_header, body_style))
        elements.append(Paragraph(f"  {project['description']}", body_style))
        elements.append(Paragraph(f"  Link: {project['link']}", body_style))
        elements.append(Spacer(1, 6))

    elements.append(Paragraph("EDUCATION", heading_style))
    education = cv_data["education"]
    for edu in education:
        edu_header = (
            f"<b>{edu['degree']}</b> | {edu['institution']} | {edu['period']}"
        )
        elements.append(Paragraph(edu_header, body_style))
        for detail in edu["details"]:
            elements.append(Paragraph(f"  • {detail}", body_style))
        elements.append(Spacer(1, 6))

    elements.append(Paragraph("CONTACT", heading_style))
    contact = cv_data["contact"]
    contact_lines = [
        f"Email: {contact['email']}",
        f"GitHub: {contact['github']}",
        f"LinkedIn: {contact['linkedin']}",
        f"Website: {contact['website']}",
        f"Phone: {contact['phone']}",
    ]
    for line in contact_lines:
        elements.append(Paragraph(line, body_style))

    def on_every_page(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(HexColor("#FFFFFF"))
        canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
        canvas.restoreState()

    doc.build(elements, onFirstPage=on_every_page, onLaterPages=on_every_page)
    print(f"PDF created successfully: {filename}")


if __name__ == "__main__":
    import sys

    json_file = sys.argv[1] if len(sys.argv) > 1 else "info.json"
    create_terminal_cv(json_file)

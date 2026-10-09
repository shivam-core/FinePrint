# app/reporting.py
import io
import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.units import mm
from reportlab.lib import colors
import html

def generate_report(analysis, filename="report.pdf"):
    buffer = io.BytesIO()
    
    def add_page_number(canvas, doc):
        page_num = canvas.getPageNumber()
        text = f"FinePrint Analysis Report | Model {analysis.model_version} | Page {page_num}"
        canvas.saveState()
        canvas.setFont('Helvetica', 9)
        canvas.setFillColor(colors.gray)
        canvas.drawString(18*mm, 10*mm, text)
        canvas.restoreState()

    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=18*mm, leftMargin=18*mm,
                            topMargin=18*mm, bottomMargin=18*mm)
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        spaceAfter=12
    )
    
    heading2 = ParagraphStyle(
        'Heading2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        spaceAfter=10,
        spaceBefore=15
    )
    
    normal = styles['Normal']
    normal.fontName = 'Helvetica'
    normal.fontSize = 10
    normal.leading = 14
    
    clause_box = ParagraphStyle(
        'ClauseBox',
        parent=normal,
        backColor=colors.HexColor("#f8f9fa"),
        borderColor=colors.HexColor("#dee2e6"),
        borderWidth=1,
        borderPadding=10,
        spaceBefore=10,
        spaceAfter=10
    )
    
    meta_style = ParagraphStyle(
        'MetaStyle',
        parent=normal,
        textColor=colors.gray,
        fontSize=9
    )
    
    story = []
    
    # Title
    story.append(Paragraph("FinePrint — Terms-of-Service Analysis", title_style))
    
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    story.append(Paragraph(f"<b>Generated:</b> {timestamp}", normal))
    story.append(Paragraph(f"<b>Source:</b> {html.escape(analysis.source_name)}", normal))
    story.append(Paragraph(f"<b>Model Version:</b> {html.escape(analysis.model_version)}", normal))
    story.append(Spacer(1, 10))
    
    # Limitation
    story.append(Paragraph("<i>Educational screening tool. Unflagged text is not a guarantee of fairness. Not legal advice.</i>", meta_style))
    story.append(Spacer(1, 20))
    
    # Summary
    story.append(Paragraph("Summary", heading2))
    summary = analysis.summary
    story.append(Paragraph(f"<b>Total Clauses:</b> {summary.total}", normal))
    story.append(Paragraph(f"<b>Potentially Unfair:</b> {summary.potentially_unfair}", normal))
    story.append(Paragraph(f"<b>No Issue Detected:</b> {summary.no_issue_detected}", normal))
    story.append(Paragraph(f"<b>Needs Review:</b> {summary.needs_review}", normal))
    story.append(Spacer(1, 10))
    
    if analysis.warnings:
        story.append(Paragraph("Warnings", heading2))
        for w in analysis.warnings:
            story.append(Paragraph(f"• {html.escape(w)}", normal))
        story.append(Spacer(1, 10))
        
    # Findings
    story.append(Paragraph("Executive Findings (Potentially Unfair)", heading2))
    flagged = [s for s in analysis.segments if s.status == "potentially_unfair"]
    
    if not flagged:
        story.append(Paragraph("No potentially unfair clauses detected.", normal))
    else:
        for i, s in enumerate(flagged[:10]):
            story.append(Paragraph(f"<b>Clause ID:</b> {html.escape(s.id)}", normal))
            cats = ", ".join([html.escape(c.name) for c in s.categories])
            story.append(Paragraph(f"<b>Categories:</b> {cats}", normal))
            story.append(Paragraph(html.escape(s.text), clause_box))
            
            # Context
            first_cat = s.categories[0]
            ctx = s.explanations[str(first_cat.id)].context
            story.append(Paragraph(f"<b>Context:</b> {html.escape(ctx)}", normal))
            story.append(Spacer(1, 15))
            
        if len(flagged) > 10:
            story.append(Paragraph(f"<i>... and {len(flagged) - 10} more findings. See appendix for complete details.</i>", meta_style))

    # Unflagged overview
    story.append(PageBreak())
    story.append(Paragraph("Unflagged Overview", heading2))
    unflagged = [s for s in analysis.segments if s.status == "no_issue_detected"]
    
    if unflagged:
        story.append(Paragraph("Representative 'No Issue Detected' clauses:", normal))
        for s in unflagged[:3]:
            story.append(Paragraph(html.escape(s.text), clause_box))
    else:
        story.append(Paragraph("None.", normal))
        
    # Appendix: Complete source
    story.append(PageBreak())
    story.append(Paragraph("Appendix: Complete Analysed Input", heading2))
    story.append(Paragraph("This section contains the entire input document in order, with clause IDs.", meta_style))
    story.append(Spacer(1, 10))
    
    for s in analysis.segments:
        prefix = f"<b>[{s.id}]</b> "
        if s.status == "potentially_unfair":
            prefix += "<font color='red'>[FLAGGED]</font> "
        elif s.status == "needs_review":
            prefix += "<font color='orange'>[REVIEW]</font> "
            
        story.append(Paragraph(prefix + html.escape(s.text), normal))
        story.append(Spacer(1, 5))
        
    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    return buffer.getvalue()

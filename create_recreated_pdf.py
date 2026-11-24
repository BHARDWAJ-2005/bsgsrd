import os
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_footer(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_footer(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        # Left footer: BSG District · School (UDISE)
        self.drawString(36, 26, "BSG Nizamabad · ZPHS ALOOR (36050301331)")
        # Right footer: Page X
        self.drawRightString(595.27 - 36, 26, f"Page {self._pageNumber}")
        self.restoreState()

def build_pdf(filename):
    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=26,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        alignment=1,
        textColor=colors.HexColor('#1A365D')
    )
    sub_style = ParagraphStyle(
        'DocSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
        alignment=1,
        textColor=colors.HexColor('#4A5568')
    )
    banner_style = ParagraphStyle(
        'BannerText',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=12,
        alignment=1,
        textColor=colors.white
    )
    sec_heading_blue = ParagraphStyle(
        'SecHeadingBlue',
        parent=styles['Normal'],
        fontName='Helvetica-BoldOblique',
        fontSize=10.5,
        leading=13,
        textColor=colors.HexColor('#1A365D'),
        spaceBefore=7,
        spaceAfter=3
    )
    sec_heading_boys = ParagraphStyle(
        'SecHeadingBoys',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=13,
        textColor=colors.HexColor('#1A365D'),
        spaceBefore=7,
        spaceAfter=3
    )
    sec_heading_girls = ParagraphStyle(
        'SecHeadingGirls',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=13,
        textColor=colors.HexColor('#6B21A8'),
        spaceBefore=7,
        spaceAfter=3
    )
    cell_meta_label = ParagraphStyle(
        'MetaLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor('#1E293B')
    )
    cell_meta_val = ParagraphStyle(
        'MetaVal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor('#0F172A')
    )
    cell_meta_val_bold = ParagraphStyle(
        'MetaValBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor('#0F172A')
    )
    th_style = ParagraphStyle(
        'TH',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=6.5,
        leading=7.5,
        alignment=1,
        textColor=colors.white
    )
    td_style_center = ParagraphStyle(
        'TDC',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=6.5,
        leading=7.5,
        alignment=1,
        textColor=colors.HexColor('#0F172A')
    )
    td_style_left = ParagraphStyle(
        'TDL',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=6.5,
        leading=7.5,
        alignment=0,
        textColor=colors.HexColor('#0F172A')
    )
    td_style_left_bold = ParagraphStyle(
        'TDLB',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=6.5,
        leading=7.5,
        alignment=0,
        textColor=colors.HexColor('#0F172A')
    )
    note_style = ParagraphStyle(
        'Note',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=6.5,
        leading=8.5,
        textColor=colors.HexColor('#64748B')
    )

    story = []

    # 1. Header
    story.append(Paragraph("THE BHARAT SCOUTS AND GUIDES", title_style))
    story.append(Spacer(1, 2))
    story.append(Paragraph("Nizamabad District Association · Telangana State", sub_style))
    story.append(Spacer(1, 7))

    # 2. Blue Banner with Gold Accent Stripe
    banner_data = [
        [Paragraph("UNIT ENROLLMENT & UNIFORM MEASUREMENT REPORT", banner_style)],
        [""]
    ]
    banner_table = Table(banner_data, colWidths=[523.27], rowHeights=[20, 2.5])
    banner_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#18335C')),
        ('BACKGROUND', (0, 1), (0, 1), colors.HexColor('#EAB308')), # Golden accent line
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (0, 0), 4),
        ('BOTTOMPADDING', (0, 0), (0, 0), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(banner_table)
    story.append(Spacer(1, 5))

    # 3. School Details Table
    school_info = [
        [
            Paragraph("School", cell_meta_label),
            Paragraph("ZPHS ALOOR", cell_meta_val_bold),
            Paragraph("UDISE code", cell_meta_label),
            Paragraph("36050301331", cell_meta_val),
            Paragraph("Mandal", cell_meta_label),
            Paragraph("ALOOR", cell_meta_val)
        ],
        [
            Paragraph("School type", cell_meta_label),
            Paragraph("Co-education High School", cell_meta_val),
            Paragraph("Classes", cell_meta_label),
            Paragraph("6, 7, 8, 9", cell_meta_val),
            Paragraph("Generated on", cell_meta_label),
            Paragraph("24-11-2026 07:20 PM", cell_meta_val)
        ]
    ]
    meta_table = Table(school_info, colWidths=[65, 125, 65, 95, 65, 108.27])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F8FAFC')),
        ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#F8FAFC')),
        ('BACKGROUND', (4, 0), (4, -1), colors.HexColor('#F8FAFC')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(meta_table)

    # 4. Summary Table
    story.append(Paragraph("Summary", sec_heading_blue))
    sum_data = [
        [
            Paragraph("Unit", ParagraphStyle('THL', parent=th_style, alignment=0)),
            Paragraph("Quota", th_style),
            Paragraph("Enrolled", th_style),
            Paragraph("Short details", th_style),
            Paragraph("Brief details", th_style),
            Paragraph("Vacant", th_style)
        ],
        [Paragraph("Scouts (Boys)", td_style_left), Paragraph("16", td_style_center), Paragraph("16", td_style_center), Paragraph("0", td_style_center), Paragraph("16", td_style_center), Paragraph("0", td_style_center)],
        [Paragraph("Guides (Girls)", td_style_left), Paragraph("16", td_style_center), Paragraph("16", td_style_center), Paragraph("0", td_style_center), Paragraph("16", td_style_center), Paragraph("0", td_style_center)],
        [Paragraph("Unit leaders", td_style_left), Paragraph("2", td_style_center), Paragraph("1", td_style_center), Paragraph("", td_style_center), Paragraph("", td_style_center), Paragraph("1", td_style_center)],
    ]
    sum_table = Table(sum_data, colWidths=[110, 80, 80, 85, 85, 83.27])
    sum_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#18335C')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(sum_table)

    # 5. Unit Leaders Table
    story.append(Paragraph("Unit leaders", sec_heading_blue))
    leader_data = [
        [
            Paragraph("Role", ParagraphStyle('THL', parent=th_style, alignment=0)),
            Paragraph("Unit", ParagraphStyle('THL', parent=th_style, alignment=0)),
            Paragraph("Teacher name", ParagraphStyle('THL', parent=th_style, alignment=0)),
            Paragraph("Designation", ParagraphStyle('THL', parent=th_style, alignment=0)),
            Paragraph("Mobile", ParagraphStyle('THL', parent=th_style, alignment=0)),
            Paragraph("Size", th_style),
            Paragraph("Measurements", ParagraphStyle('THL', parent=th_style, alignment=0))
        ],
        [
            Paragraph("Scout Master", td_style_left),
            Paragraph("Scouts", td_style_left),
            Paragraph("GATADI RAJESH", td_style_left_bold),
            Paragraph("PHYSICAL DIRECTOR", td_style_left),
            Paragraph("9440441757", td_style_left),
            Paragraph("44", td_style_center),
            Paragraph("Ht 174cm, Chest 44, Waist 36, Neck 17, Sh 23, Sleeve 26, Shirt 31, Pant 41, Shoe 8", td_style_left)
        ],
        [
            Paragraph("Guide Captain", td_style_left),
            Paragraph("Guides", td_style_left),
            Paragraph("<i>Not appointed</i>", ParagraphStyle('TDI', parent=td_style_left, fontName='Helvetica-Oblique', textColor=colors.HexColor('#64748B'))),
            Paragraph("", td_style_left),
            Paragraph("", td_style_left),
            Paragraph("", td_style_center),
            Paragraph("", td_style_left)
        ]
    ]
    leader_table = Table(leader_data, colWidths=[65, 45, 95, 95, 58, 25, 140.27])
    leader_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#18335C')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(leader_table)

    # 6. Boys – Scouts (Page 1: rows 1 to 10)
    story.append(Paragraph("Boys – Scouts (16 of 16)", sec_heading_boys))

    # Adjusted widths so Class, Shoulder, Pant len, Details NEVER wrap
    boys_col_widths = [16, 86, 79, 24, 19, 39, 24, 24, 23, 35, 25, 36, 46, 21, 26.27]

    def make_boys_header():
        return [
            Paragraph("#", th_style),
            Paragraph("Name", ParagraphStyle('THL', parent=th_style, alignment=0)),
            Paragraph("Father / Guardian", ParagraphStyle('THL', parent=th_style, alignment=0)),
            Paragraph("Class", th_style),
            Paragraph("Size", th_style),
            Paragraph("Height (cm)", th_style),
            Paragraph("Chest", th_style),
            Paragraph("Waist", th_style),
            Paragraph("Neck", th_style),
            Paragraph("Shoulder", th_style),
            Paragraph("Sleeve", th_style),
            Paragraph("Shirt len.", th_style),
            Paragraph("Pant len.", th_style),
            Paragraph("Shoe", th_style),
            Paragraph("Details", th_style)
        ]

    boys_rows_raw = [
        (1, "G.HARISH", "MALLAIAH", 6, 32, 134, 27, 28, 13, 15, 8, 24, 34, 6, "Brief"),
        (2, "G.MOKSHITH", "SUMAN", 6, 30, 132, 24, 26, 13, 15, 13, 24, 32, 5, "Brief"),
        (3, "H.SIMHADRI", "PRASAD", 6, 30, 138, 23, 25, 13, 16, 8, 25, 34, 5, "Brief"),
        (4, "K.CHARAN TEJ", "SRINIVAS", 6, 32, 144, 24, 28, 13, 16, 8, 25, 36, 6, "Brief"),
        (5, "M.NIKHIL", "RAMSINGH", 6, 34, 139, 27, 28, 12, 15, 8, 25, 32, 7, "Brief"),
        (6, "M.SAHARSH", "MARUTHI", 6, 32, 142, 24, 26, 13, 16, 22, 24, 35, 7, "Brief"),
        (7, "B.SAI KUMAR", "BHOOMANNA", 8, 38, 160, 30, 28, 16, 17, 9, 28, 39, 8, "Brief"),
        (8, "D.AKSHAY KUMAR", "RAMANUJAN", 8, 38, 154, 28, 28, 16, 18, 9, 28, 39, 8, "Brief"),
        (9, "K.PRANEETH", "SRINU", 8, 34, 147, 29, 28, 15, 17, 9, 26, 37, 7, "Brief"),
        (10, "R.HARSHITH", "SANTHOSH", 8, 32, 140, 26, 26, 14, 16, 8, 26, 37, 4, "Brief"),
        (11, "K.SRINITH", "SRINIVAS", 9, 36, 160, 31, 30, 16, 17, 9, 26, 37, 8, "Brief"),
        (12, "M.ADITHYA GOUD", "RAVI GOUD", 9, 36, 152, 26, 26, 15, 16, 8.5, 24, 38, 6, "Brief"),
        (13, "M.SRITEJ", "NAGESH", 9, 34, 152, 29, 26, 15, 16, 9, 26, 37, 8, "Brief"),
        (14, "N.KARTHIK", "KRISHNA", 9, 36, 159, 33, 32, 15, 18, 9, 27, 38, 9, "Brief"),
        (15, "N.SRI HANEESH", "RAVI KUMAR", 9, 36, 155, 29, 29, 15, 16, 9, 26, 38, 8, "Brief"),
        (16, "Y.VISHNU VARDHAN", "CHINNA MALLAIAH", 9, 36, 145, 25, 26, 15, 17, 8, 24, 37, 7, "Brief"),
    ]

    boys_p1_data = [make_boys_header()]
    for r in boys_rows_raw[:10]:
        boys_p1_data.append([
            Paragraph(str(r[0]), td_style_center),
            Paragraph(str(r[1]), td_style_left_bold),
            Paragraph(str(r[2]), td_style_left),
            Paragraph(str(r[3]), td_style_center),
            Paragraph(str(r[4]), td_style_center),
            Paragraph(str(r[5]), td_style_center),
            Paragraph(str(r[6]), td_style_center),
            Paragraph(str(r[7]), td_style_center),
            Paragraph(str(r[8]), td_style_center),
            Paragraph(str(r[9]), td_style_center),
            Paragraph(str(r[10]), td_style_center),
            Paragraph(str(r[11]), td_style_center),
            Paragraph(str(r[12]), td_style_center),
            Paragraph(str(r[13]), td_style_center),
            Paragraph(str(r[14]), td_style_center),
        ])

    table_style_boys = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')), # Royal blue header
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
    ]

    boys_p1_table = Table(boys_p1_data, colWidths=boys_col_widths)
    boys_p1_table.setStyle(TableStyle(table_style_boys))
    story.append(boys_p1_table)

    # EXACT PAGE BREAK MATCHING ORIGINAL DOCUMENT
    story.append(PageBreak())

    # 7. Boys continuation (rows 11 to 16) on Page 2
    boys_p2_data = [make_boys_header()]
    for r in boys_rows_raw[10:]:
        boys_p2_data.append([
            Paragraph(str(r[0]), td_style_center),
            Paragraph(str(r[1]), td_style_left_bold),
            Paragraph(str(r[2]), td_style_left),
            Paragraph(str(r[3]), td_style_center),
            Paragraph(str(r[4]), td_style_center),
            Paragraph(str(r[5]), td_style_center),
            Paragraph(str(r[6]), td_style_center),
            Paragraph(str(r[7]), td_style_center),
            Paragraph(str(r[8]), td_style_center),
            Paragraph(str(r[9]), td_style_center),
            Paragraph(str(r[10]), td_style_center),
            Paragraph(str(r[11]), td_style_center),
            Paragraph(str(r[12]), td_style_center),
            Paragraph(str(r[13]), td_style_center),
            Paragraph(str(r[14]), td_style_center),
        ])
    boys_p2_table = Table(boys_p2_data, colWidths=boys_col_widths)
    boys_p2_table.setStyle(TableStyle(table_style_boys))
    story.append(boys_p2_table)
    story.append(Spacer(1, 2))
    story.append(Paragraph("Height in cm; all other measurements in inches.", note_style))
    story.append(Spacer(1, 6))

    # 8. Girls – Guides (16 of 16)
    story.append(Paragraph("Girls – Guides (16 of 16)", sec_heading_girls))

    girls_col_widths = [16, 86, 79, 24, 19, 39, 24, 24, 23, 35, 25, 36, 46, 21, 26.27]

    def make_girls_header():
        return [
            Paragraph("#", th_style),
            Paragraph("Name", ParagraphStyle('THL', parent=th_style, alignment=0)),
            Paragraph("Father / Guardian", ParagraphStyle('THL', parent=th_style, alignment=0)),
            Paragraph("Class", th_style),
            Paragraph("Size", th_style),
            Paragraph("Height (cm)", th_style),
            Paragraph("Bust", th_style),
            Paragraph("Waist", th_style),
            Paragraph("Hip", th_style),
            Paragraph("Shoulder", th_style),
            Paragraph("Sleeve", th_style),
            Paragraph("Kameez", th_style),
            Paragraph("Salwar/Skirt", th_style),
            Paragraph("Shoe", th_style),
            Paragraph("Details", th_style)
        ]

    girls_rows_raw = [
        (1, "A. THANUSRI", "SAILU", 6, 34, 151, 29, 27, 34, 13, 10, 30, 33, 7, "Brief"),
        (2, "G. BHANU", "SURYA BOI", 6, 30, 138.3, 24, 23, 28, 13, 8, 28, 30, 5, "Brief"),
        (3, "M. RUTHWIKA", "RAVI", 6, 28, 144.4, 24, 23, 28, 12, 8, 28, 29, 5, "Brief"),
        (4, "S. NITHYA", "NAGARAJU", 6, 28, 136.9, 25, 23, 28, 12, 8, 26, 28, 5, "Brief"),
        (5, "B. SRINIKA", "SRIKANTH", 7, 32, 149, 27, 25, 32, 14, 8, 30, 31, 6, "Brief"),
        (6, "N. SANVIKA", "PRABHAKAR", 7, 32, 147.8, 29, 30, 34, 14, 8, 30, 31, 6, "Brief"),
        (7, "P. SATHWIKA", "CHAKRAPANI", 7, 34, 156.5, 28, 26, 32, 13, 10, 32, 34, 7, "Brief"),
        (8, "S. NEEHA", "MURALI MOHAN", 7, 32, 148.6, 24, 23, 29, 12, 9, 30, 33, 6, "Brief"),
        (9, "D. RISHIKA", "GANGADHAR", 8, 30, 146.1, 27, 24, 30, 13.5, 9, 28, 32, 6, "Brief"),
        (10, "M. SHRAVYA", "THIRUPATHI", 8, 32, 150.9, 26, 24, 28, 13, 9, 27, 34, 6, "Brief"),
        (11, "P. NIHARSHINI", "RAJINI KUMAR", 8, 30, 142, 26, 24, 28, 12, 9, 29, 30, 6, "Brief"),
        (12, "V. SATHWIKA", "SHANKAR", 8, 32, 152.3, 26, 23, 28, 13, 9, 30, 33, 6, "Brief"),
        (13, "B. VIDHYA", "NARAYANA", 9, 30, 149.5, 26, 25, 29, 13, 9, 28, 33, 7, "Brief"),
        (14, "G. HARICHANDANA", "SUMAN", 9, 30, 149.5, 26, 25, 29, 13, 9, 28, 33, 7, "Brief"),
        (15, "K. SRIHITHA", "NARA GOUD", 9, 34, 162.5, 32, 30, 36, 15, 11, 33, 38, 8, "Brief"),
        (16, "L. AISHWARYA", "ABBULU", 9, 32, 153.2, 29, 28.5, 30, 14.5, 9.5, 32, 35, 7, "Brief"),
    ]

    girls_p2_data = [make_girls_header()]
    for r in girls_rows_raw:
        girls_p2_data.append([
            Paragraph(str(r[0]), td_style_center),
            Paragraph(str(r[1]), td_style_left_bold),
            Paragraph(str(r[2]), td_style_left),
            Paragraph(str(r[3]), td_style_center),
            Paragraph(str(r[4]), td_style_center),
            Paragraph(str(r[5]), td_style_center),
            Paragraph(str(r[6]), td_style_center),
            Paragraph(str(r[7]), td_style_center),
            Paragraph(str(r[8]), td_style_center),
            Paragraph(str(r[9]), td_style_center),
            Paragraph(str(r[10]), td_style_center),
            Paragraph(str(r[11]), td_style_center),
            Paragraph(str(r[12]), td_style_center),
            Paragraph(str(r[13]), td_style_center),
            Paragraph(str(r[14]), td_style_center),
        ])

    table_style_girls = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7C3AED')), # Purple header
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
    ]

    girls_p2_table = Table(girls_p2_data, colWidths=girls_col_widths)
    girls_p2_table.setStyle(TableStyle(table_style_girls))
    story.append(girls_p2_table)
    story.append(Spacer(1, 2))
    story.append(Paragraph("Height in cm; all other measurements in inches.", note_style))
    story.append(Spacer(1, 32))

    # 9. Clean Signature Lines
    sig_label_style = ParagraphStyle(
        'SigLabel',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        alignment=1,
        textColor=colors.HexColor('#1E293B')
    )
    sig_data = [
        [
            Paragraph("Signature of Scout Master / Cub Master", sig_label_style),
            "",
            Paragraph("Signature of Guide Captain / Flock Leader", sig_label_style),
            "",
            Paragraph("Signature of Headmaster with seal", sig_label_style)
        ]
    ]
    sig_table = Table(sig_data, colWidths=[155, 29.13, 155, 29.14, 155])
    sig_table.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (0, 0), 0.75, colors.HexColor('#475569')),
        ('LINEABOVE', (2, 0), (2, 0), 0.75, colors.HexColor('#475569')),
        ('LINEABOVE', (4, 0), (4, 0), 0.75, colors.HexColor('#475569')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(sig_table)

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated: {filename}")

if __name__ == '__main__':
    build_pdf("BSG_Report_ZPHS_ALOOR.pdf")

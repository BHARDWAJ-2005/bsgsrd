import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas
from .models import School, Student, UnitLeader, StudentDetailLevel

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
        district_name = getattr(self, 'district_name', 'Sangareddy')
        school_name = getattr(self, 'school_name', '')
        udise_code = getattr(self, 'udise_code', '')
        self.drawString(36, 26, f"BSG {district_name} · {school_name} ({udise_code})")
        self.drawRightString(595.27 - 36, 26, f"Page {self._pageNumber}")
        self.restoreState()

def generate_school_pdf_report(school: School) -> io.BytesIO:
    """
    Generates an exact 2-page Bharat Scouts and Guides Unit Enrollment & Uniform Measurement Report
    matching the official district layout and typography.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=26,
        bottomMargin=36
    )

    district_name = school.mandal.district.name if (school.mandal and school.mandal.district) else "Sangareddy"

    class CustomDocCanvas(NumberedCanvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.district_name = district_name
            self.school_name = school.name
            self.udise_code = school.udise_code

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
        fontSize=10,
        leading=12,
        textColor=colors.HexColor('#1A365D'),
        spaceBefore=5,
        spaceAfter=2
    )
    sec_heading_boys = ParagraphStyle(
        'SecHeadingBoys',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=12,
        textColor=colors.HexColor('#1A365D'),
        spaceBefore=5,
        spaceAfter=2
    )
    sec_heading_girls = ParagraphStyle(
        'SecHeadingGirls',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=12,
        textColor=colors.HexColor('#6B21A8'),
        spaceBefore=5,
        spaceAfter=2
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
    story.append(Paragraph(f"{district_name} District Association · Telangana State", sub_style))
    story.append(Spacer(1, 6))

    # 2. Banner
    banner_data = [
        [Paragraph("UNIT ENROLLMENT & UNIFORM MEASUREMENT REPORT", banner_style)],
        [""]
    ]
    banner_table = Table(banner_data, colWidths=[523.27], rowHeights=[20, 2.5])
    banner_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#18335C')),
        ('BACKGROUND', (0, 1), (0, 1), colors.HexColor('#EAB308')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (0, 0), 4),
        ('BOTTOMPADDING', (0, 0), (0, 0), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(banner_table)
    story.append(Spacer(1, 5))

    # 3. School Details Table
    enrolled_classes = sorted(list(set(school.students.values_list('class_level', flat=True))))
    classes_str = ", ".join(str(c) for c in enrolled_classes) if enrolled_classes else "6, 7, 8, 9, 10"

    school_info = [
        [
            Paragraph("School", cell_meta_label),
            Paragraph(school.name, cell_meta_val_bold),
            Paragraph("UDISE code", cell_meta_label),
            Paragraph(str(school.udise_code), cell_meta_val),
            Paragraph("Mandal", cell_meta_label),
            Paragraph(school.mandal.name if school.mandal else "—", cell_meta_val)
        ],
        [
            Paragraph("School type", cell_meta_label),
            Paragraph(school.get_school_type_display(), cell_meta_val),
            Paragraph("Classes", cell_meta_label),
            Paragraph(classes_str, cell_meta_val),
            Paragraph("Generated on", cell_meta_label),
            Paragraph(datetime.now().strftime("%d-%m-%Y %I:%M %p"), cell_meta_val)
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

    boys_enrolled = school.boys_enrolled_count()
    boys_short = school.students.filter(gender='BOY', detail_level=StudentDetailLevel.SHORT).count()
    boys_brief = school.students.filter(gender='BOY', detail_level=StudentDetailLevel.BRIEF).count()
    boys_vacant = max(0, school.boys_quota - boys_enrolled)

    girls_enrolled = school.girls_enrolled_count()
    girls_short = school.students.filter(gender='GIRL', detail_level=StudentDetailLevel.SHORT).count()
    girls_brief = school.students.filter(gender='GIRL', detail_level=StudentDetailLevel.BRIEF).count()
    girls_vacant = max(0, school.girls_quota - girls_enrolled)

    leader_quota = school.max_leaders_count()
    leader_enrolled = school.unit_leaders.count()
    leader_vacant = max(0, leader_quota - leader_enrolled)

    sum_data = [
        [
            Paragraph("Unit", ParagraphStyle('THL', parent=th_style, alignment=0)),
            Paragraph("Quota", th_style),
            Paragraph("Enrolled", th_style),
            Paragraph("Short details", th_style),
            Paragraph("Brief details", th_style),
            Paragraph("Vacant", th_style)
        ],
        [Paragraph("Scouts (Boys)", td_style_left), Paragraph(str(school.boys_quota), td_style_center), Paragraph(str(boys_enrolled), td_style_center), Paragraph(str(boys_short), td_style_center), Paragraph(str(boys_brief), td_style_center), Paragraph(str(boys_vacant), td_style_center)],
        [Paragraph("Guides (Girls)", td_style_left), Paragraph(str(school.girls_quota), td_style_center), Paragraph(str(girls_enrolled), td_style_center), Paragraph(str(girls_short), td_style_center), Paragraph(str(girls_brief), td_style_center), Paragraph(str(girls_vacant), td_style_center)],
        [Paragraph("Unit leaders", td_style_left), Paragraph(str(leader_quota), td_style_center), Paragraph(str(leader_enrolled), td_style_center), Paragraph("", td_style_center), Paragraph("", td_style_center), Paragraph(str(leader_vacant), td_style_center)],
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
        ]
    ]

    # Pre-populate rows for Scout Master and Guide Captain
    scout_master = school.unit_leaders.filter(role__in=['SCOUT_MASTER', 'CUB_MASTER']).first()
    guide_captain = school.unit_leaders.filter(role__in=['GUIDE_CAPTAIN', 'FLOCK_LEADER']).first()

    def format_leader_meas(ldr):
        if not ldr:
            return ""
        m = []
        if ldr.height_cm: m.append(f"Ht {ldr.height_cm}cm")
        if ldr.chest_bust: m.append(f"Chest {ldr.chest_bust}" if ldr.gender == 'MALE' else f"Bust {ldr.chest_bust}")
        if ldr.waist: m.append(f"Waist {ldr.waist}")
        if ldr.neck and ldr.gender == 'MALE': m.append(f"Neck {ldr.neck}")
        if ldr.hip and ldr.gender == 'FEMALE': m.append(f"Hip {ldr.hip}")
        if ldr.shoulder: m.append(f"Sh {ldr.shoulder}")
        if ldr.sleeve: m.append(f"Sleeve {ldr.sleeve}")
        if ldr.top_length: m.append(f"Shirt {ldr.top_length}" if ldr.gender == 'MALE' else f"Kameez {ldr.top_length}")
        if ldr.bottom_length: m.append(f"Pant {ldr.bottom_length}" if ldr.gender == 'MALE' else f"Salwar {ldr.bottom_length}")
        if ldr.shoe_size: m.append(f"Shoe {ldr.shoe_size}")
        return ", ".join(m)

    if scout_master:
        leader_data.append([
            Paragraph(scout_master.get_role_display(), td_style_left),
            Paragraph("Scouts" if scout_master.role == 'SCOUT_MASTER' else "Cubs", td_style_left),
            Paragraph(scout_master.name, td_style_left_bold),
            Paragraph(scout_master.designation or "TEACHER", td_style_left),
            Paragraph(scout_master.mobile or "", td_style_left),
            Paragraph(str(scout_master.uniform_size or ""), td_style_center),
            Paragraph(format_leader_meas(scout_master), td_style_left)
        ])
    else:
        leader_data.append([
            Paragraph("Scout Master", td_style_left),
            Paragraph("Scouts", td_style_left),
            Paragraph("<i>Not appointed</i>", ParagraphStyle('TDI', parent=td_style_left, fontName='Helvetica-Oblique', textColor=colors.HexColor('#64748B'))),
            Paragraph("", td_style_left),
            Paragraph("", td_style_left),
            Paragraph("", td_style_center),
            Paragraph("", td_style_left)
        ])

    if guide_captain:
        leader_data.append([
            Paragraph(guide_captain.get_role_display(), td_style_left),
            Paragraph("Guides" if guide_captain.role == 'GUIDE_CAPTAIN' else "Bulbuls", td_style_left),
            Paragraph(guide_captain.name, td_style_left_bold),
            Paragraph(guide_captain.designation or "TEACHER", td_style_left),
            Paragraph(guide_captain.mobile or "", td_style_left),
            Paragraph(str(guide_captain.uniform_size or ""), td_style_center),
            Paragraph(format_leader_meas(guide_captain), td_style_left)
        ])
    else:
        leader_data.append([
            Paragraph("Guide Captain", td_style_left),
            Paragraph("Guides", td_style_left),
            Paragraph("<i>Not appointed</i>", ParagraphStyle('TDI', parent=td_style_left, fontName='Helvetica-Oblique', textColor=colors.HexColor('#64748B'))),
            Paragraph("", td_style_left),
            Paragraph("", td_style_left),
            Paragraph("", td_style_center),
            Paragraph("", td_style_left)
        ])

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

    # 6. Boys – Scouts Table
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

    table_style_boys = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
    ]

    boys_qs = list(school.students.filter(gender='BOY').order_by('class_level', 'name'))
    boys_count = len(boys_qs)

    if boys_count > 0:
        story.append(Paragraph(f"Boys – Scouts ({boys_count} of {school.boys_quota})", sec_heading_boys))

        # Rows 0-10 on page 1, rows 10+ on page 2 (if co-ed standard 16+16 layout)
        p1_boys = boys_qs[:10]
        p2_boys = boys_qs[10:]

        boys_p1_data = [make_boys_header()]
        for idx, s in enumerate(p1_boys, start=1):
            det_label = "Brief" if s.detail_level == StudentDetailLevel.BRIEF else "Short"
            boys_p1_data.append([
                Paragraph(str(idx), td_style_center),
                Paragraph(s.name, td_style_left_bold),
                Paragraph(s.father_name, td_style_left),
                Paragraph(str(s.class_level), td_style_center),
                Paragraph(str(s.uniform_size or ""), td_style_center),
                Paragraph(str(s.height_cm or ""), td_style_center),
                Paragraph(str(s.chest or ""), td_style_center),
                Paragraph(str(s.waist or ""), td_style_center),
                Paragraph(str(s.neck or ""), td_style_center),
                Paragraph(str(s.shoulder or ""), td_style_center),
                Paragraph(str(s.sleeve or ""), td_style_center),
                Paragraph(str(s.shirt_length or ""), td_style_center),
                Paragraph(str(s.pant_length or ""), td_style_center),
                Paragraph(str(s.shoe_size or ""), td_style_center),
                Paragraph(det_label, td_style_center),
            ])

        boys_p1_table = Table(boys_p1_data, colWidths=boys_col_widths)
        boys_p1_table.setStyle(TableStyle(table_style_boys))
        story.append(boys_p1_table)

        if p2_boys:
            story.append(PageBreak())
            boys_p2_data = [make_boys_header()]
            for idx, s in enumerate(p2_boys, start=11):
                det_label = "Brief" if s.detail_level == StudentDetailLevel.BRIEF else "Short"
                boys_p2_data.append([
                    Paragraph(str(idx), td_style_center),
                    Paragraph(s.name, td_style_left_bold),
                    Paragraph(s.father_name, td_style_left),
                    Paragraph(str(s.class_level), td_style_center),
                    Paragraph(str(s.uniform_size or ""), td_style_center),
                    Paragraph(str(s.height_cm or ""), td_style_center),
                    Paragraph(str(s.chest or ""), td_style_center),
                    Paragraph(str(s.waist or ""), td_style_center),
                    Paragraph(str(s.neck or ""), td_style_center),
                    Paragraph(str(s.shoulder or ""), td_style_center),
                    Paragraph(str(s.sleeve or ""), td_style_center),
                    Paragraph(str(s.shirt_length or ""), td_style_center),
                    Paragraph(str(s.pant_length or ""), td_style_center),
                    Paragraph(str(s.shoe_size or ""), td_style_center),
                    Paragraph(det_label, td_style_center),
                ])
            boys_p2_table = Table(boys_p2_data, colWidths=boys_col_widths)
            boys_p2_table.setStyle(TableStyle(table_style_boys))
            story.append(boys_p2_table)
            story.append(Spacer(1, 2))
            story.append(Paragraph("Height in cm; all other measurements in inches.", note_style))
            story.append(Spacer(1, 6))
        else:
            story.append(Spacer(1, 2))
            story.append(Paragraph("Height in cm; all other measurements in inches.", note_style))
            story.append(Spacer(1, 6))
    elif 'BOY' in school.allowed_genders():
        story.append(Paragraph(f"Boys – Scouts (0 of {school.boys_quota})", sec_heading_boys))
        story.append(Paragraph("<i>No scout enrollments recorded.</i>", td_style_left))
        story.append(Spacer(1, 6))

    # 7. Girls – Guides Table
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

    table_style_girls = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7C3AED')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
    ]

    girls_qs = list(school.students.filter(gender='GIRL').order_by('class_level', 'name'))
    girls_count = len(girls_qs)

    if girls_count > 0:
        story.append(Paragraph(f"Girls – Guides ({girls_count} of {school.girls_quota})", sec_heading_girls))
        girls_data = [make_girls_header()]
        for idx, s in enumerate(girls_qs, start=1):
            det_label = "Brief" if s.detail_level == StudentDetailLevel.BRIEF else "Short"
            girls_data.append([
                Paragraph(str(idx), td_style_center),
                Paragraph(s.name, td_style_left_bold),
                Paragraph(s.father_name, td_style_left),
                Paragraph(str(s.class_level), td_style_center),
                Paragraph(str(s.uniform_size or ""), td_style_center),
                Paragraph(str(s.height_cm or ""), td_style_center),
                Paragraph(str(s.bust or ""), td_style_center),
                Paragraph(str(s.waist or ""), td_style_center),
                Paragraph(str(s.hip or ""), td_style_center),
                Paragraph(str(s.shoulder or ""), td_style_center),
                Paragraph(str(s.sleeve or ""), td_style_center),
                Paragraph(str(s.kameez_length or ""), td_style_center),
                Paragraph(str(s.salwar_length or ""), td_style_center),
                Paragraph(str(s.shoe_size or ""), td_style_center),
                Paragraph(det_label, td_style_center),
            ])
        girls_table = Table(girls_data, colWidths=girls_col_widths)
        girls_table.setStyle(TableStyle(table_style_girls))
        story.append(girls_table)
        story.append(Spacer(1, 2))
        story.append(Paragraph("Height in cm; all other measurements in inches.", note_style))
        story.append(Spacer(1, 28))
    elif 'GIRL' in school.allowed_genders():
        story.append(Paragraph(f"Girls – Guides (0 of {school.girls_quota})", sec_heading_girls))
        story.append(Paragraph("<i>No guide enrollments recorded.</i>", td_style_left))
        story.append(Spacer(1, 28))

    # 8. Clean Signature Section
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
    story.append(KeepTogether([sig_table]))

    doc.build(story, canvasmaker=CustomDocCanvas)
    buffer.seek(0)
    return buffer

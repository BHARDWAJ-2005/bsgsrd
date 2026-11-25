import io
from datetime import datetime, date
from decimal import Decimal
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.utils import get_column_letter
from django.db import transaction
from .models import School, Student, UnitLeader, AuditLog, SchoolType, StudentDetailLevel

# Styling constants
HEADER_FILL_REQUIRED = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")  # Navy Blue
HEADER_FILL_OPTIONAL = PatternFill(start_color="475569", end_color="475569", fill_type="solid")  # Slate Gray
HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
BORDER_THIN = Border(
    left=Side(style='thin', color='CBD5E1'),
    right=Side(style='thin', color='CBD5E1'),
    top=Side(style='thin', color='CBD5E1'),
    bottom=Side(style='thin', color='CBD5E1')
)

BOYS_COLUMNS = [
    ("Name*", True),
    ("Father Name*", True),
    ("Class*", True),
    ("Height (cm)*", True),
    ("Uniform Size*", True),
    ("Shoe Size*", True),
    ("Date of Birth (YYYY-MM-DD)", False),
    ("Parent Mobile", False),
    ("Chest (in)", False),
    ("Waist (in)", False),
    ("Neck (in)", False),
    ("Shoulder (in)", False),
    ("Sleeve (in)", False),
    ("Shirt Length (in)", False),
    ("Pant Length (in)", False),
]

GIRLS_COLUMNS = [
    ("Name*", True),
    ("Father Name*", True),
    ("Class*", True),
    ("Height (cm)*", True),
    ("Uniform Size*", True),
    ("Shoe Size*", True),
    ("Date of Birth (YYYY-MM-DD)", False),
    ("Parent Mobile", False),
    ("Bust (in)", False),
    ("Waist (in)", False),
    ("Hip (in)", False),
    ("Shoulder (in)", False),
    ("Sleeve (in)", False),
    ("Shirt Length (in)", False),
    ("Pant Length (in)", False),
]


def generate_school_excel_template(school: School) -> io.BytesIO:
    """Generates an openpyxl workbook tailored to the school's type with dropdown validations."""
    wb = openpyxl.Workbook()
    # remove default sheet
    wb.remove(wb.active)

    allowed_classes_str = ",".join(str(c) for c in school.allowed_classes())
    allowed_sizes_str = ",".join(school.allowed_uniform_sizes())

    sheets_to_create = []
    if 'BOY' in school.allowed_genders():
        sheets_to_create.append(('Boys Enrollment', BOYS_COLUMNS, 'BOY'))
    if 'GIRL' in school.allowed_genders():
        sheets_to_create.append(('Girls Enrollment', GIRLS_COLUMNS, 'GIRL'))

    for sheet_title, columns, gender in sheets_to_create:
        ws = wb.create_sheet(title=sheet_title)
        ws.views.sheetView[0].showGridLines = True

        # Header instructions row
        ws.merge_cells('A1:O1')
        top_cell = ws['A1']
        top_cell.value = (
            f"BHARAT SCOUTS & GUIDES - SANGAREDDY | School: {school.name} (UDISE: {school.udise_code}) | "
            f"Type: {school.get_school_type_display()} | Gender: {gender}s | * Columns are Mandatory"
        )
        top_cell.font = Font(name="Calibri", size=10, bold=True, color="1E293B")
        top_cell.fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
        top_cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 24

        # Column headers row (Row 2)
        for col_idx, (col_name, is_req) in enumerate(columns, start=1):
            cell = ws.cell(row=2, column=col_idx, value=col_name)
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL_REQUIRED if is_req else HEADER_FILL_OPTIONAL
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = BORDER_THIN
        ws.row_dimensions[2].height = 28

        # Add Data Validation for Class (Column C) and Uniform Size (Column E)
        class_dv = DataValidation(type="list", formula1=f'"{allowed_classes_str}"', allow_blank=False)
        class_dv.error = f"Allowed classes for this school are: {allowed_classes_str}"
        class_dv.errorTitle = "Invalid Class"
        ws.add_data_validation(class_dv)
        class_dv.add(f"C3:C150")

        size_dv = DataValidation(type="list", formula1=f'"{allowed_sizes_str}"', allow_blank=False)
        size_dv.error = f"Allowed sizes are: {allowed_sizes_str}"
        size_dv.errorTitle = "Invalid Uniform Size"
        ws.add_data_validation(size_dv)
        size_dv.add(f"E3:E150")

        # Freeze panes at Row 3
        ws.freeze_panes = "A3"

        # Set column widths
        for col_idx, (col_name, _) in enumerate(columns, start=1):
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = max(len(col_name) + 4, 14)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def _parse_decimal_or_none(val, field_name, row_num, sheet_name):
    if val is None or str(val).strip() == '':
        return None
    try:
        dec = Decimal(str(val).strip())
        if dec < 10 or dec > 60:
            raise ValueError(f"Value {dec} outside 10-60 inch range.")
        if (float(dec) * 10) % 5 != 0:
            raise ValueError(f"Value {dec} must be whole or half inch (e.g. 26 or 26.5).")
        return dec
    except Exception as e:
        raise ValueError(f"Sheet '{sheet_name}', Row {row_num}: Invalid measurement '{field_name}': {val}. Error: {e}")


def import_students_from_excel(school: School, file_obj, user=None, ip_address=""):
    """
    All-or-nothing transactional import of students from Excel workbook.
    If any row has an error, nothing is imported and full list of errors is returned.
    Safe and idempotent based on natural key: (school, normalized name, normalized father name, class).
    """
    wb = openpyxl.load_workbook(file_obj, data_only=True)
    errors = []
    parsed_records = []

    # Prepare sheet mapping
    sheet_configs = []
    if 'BOY' in school.allowed_genders():
        sheet_configs.append(('Boys Enrollment', 'BOY', BOYS_COLUMNS))
    if 'GIRL' in school.allowed_genders():
        sheet_configs.append(('Girls Enrollment', 'GIRL', GIRLS_COLUMNS))

    # Also search by sheet names case-insensitively if user changed the title slightly
    existing_sheets_lower = {s.lower().strip(): s for s in wb.sheetnames}

    for expected_name, gender, col_defs in sheet_configs:
        sheet_key = expected_name.lower().strip()
        matched_sheet = None
        for k in existing_sheets_lower:
            if gender.lower() in k or sheet_key in k:
                matched_sheet = existing_sheets_lower[k]
                break

        if not matched_sheet:
            continue

        ws = wb[matched_sheet]
        row_idx = 2  # data starts at row 3 (row 1 is title, row 2 is headers)

        for row in ws.iter_rows(min_row=3, values_only=True):
            row_idx += 1
            if not any(row):  # skip completely blank rows
                continue

            name = str(row[0]).strip() if row[0] is not None else ""
            father_name = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
            class_val = row[2] if len(row) > 2 else None
            height_val = row[3] if len(row) > 3 else None
            uniform_val = str(row[4]).strip() if len(row) > 4 and row[4] is not None else ""
            shoe_val = str(row[5]).strip() if len(row) > 5 and row[5] is not None else ""

            if not name:
                errors.append(f"Sheet '{matched_sheet}', Row {row_idx}: Student Name is required.")
                continue
            if not father_name:
                errors.append(f"Sheet '{matched_sheet}', Row {row_idx}: Father's Name is required for '{name}'.")
            
            # Validate class
            try:
                class_int = int(class_val)
                if class_int not in school.allowed_classes():
                    errors.append(
                        f"Sheet '{matched_sheet}', Row {row_idx}: Class {class_int} is not allowed for {school.get_school_type_display()}. Allowed: {school.allowed_classes()}"
                    )
            except (TypeError, ValueError):
                errors.append(f"Sheet '{matched_sheet}', Row {row_idx}: Invalid Class value '{class_val}'.")
                class_int = None

            # Validate height
            try:
                height_dec = Decimal(str(height_val).strip())
                if height_dec < 90 or height_dec > 220:
                    errors.append(f"Sheet '{matched_sheet}', Row {row_idx}: Height ({height_dec} cm) must be between 90 and 220 cm.")
            except Exception:
                errors.append(f"Sheet '{matched_sheet}', Row {row_idx}: Invalid Height '{height_val}'. Must be a number in cm.")
                height_dec = None

            # Validate uniform size
            if not uniform_val:
                errors.append(f"Sheet '{matched_sheet}', Row {row_idx}: Uniform Size is mandatory.")
            elif uniform_val not in school.allowed_uniform_sizes():
                errors.append(
                    f"Sheet '{matched_sheet}', Row {row_idx}: Uniform size '{uniform_val}' not recognized. Allowed: {school.allowed_uniform_sizes()}"
                )

            if not shoe_val:
                errors.append(f"Sheet '{matched_sheet}', Row {row_idx}: Shoe Size is mandatory.")

            # Optional BRIEF fields
            dob_val = row[6] if len(row) > 6 else None
            dob = None
            if dob_val:
                if isinstance(dob_val, (datetime, date)):
                    dob = dob_val.date() if isinstance(dob_val, datetime) else dob_val
                else:
                    try:
                        dob = datetime.strptime(str(dob_val).strip()[:10], "%Y-%m-%d").date()
                    except ValueError:
                        errors.append(f"Sheet '{matched_sheet}', Row {row_idx}: Invalid Date of Birth format '{dob_val}'. Use YYYY-MM-DD.")

            parent_mobile = str(row[7]).strip() if len(row) > 7 and row[7] is not None else ""
            if parent_mobile:
                # remove any decimals like '9876543210.0' from excel numbers
                parent_mobile = parent_mobile.split('.')[0]
                if not parent_mobile.isdigit() or len(parent_mobile) < 10:
                    errors.append(f"Sheet '{matched_sheet}', Row {row_idx}: Parent Mobile '{parent_mobile}' must be at least 10 digits.")

            # Parse tailoring measurements
            has_measurements = False
            measurements = {}
            if gender == 'BOY':
                meas_keys = ['chest', 'waist', 'neck', 'shoulder', 'sleeve', 'shirt_length', 'pant_length']
                start_col = 8
            else:
                meas_keys = ['bust', 'waist', 'hip', 'shoulder', 'sleeve', 'kameez_length', 'salwar_length']
                start_col = 8

            for idx, key in enumerate(meas_keys):
                cell_val = row[start_col + idx] if len(row) > (start_col + idx) else None
                try:
                    dec = _parse_decimal_or_none(cell_val, key, row_idx, matched_sheet)
                    measurements[key] = dec
                    if dec is not None:
                        has_measurements = True
                except ValueError as ve:
                    errors.append(str(ve))

            detail_level = StudentDetailLevel.BRIEF if (has_measurements or dob or parent_mobile) else StudentDetailLevel.SHORT

            parsed_records.append({
                'gender': gender,
                'name': name,
                'father_name': father_name,
                'class_level': class_int,
                'height_cm': height_dec,
                'uniform_size': uniform_val,
                'shoe_size': shoe_val,
                'dob': dob,
                'parent_mobile': parent_mobile,
                'measurements': measurements,
                'detail_level': detail_level,
                'row_idx': row_idx,
                'sheet': matched_sheet
            })

    if not parsed_records and not errors:
        return False, ["The uploaded Excel file contains no student data rows."], 0

    if errors:
        return False, errors, 0

    # Check quotas and idempotency
    boys_new_count = 0
    girls_new_count = 0

    existing_students = {
        (s.gender, s.name.strip().lower(), s.father_name.strip().lower(), s.class_level): s
        for s in school.students.all()
    }

    for rec in parsed_records:
        key = (rec['gender'], rec['name'].strip().lower(), rec['father_name'].strip().lower(), rec['class_level'])
        if key not in existing_students:
            if rec['gender'] == 'BOY':
                boys_new_count += 1
            else:
                girls_new_count += 1

    current_boys = school.boys_enrolled_count()
    current_girls = school.girls_enrolled_count()

    if current_boys + boys_new_count > school.boys_quota:
        exceeded = (current_boys + boys_new_count) - school.boys_quota
        return False, [
            f"Boys quota exceeded! Your school quota is {school.boys_quota}. Currently enrolled: {current_boys}. "
            f"File attempts to add {boys_new_count} new boys (exceeds by {exceeded})."
        ], 0

    if current_girls + girls_new_count > school.girls_quota:
        exceeded = (current_girls + girls_new_count) - school.girls_quota
        return False, [
            f"Girls quota exceeded! Your school quota is {school.girls_quota}. Currently enrolled: {current_girls}. "
            f"File attempts to add {girls_new_count} new girls (exceeds by {exceeded})."
        ], 0

    # Perform all-or-nothing transactional import
    created_count = 0
    updated_count = 0

    with transaction.atomic():
        # Lock school row for update
        school_locked = School.objects.select_for_update().get(pk=school.pk)

        for rec in parsed_records:
            key = (rec['gender'], rec['name'].strip().lower(), rec['father_name'].strip().lower(), rec['class_level'])
            student = existing_students.get(key)
            if not student:
                student = Student(
                    school=school_locked,
                    gender=rec['gender'],
                    name=rec['name'],
                    father_name=rec['father_name'],
                    class_level=rec['class_level'],
                )
                created_count += 1
            else:
                updated_count += 1

            student.height_cm = rec['height_cm']
            student.uniform_size = rec['uniform_size']
            student.shoe_size = rec['shoe_size']
            student.detail_level = rec['detail_level']
            student.dob = rec['dob']
            student.parent_mobile = rec['parent_mobile']

            # Assign measurements
            for k, v in rec['measurements'].items():
                setattr(student, k, v)

            student.full_clean()
            student.save()

        # Create audit log
        AuditLog.objects.create(
            school=school_locked,
            user=user,
            action="EXCEL_IMPORT",
            target_type="Student",
            target_id=f"Count: {created_count + updated_count}",
            description=f"Excel import successful: {created_count} created, {updated_count} updated.",
            ip_address=ip_address
        )

    return True, [], created_count + updated_count


def export_school_excel(school: School) -> io.BytesIO:
    """
    Exports school complete workbook matching the template layout.
    Boys Enrollment and Girls Enrollment are the primary sheets so the workbook
    is identical in format to the download template and can be re-imported seamlessly.
    Also includes Unit Leaders, Uniform Sizing Summary, and School Overview.
    """
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    allowed_classes_str = ",".join(str(c) for c in school.allowed_classes())
    allowed_sizes_str = ",".join(school.allowed_uniform_sizes())

    # Helper for student sheets matching the exact template format
    def build_student_sheet(title, gender, col_list):
        ws = wb.create_sheet(title=title)
        ws.views.sheetView[0].showGridLines = True

        # Header instructions row (Row 1)
        ws.merge_cells('A1:O1')
        top_cell = ws['A1']
        top_cell.value = (
            f"BHARAT SCOUTS & GUIDES - SANGAREDDY | School: {school.name} (UDISE: {school.udise_code}) | "
            f"Type: {school.get_school_type_display()} | Gender: {gender}s | * Columns are Mandatory"
        )
        top_cell.font = Font(name="Calibri", size=10, bold=True, color="1E293B")
        top_cell.fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
        top_cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 24

        # Column headers row (Row 2) - identical to template
        for col_idx, (col_name, is_req) in enumerate(col_list, start=1):
            cell = ws.cell(row=2, column=col_idx, value=col_name)
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL_REQUIRED if is_req else HEADER_FILL_OPTIONAL
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = BORDER_THIN
        ws.row_dimensions[2].height = 28

        # Data Validation for Class (Column C) and Uniform Size (Column E)
        class_dv = DataValidation(type="list", formula1=f'"{allowed_classes_str}"', allow_blank=False)
        class_dv.error = f"Allowed classes: {allowed_classes_str}"
        class_dv.errorTitle = "Invalid Class"
        ws.add_data_validation(class_dv)
        class_dv.add("C3:C200")

        size_dv = DataValidation(type="list", formula1=f'"{allowed_sizes_str}"', allow_blank=False)
        size_dv.error = f"Allowed sizes: {allowed_sizes_str}"
        size_dv.errorTitle = "Invalid Uniform Size"
        ws.add_data_validation(size_dv)
        size_dv.add("E3:E200")

        # Freeze panes at Row 3
        ws.freeze_panes = "A3"

        # Set column widths
        for col_idx, (col_name, _) in enumerate(col_list, start=1):
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = max(len(col_name) + 4, 14)

        # Populate student data rows starting at Row 3
        students = school.students.filter(gender=gender).order_by('class_level', 'name')
        for r_idx, s in enumerate(students, start=3):
            if gender == 'BOY':
                row_vals = [
                    s.name, s.father_name, s.class_level, float(s.height_cm), s.uniform_size, s.shoe_size,
                    str(s.dob) if s.dob else "", s.parent_mobile or "",
                    float(s.chest) if s.chest else "", float(s.waist) if s.waist else "",
                    float(s.neck) if s.neck else "", float(s.shoulder) if s.shoulder else "",
                    float(s.sleeve) if s.sleeve else "", float(s.shirt_length) if s.shirt_length else "",
                    float(s.pant_length) if s.pant_length else ""
                ]
            else:
                row_vals = [
                    s.name, s.father_name, s.class_level, float(s.height_cm), s.uniform_size, s.shoe_size,
                    str(s.dob) if s.dob else "", s.parent_mobile or "",
                    float(s.bust) if s.bust else "", float(s.waist) if s.waist else "",
                    float(s.hip) if s.hip else "", float(s.shoulder) if s.shoulder else "",
                    float(s.sleeve) if s.sleeve else "", float(s.kameez_length) if s.kameez_length else "",
                    float(s.salwar_length) if s.salwar_length else ""
                ]
            for c_idx, val in enumerate(row_vals, start=1):
                cell = ws.cell(row=r_idx, column=c_idx, value=val)
                cell.border = BORDER_THIN
                if c_idx in [3, 4, 5, 6]:
                    cell.alignment = Alignment(horizontal="center")

    # 1. Primary sheets (same sheet names as template)
    if 'BOY' in school.allowed_genders():
        build_student_sheet("Boys Enrollment", "BOY", BOYS_COLUMNS)
    if 'GIRL' in school.allowed_genders():
        build_student_sheet("Girls Enrollment", "GIRL", GIRLS_COLUMNS)

    # 2. Sheet: Uniform Ordering Summary (for Tailors & District Supply)
    ws_sum = wb.create_sheet(title="Uniform Sizing Summary")
    ws_sum.views.sheetView[0].showGridLines = True
    ws_sum.column_dimensions['A'].width = 20
    ws_sum.column_dimensions['B'].width = 15
    ws_sum.column_dimensions['C'].width = 15
    ws_sum.column_dimensions['D'].width = 15

    sum_headers = ["Uniform Size", "Boys Count", "Girls Count", "Total Required"]
    for c_idx, h in enumerate(sum_headers, start=1):
        cell = ws_sum.cell(row=1, column=c_idx, value=h)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL_REQUIRED
        cell.alignment = Alignment(horizontal="center")

    all_sizes = ['24', '26', '28', '30', '32', '34', '36', '38', '40', '42', '44', '46', '48']
    row_cur = 2
    for sz in all_sizes:
        b_cnt = school.students.filter(gender='BOY', uniform_size=sz).count()
        g_cnt = school.students.filter(gender='GIRL', uniform_size=sz).count()
        tot = b_cnt + g_cnt
        if tot > 0:
            ws_sum.cell(row=row_cur, column=1, value=f"Size {sz}").border = BORDER_THIN
            ws_sum.cell(row=row_cur, column=2, value=b_cnt).border = BORDER_THIN
            ws_sum.cell(row=row_cur, column=3, value=g_cnt).border = BORDER_THIN
            tot_cell = ws_sum.cell(row=row_cur, column=4, value=tot)
            tot_cell.font = Font(bold=True)
            tot_cell.border = BORDER_THIN
            row_cur += 1

    tot_row = row_cur
    ws_sum.cell(row=tot_row, column=1, value="GRAND TOTAL").font = Font(bold=True)
    ws_sum.cell(row=tot_row, column=2, value=school.boys_enrolled_count()).font = Font(bold=True)
    ws_sum.cell(row=tot_row, column=3, value=school.girls_enrolled_count()).font = Font(bold=True)
    ws_sum.cell(row=tot_row, column=4, value=school.total_enrolled_count()).font = Font(bold=True)

    # 3. Sheet: Unit Leaders
    ws_lead = wb.create_sheet(title="Unit Leaders")
    ws_lead.views.sheetView[0].showGridLines = True
    lead_headers = [
        "Role", "Teacher Name", "Gender", "Designation", "Mobile", "Email",
        "Height (cm)", "Uniform Size", "Shoe Size",
        "Chest/Bust (in)", "Waist (in)", "Neck (in)", "Shoulder (in)", "Sleeve (in)",
        "Top Length (in)", "Bottom Length (in)", "Hip (in)"
    ]
    for c_idx, h in enumerate(lead_headers, start=1):
        cell = ws_lead.cell(row=1, column=c_idx, value=h)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL_REQUIRED
        ws_lead.column_dimensions[get_column_letter(c_idx)].width = max(len(h) + 3, 14)

    for r_idx, l in enumerate(school.unit_leaders.all(), start=2):
        l_vals = [
            l.get_role_display(), l.name, l.get_gender_display(), l.designation or "", l.mobile, l.email,
            float(l.height_cm) if l.height_cm else "",
            l.uniform_size,
            l.shoe_size,
            float(l.chest_bust) if l.chest_bust else "",
            float(l.waist) if l.waist else "",
            float(l.neck) if l.neck else "",
            float(l.shoulder) if l.shoulder else "",
            float(l.sleeve) if l.sleeve else "",
            float(l.top_length) if l.top_length else "",
            float(l.bottom_length) if l.bottom_length else "",
            float(l.hip) if l.hip else ""
        ]
        for c_idx, val in enumerate(l_vals, start=1):
            cell = ws_lead.cell(row=r_idx, column=c_idx, value=val)
            cell.border = BORDER_THIN

    # 4. Sheet: School Overview
    ws_info = wb.create_sheet(title="School Overview")
    ws_info.views.sheetView[0].showGridLines = True
    ws_info.column_dimensions['A'].width = 25
    ws_info.column_dimensions['B'].width = 40

    info_rows = [
        ("School Name", school.name),
        ("UDISE Code", school.udise_code),
        ("Mandal", school.mandal.name),
        ("District", school.mandal.district.name),
        ("School Category", school.get_school_type_display()),
        ("Boys Quota", school.boys_quota),
        ("Boys Enrolled", school.boys_enrolled_count()),
        ("Girls Quota", school.girls_quota),
        ("Girls Enrolled", school.girls_enrolled_count()),
        ("Total Enrolled", school.total_enrolled_count()),
        ("Export Timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    ]
    for r_idx, (lbl, val) in enumerate(info_rows, start=1):
        cell_lbl = ws_info.cell(row=r_idx, column=1, value=lbl)
        cell_lbl.font = Font(bold=True)
        cell_lbl.fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
        ws_info.cell(row=r_idx, column=2, value=str(val))

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def export_district_consolidated_excel() -> io.BytesIO:
    """Exports district-wide master workbook with mandal progress and uniform size breakdown."""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    # Sheet 1: Mandal Progress
    ws_mandal = wb.create_sheet(title="Mandal Progress")
    ws_mandal.views.sheetView[0].showGridLines = True
    m_headers = ["Mandal Name", "Total Schools", "Boys Quota", "Boys Enrolled", "Girls Quota", "Girls Enrolled", "Total Enrolled", "Progress %"]
    for c_idx, h in enumerate(m_headers, start=1):
        cell = ws_mandal.cell(row=1, column=c_idx, value=h)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL_REQUIRED
        ws_mandal.column_dimensions[get_column_letter(c_idx)].width = 18

    row_idx = 2
    from .models import Mandal
    for m in Mandal.objects.all().order_by('name'):
        m_schools = m.schools.all()
        m_boys_q = sum(s.boys_quota for s in m_schools)
        m_girls_q = sum(s.girls_quota for s in m_schools)
        m_boys_enr = Student.objects.filter(school__mandal=m, gender='BOY').count()
        m_girls_enr = Student.objects.filter(school__mandal=m, gender='GIRL').count()
        tot_q = m_boys_q + m_girls_q
        tot_enr = m_boys_enr + m_girls_enr
        pct = round((tot_enr / tot_q * 100), 1) if tot_q > 0 else 0

        vals = [m.name, m_schools.count(), m_boys_q, m_boys_enr, m_girls_q, m_girls_enr, tot_enr, f"{pct}%"]
        for c_idx, v in enumerate(vals, start=1):
            cell = ws_mandal.cell(row=row_idx, column=c_idx, value=v)
            cell.border = BORDER_THIN
        row_idx += 1

    # Sheet 2: District Uniform Supply Count
    ws_supply = wb.create_sheet(title="District Uniform Orders")
    ws_supply.views.sheetView[0].showGridLines = True
    sup_headers = ["Uniform Size", "Boys Count", "Girls Count", "Total District Demand"]
    for c_idx, h in enumerate(sup_headers, start=1):
        cell = ws_supply.cell(row=1, column=c_idx, value=h)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL_REQUIRED
        ws_supply.column_dimensions[get_column_letter(c_idx)].width = 22

    all_sizes = ['24', '26', '28', '30', '32', '34', '36', '38', '40', '42', '44', '46', '48']
    r_cur = 2
    for sz in all_sizes:
        b_cnt = Student.objects.filter(gender='BOY', uniform_size=sz).count()
        g_cnt = Student.objects.filter(gender='GIRL', uniform_size=sz).count()
        tot = b_cnt + g_cnt
        ws_supply.cell(row=r_cur, column=1, value=f"Size {sz}").border = BORDER_THIN
        ws_supply.cell(row=r_cur, column=2, value=b_cnt).border = BORDER_THIN
        ws_supply.cell(row=r_cur, column=3, value=g_cnt).border = BORDER_THIN
        tot_c = ws_supply.cell(row=r_cur, column=4, value=tot)
        tot_c.font = Font(bold=True)
        tot_c.border = BORDER_THIN
        r_cur += 1

    # Sheet 3: District Unit Leaders Roster
    ws_all_lead = wb.create_sheet(title="District Unit Leaders")
    ws_all_lead.views.sheetView[0].showGridLines = True
    dl_headers = [
        "Mandal", "School UDISE", "School Name", "Role", "Leader Name", "Gender",
        "Designation", "Mobile", "Height (cm)", "Uniform Size", "Shoe Size",
        "Chest/Bust", "Waist", "Neck", "Shoulder", "Sleeve", "Top Length", "Bottom Length", "Hip"
    ]
    for c_idx, h in enumerate(dl_headers, start=1):
        cell = ws_all_lead.cell(row=1, column=c_idx, value=h)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL_REQUIRED
        ws_all_lead.column_dimensions[get_column_letter(c_idx)].width = max(len(h) + 3, 14)

    dl_row = 2
    for l in UnitLeader.objects.select_related('school__mandal').all().order_by('school__mandal__name', 'school__name', 'role'):
        row_vals = [
            l.school.mandal.name, l.school.udise_code, l.school.name,
            l.get_role_display(), l.name, l.get_gender_display(),
            l.designation or "", l.mobile or "",
            float(l.height_cm) if l.height_cm else "",
            l.uniform_size or "",
            l.shoe_size or "",
            float(l.chest_bust) if l.chest_bust else "",
            float(l.waist) if l.waist else "",
            float(l.neck) if l.neck else "",
            float(l.shoulder) if l.shoulder else "",
            float(l.sleeve) if l.sleeve else "",
            float(l.top_length) if l.top_length else "",
            float(l.bottom_length) if l.bottom_length else "",
            float(l.hip) if l.hip else "",
        ]
        for c_idx, v in enumerate(row_vals, start=1):
            cell = ws_all_lead.cell(row=dl_row, column=c_idx, value=v)
            cell.border = BORDER_THIN
        dl_row += 1

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output

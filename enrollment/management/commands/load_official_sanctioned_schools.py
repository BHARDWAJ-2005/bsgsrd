import os
import openpyxl
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from enrollment.models import (
    District, Mandal, School, Student, UnitLeader, AuditLog,
    SchoolType, StudentDetailLevel, LeaderRole
)

class Command(BaseCommand):
    help = "Loads all officially sanctioned Bharat Scouts & Guides schools in Sangareddy from the official Excel rosters (112 + 52 + 10 schools)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing schools and unit leaders before re-importing (preserves student registrations)'
        )
        parser.add_argument(
            '--clear-students',
            action='store_true',
            help='Also clear all enrolled students'
        )

    def handle(self, *args, **options):
        clear = options['clear']
        clear_students = options['clear_students']

        self.stdout.write(self.style.NOTICE("Starting import of all officially sanctioned schools for Sangareddy District..."))

        # 1. District
        district, _ = District.objects.get_or_create(
            name="Sangareddy",
            defaults={"code": "SRD"}
        )

        # 2. Admin superuser
        admin_user, _ = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "deo-sangareddy@telangana.gov.in",
                "is_staff": True,
                "is_superuser": True,
                "first_name": "District",
                "last_name": "Admin"
            }
        )
        admin_user.set_password("Admin@Sangareddy2026")
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.save()

        # Handle clear flags
        if clear_students:
            self.stdout.write(self.style.WARNING("Clearing student registrations as requested..."))
            Student.objects.all().delete()

        if clear:
            self.stdout.write(self.style.WARNING("Clearing existing schools and unit leaders..."))
            UnitLeader.objects.all().delete()
            School.objects.all().delete()
            User.objects.exclude(is_superuser=True).delete()

        def clean_mobile(val):
            if val is None:
                return ''
            s = str(val).strip().replace(' ', '').replace('-', '').replace('.', '')
            if len(s) == 12 and s.startswith('91'):
                s = s[2:]
            if s.endswith('0') and len(s) == 11 and s.startswith(('6', '7', '8', '9')):
                s = s[:10]
            digits = ''.join(c for c in s if c.isdigit())
            return digits[:10] if len(digits) >= 10 else digits

        def norm_mandal(m_raw):
            if not m_raw:
                return 'Sangareddy'
            m = str(m_raw).strip().title()
            m = m.replace('Sadashivapet', 'Sadasivpet').replace('Sadashivpet', 'Sadasivpet')
            m = m.replace('Watpally', 'Vatpally')
            m = m.replace('Ramachandrapuram', 'Ramchandrapuram')
            if m == 'Tadkal':
                m = 'Kangti'
            return m

        def is_valid_teacher(name):
            if not name:
                return False
            n = str(name).strip().lower()
            if not n or n in ['-', '--', '---', '0', '0.0', 'nil', 'none', 'no female in school staff.', 'no female teacher', 'vacant']:
                return False
            return True

        default_pw_hash = make_password("BSG@Sangareddy2026")

        schools_data = {}

        # ---------------------------------------------------------
        # FILE 1: 112 Sanctioned Schools
        # ---------------------------------------------------------
        f1 = 'SCOUTS & GUIDES SRD NEW SCHOOLS-112 (1).xlsx'
        if os.path.exists(f1):
            wb1 = openpyxl.load_workbook(f1, data_only=True)
            ws1 = wb1.active
            for r in range(3, ws1.max_row + 1):
                m = ws1.cell(r, 2).value
                u = ws1.cell(r, 3).value
                name = ws1.cell(r, 4).value
                if not m or not u or not name:
                    continue
                u_str = str(int(float(u))).strip()
                schools_data[u_str] = {
                    'udise': u_str,
                    'name': str(name).strip(),
                    'mandal': norm_mandal(m),
                    'hm': str(ws1.cell(r, 5).value or '').strip(),
                    'hm_mob': '',
                    'mt': ws1.cell(r, 6).value,
                    'mdes': str(ws1.cell(r, 7).value or '').strip(),
                    'mmob': clean_mobile(ws1.cell(r, 8).value),
                    'ft': ws1.cell(r, 9).value,
                    'fdes': str(ws1.cell(r, 10).value or '').strip(),
                    'fmob': clean_mobile(ws1.cell(r, 11).value),
                    'sanction_ref': 'BSG/SRD/SANCTION/NEW-112',
                }
            self.stdout.write(self.style.SUCCESS(f"Loaded {len(schools_data)} schools from {f1}"))

        # ---------------------------------------------------------
        # FILE 2: 52 Sanctioned Schools (2026-27 Batch)
        # ---------------------------------------------------------
        f2 = 'BSG  NEW SCHOOLS 2026-27 (5).xlsx'
        if os.path.exists(f2):
            wb2 = openpyxl.load_workbook(f2, data_only=True)
            ws2 = wb2['Sheet1']
            f2_count = 0
            for r in range(3, ws2.max_row + 1):
                name = ws2.cell(r, 4).value
                if not name or 'BHARAT SCOUTS' in str(name):
                    continue
                m = ws2.cell(r, 2).value
                u = ws2.cell(r, 3).value
                # Row 8 is ZPHS Annaram with missing UDISE
                if u is not None and str(u).strip() != '':
                    u_str = str(int(float(u))).strip()
                else:
                    u_str = '36162101206' # Official UDISE for ZPHS Annaram, Gummadidala
                
                schools_data[u_str] = {
                    'udise': u_str,
                    'name': str(name).strip(),
                    'mandal': norm_mandal(m),
                    'hm': str(ws2.cell(r, 5).value or '').strip(),
                    'hm_mob': clean_mobile(ws2.cell(r, 7).value),
                    'mt': ws2.cell(r, 8).value,
                    'mdes': str(ws2.cell(r, 9).value or '').strip(),
                    'mmob': clean_mobile(ws2.cell(r, 10).value),
                    'ft': ws2.cell(r, 11).value,
                    'fdes': str(ws2.cell(r, 12).value or '').strip(),
                    'fmob': clean_mobile(ws2.cell(r, 13).value),
                    'sanction_ref': 'BSG/SRD/SANCTION/2026-27-BATCH2',
                }
                f2_count += 1
            self.stdout.write(self.style.SUCCESS(f"Loaded {f2_count} schools from {f2}"))

        # ---------------------------------------------------------
        # FILE 3: 10 BSG SRD Schools List
        # ---------------------------------------------------------
        f3 = '10 BSG SRD SCHOOLS_List.xlsx'
        if os.path.exists(f3):
            wb3 = openpyxl.load_workbook(f3, data_only=True)
            ws3 = wb3['Schools']
            f3_count = 0
            for r in range(2, ws3.max_row + 1):
                m = ws3.cell(r, 2).value
                name = ws3.cell(r, 3).value
                u = ws3.cell(r, 4).value
                if not m or not name or not u:
                    continue
                u_str = str(int(float(u))).strip()
                # If already loaded from another file with richer info, keep it
                if u_str not in schools_data:
                    schools_data[u_str] = {
                        'udise': u_str,
                        'name': str(name).strip(),
                        'mandal': norm_mandal(m),
                        'hm': str(ws3.cell(r, 5).value or '').strip(),
                        'hm_mob': clean_mobile(ws3.cell(r, 6).value),
                        'mt': ws3.cell(r, 7).value,
                        'mdes': str(ws3.cell(r, 8).value or '').strip(),
                        'mmob': clean_mobile(ws3.cell(r, 9).value),
                        'ft': None,
                        'fdes': '',
                        'fmob': '',
                        'sanction_ref': 'BSG/SRD/SANCTION/2026-27-BATCH3',
                    }
                    f3_count += 1
            self.stdout.write(self.style.SUCCESS(f"Loaded {f3_count} schools from {f3}"))

        self.stdout.write(self.style.NOTICE(f"Total unique sanctioned schools to sync: {len(schools_data)}"))

        saved_schools = 0
        saved_leaders = 0

        for u_code, data in schools_data.items():
            m_name = data['mandal']
            m_code = f"SRD-{m_name[:4].upper()}"
            mandal, _ = Mandal.objects.get_or_create(
                district=district,
                name=m_name,
                defaults={"code": m_code}
            )

            # Determine school type & quotas
            name_upper = data['name'].upper()
            if name_upper.startswith('MPPS'):
                s_type = SchoolType.PRIMARY
                b_quota = 12
                g_quota = 12
            elif name_upper.startswith('MPUPS'):
                s_type = SchoolType.UPPER_PRIMARY
                b_quota = 12
                g_quota = 12
            elif '(GIRLS)' in name_upper or 'GIRLS' in name_upper or 'KGBV' in name_upper:
                s_type = SchoolType.GIRLS_HIGH
                b_quota = 0
                g_quota = 32
            elif 'BOYS' in name_upper and 'CO-ED' not in name_upper and 'COED' not in name_upper:
                s_type = SchoolType.BOYS_HIGH
                b_quota = 32
                g_quota = 0
            else:
                s_type = SchoolType.COED_HIGH
                b_quota = 16
                g_quota = 16

            # School user account
            sch_user, u_created = User.objects.get_or_create(
                username=u_code,
                defaults={
                    "first_name": data['name'][:30],
                    "email": f"school{u_code}@bsg.sangareddy.org"
                }
            )
            if u_created or not sch_user.password:
                sch_user.password = default_pw_hash
                sch_user.save()

            # School profile
            school, s_created = School.objects.get_or_create(
                udise_code=u_code,
                defaults={
                    "name": data['name'],
                    "mandal": mandal,
                    "school_type": s_type,
                    "boys_quota": b_quota,
                    "girls_quota": g_quota,
                    "user": sch_user,
                    "must_change_password": True,
                    "default_password": "BSG@Sangareddy2026",
                    "contact_person": data['hm'],
                    "headmaster_name": data['hm'],
                    "contact_mobile": data['hm_mob'],
                    "is_sanctioned": True,
                    "sanction_order_number": data['sanction_ref'],
                }
            )

            if not s_created:
                # Update details and sync new quota rules
                school.is_sanctioned = True
                school.school_type = s_type
                school.boys_quota = b_quota
                school.girls_quota = g_quota
                if not school.headmaster_name and data['hm']:
                    school.headmaster_name = data['hm']
                if not school.contact_mobile and data['hm_mob']:
                    school.contact_mobile = data['hm_mob']
                school.save()

            saved_schools += 1

            # Unit Leaders (Frozen & Sanctioned)
            # Enforce leader gender & role rules:
            # - GIRLS_HIGH: Only 1 Female Unit Leader (Guide Captain), no male leader
            # - BOYS_HIGH: Only 1 Male Unit Leader (Scout Master), no female leader
            # - COED_HIGH: 2 Unit Leaders (1 Male Scout Master, 1 Female Guide Captain)
            # - PRIMARY/UPPER_PRIMARY: 2 Unit Leaders (1 Male Cub Master, 1 Female Flock Leader)

            if s_type == SchoolType.GIRLS_HIGH:
                # Remove any mistakenly attached male leaders
                school.unit_leaders.filter(gender="MALE").delete()
            elif s_type == SchoolType.BOYS_HIGH:
                # Remove any mistakenly attached female leaders
                school.unit_leaders.filter(gender="FEMALE").delete()

            # 1. Male Teacher (Scout Master or Cub Master) - only for Co-ed, Boys, Primary
            if s_type != SchoolType.GIRLS_HIGH and is_valid_teacher(data['mt']):
                m_name = str(data['mt']).strip()
                m_mobile = data['mmob']
                m_desgn = data['mdes']
                m_role = LeaderRole.CUB_MASTER if s_type in [SchoolType.PRIMARY, SchoolType.UPPER_PRIMARY] else LeaderRole.SCOUT_MASTER
                l_obj, l_created = UnitLeader.objects.get_or_create(
                    school=school,
                    role=m_role,
                    defaults={
                        "name": m_name,
                        "gender": "MALE",
                        "mobile": m_mobile,
                        "designation": m_desgn,
                        "is_frozen": True,
                        "uniform_size": "40"
                    }
                )
                if not l_created:
                    l_obj.designation = m_desgn or l_obj.designation
                    l_obj.mobile = m_mobile or l_obj.mobile
                    l_obj.is_frozen = True
                    l_obj.save()
                saved_leaders += 1

            # 2. Female Teacher (Guide Captain or Flock Leader) - only for Co-ed, Girls, Primary
            if s_type != SchoolType.BOYS_HIGH and is_valid_teacher(data['ft']):
                f_name = str(data['ft']).strip()
                f_mobile = data['fmob']
                f_desgn = data['fdes']
                f_role = LeaderRole.FLOCK_LEADER if s_type in [SchoolType.PRIMARY, SchoolType.UPPER_PRIMARY] else LeaderRole.GUIDE_CAPTAIN
                l_obj, l_created = UnitLeader.objects.get_or_create(
                    school=school,
                    role=f_role,
                    defaults={
                        "name": f_name,
                        "gender": "FEMALE",
                        "mobile": f_mobile,
                        "designation": f_desgn,
                        "is_frozen": True,
                        "uniform_size": "38"
                    }
                )
                if not l_created:
                    l_obj.designation = f_desgn or l_obj.designation
                    l_obj.mobile = f_mobile or l_obj.mobile
                    l_obj.is_frozen = True
                    l_obj.save()
                saved_leaders += 1

        total_sanctioned = School.objects.filter(is_sanctioned=True).count()
        total_mandals = Mandal.objects.count()
        total_students = Student.objects.count()
        total_leaders = UnitLeader.objects.count()

        self.stdout.write(self.style.SUCCESS(
            f"\n[IMPORT COMPLETE]\n"
            f"- Total Officially Sanctioned Schools: {total_sanctioned}\n"
            f"- Total Mandals Covered: {total_mandals}\n"
            f"- Total Designated Unit Leaders: {total_leaders}\n"
            f"- Enrolled Students Preserved: {total_students}"
        ))

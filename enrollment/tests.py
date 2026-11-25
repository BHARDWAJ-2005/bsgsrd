import io
from decimal import Decimal
from django.test import TestCase, Client, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from django.urls import reverse
from PIL import Image
import tempfile
import shutil
from .models import District, Mandal, School, Student, UnitLeader, SchoolType, StudentDetailLevel, LeaderRole, AuditLog, Circular, GalleryPhoto
from .excel_handler import generate_school_excel_template, import_students_from_excel, export_school_excel
from .pdf_generator import generate_school_pdf_report
import openpyxl

class BSGPlatformTests(TestCase):
    def setUp(self):
        # District & Mandal
        self.district = District.objects.create(name="Sangareddy", code="SRD")
        self.mandal = Mandal.objects.create(district=self.district, name="Sangareddy", code="SRD01")

        # Co-ed High School
        self.user_coed = User.objects.create_user(username="36170100101", password="BSG@Sangareddy2026")
        self.coed_school = School.objects.create(
            udise_code="36170100101",
            name="ZPHS Sangareddy Main",
            mandal=self.mandal,
            school_type=SchoolType.COED_HIGH,
            boys_quota=2, # small quota to test quota enforcement
            girls_quota=2,
            user=self.user_coed,
            must_change_password=False,
            contact_mobile="9848011223"
        )

        # Boys High School
        self.user_boys = User.objects.create_user(username="36170100102", password="BSG@Sangareddy2026")
        self.boys_school = School.objects.create(
            udise_code="36170100102",
            name="ZPHS Boys Sangareddy",
            mandal=self.mandal,
            school_type=SchoolType.BOYS_HIGH,
            boys_quota=5,
            girls_quota=0,
            user=self.user_boys,
            must_change_password=False,
            contact_mobile="9848099887"
        )

        # Admin user
        self.admin_user = User.objects.create_superuser(
            username="admin",
            password="Admin@Sangareddy2026",
            email="admin@srd.gov.in"
        )

        self.client = Client()

    def test_cascading_dropdown_api(self):
        """Verify that API returns only sanctioned schools for a given mandal."""
        # Create an unsanctioned school
        School.objects.create(
            udise_code="36170100999",
            name="Unsanctioned Private School",
            mandal=self.mandal,
            school_type=SchoolType.COED_HIGH,
            is_sanctioned=False
        )

        response = self.client.get(reverse('api_schools_by_mandal'), {'mandal_id': self.mandal.id})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['schools']), 2) # only 2 sanctioned, not 3
        udises = [s['udise_code'] for s in data['schools']]
        self.assertIn("36170100101", udises)
        self.assertNotIn("36170100999", udises)

    def test_admin_only_can_add_sanctioned_school(self):
        """Verify only district admin can add a sanctioned school."""
        # Non-admin attempts to add school
        res_unauth = self.client.post(reverse('district_add_school'), {
            'udise_code': '36162599999',
            'name': 'Unauthorized New School',
            'mandal_id': self.mandal.id,
            'boys_quota': 32,
            'girls_quota': 32
        })
        self.assertNotEqual(res_unauth.status_code, 200) # redirected to login

        # Admin logs in and sanctions school
        self.client.login(username="admin", password="Admin@Sangareddy2026")
        res_admin = self.client.post(reverse('district_add_school'), {
            'udise_code': '36162599999',
            'name': 'ZPHS Newly Sanctioned School',
            'mandal_id': self.mandal.id,
            'school_type': 'COED_HIGH',
            'sanction_order_number': 'BSG/SRD/SANCTION/2026/NEW',
            'headmaster_name': 'S. Venkat Rao',
            'boys_quota': 32,
            'girls_quota': 32,
            'male_teacher_name': 'M. Ramesh',
            'male_teacher_mobile': '9848011223',
            'female_teacher_name': 'K. Sunitha',
            'female_teacher_mobile': '9848044556'
        })
        self.assertEqual(res_admin.status_code, 302) # redirect back to district dashboard

        # Verify school was created and marked sanctioned
        new_sch = School.objects.get(udise_code='36162599999')
        self.assertTrue(new_sch.is_sanctioned)
        self.assertEqual(new_sch.name, 'ZPHS Newly Sanctioned School')
        self.assertEqual(new_sch.unit_leaders.count(), 2)
        # Verify user account was auto-generated
        self.assertTrue(User.objects.filter(username='36162599999').exists())

    def test_live_stats_api(self):
        """Verify real-time live stats endpoint."""
        response = self.client.get(reverse('api_live_stats'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['mandals_count'], 1)
        self.assertEqual(data['schools_count'], 2)

    def test_bilingual_help_page(self):
        """Verify bilingual English and Telugu toggle."""
        # English
        res_en = self.client.get(reverse('help') + '?lang=en')
        self.assertEqual(res_en.status_code, 200)
        self.assertContains(res_en, "How to Use & FAQ")

        # Telugu
        res_te = self.client.get(reverse('help') + '?lang=te')
        self.assertEqual(res_te.status_code, 200)
        self.assertContains(res_te, "సహాయం")

    def test_quota_enforcement(self):
        """Strict test that school quota cannot be exceeded."""
        self.client.login(username="36170100101", password="BSG@Sangareddy2026")

        # Enroll Boy 1 (Quota is 2)
        res1 = self.client.post(reverse('enroll_student'), {
            'gender': 'BOY',
            'name': 'Rahul',
            'father_name': 'Ramesh',
            'class_level': 8,
            'height_cm': '145.0',
            'uniform_size': '30',
            'shoe_size': '6',
            'detail_level': 'SHORT'
        })
        self.assertEqual(res1.status_code, 200)
        self.assertTrue(res1.json()['success'])

        # Enroll Boy 2 (Reaches Quota 2)
        res2 = self.client.post(reverse('enroll_student'), {
            'gender': 'BOY',
            'name': 'Adil',
            'father_name': 'Rahim',
            'class_level': 8,
            'height_cm': '146.0',
            'uniform_size': '32',
            'shoe_size': '6',
            'detail_level': 'SHORT'
        })
        self.assertEqual(res2.status_code, 200)
        self.assertTrue(res2.json()['success'])

        # Enroll Boy 3 (Should be REJECTED because quota is full)
        res3 = self.client.post(reverse('enroll_student'), {
            'gender': 'BOY',
            'name': 'Karthik',
            'father_name': 'Suresh',
            'class_level': 8,
            'height_cm': '147.0',
            'uniform_size': '30',
            'shoe_size': '6',
            'detail_level': 'SHORT'
        })
        self.assertEqual(res3.status_code, 400)
        self.assertFalse(res3.json()['success'])
        self.assertIn("Quota is Full", res3.json()['message'])

    def test_school_type_restriction(self):
        """Verify Boys High School cannot enroll Girls."""
        self.client.login(username="36170100102", password="BSG@Sangareddy2026")
        res = self.client.post(reverse('enroll_student'), {
            'gender': 'GIRL',
            'name': 'Sneha',
            'father_name': 'Srinivas',
            'class_level': 8,
            'height_cm': '145.0',
            'uniform_size': '30',
            'shoe_size': '5',
            'detail_level': 'SHORT'
        })
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json()['success'])

    def test_excel_template_generation(self):
        """Verify that openpyxl generates template with sheets and data validation."""
        template_io = generate_school_excel_template(self.coed_school)
        self.assertGreater(len(template_io.getvalue()), 1000)

        wb = openpyxl.load_workbook(template_io)
        self.assertIn('Boys Enrollment', wb.sheetnames)
        self.assertIn('Girls Enrollment', wb.sheetnames)

    def test_excel_export_and_sizing_summary(self):
        """Verify export contains all sheets including uniform ordering summary."""
        # Add 1 boy
        Student.objects.create(
            school=self.coed_school,
            gender='BOY',
            name='Test Boy',
            father_name='Father',
            class_level=8,
            height_cm=Decimal('150.0'),
            uniform_size='32',
            shoe_size='6'
        )
        export_io = export_school_excel(self.coed_school)
        self.assertGreater(len(export_io.getvalue()), 1000)

        wb = openpyxl.load_workbook(export_io)
        self.assertIn('School Overview', wb.sheetnames)
        self.assertIn('Uniform Sizing Summary', wb.sheetnames)

    def test_pdf_report_generation(self):
        """Verify ReportLab compiles official PDF report without errors."""
        Student.objects.create(
            school=self.coed_school,
            gender='BOY',
            name='Test Boy',
            father_name='Father',
            class_level=8,
            height_cm=Decimal('150.0'),
            uniform_size='32',
            shoe_size='6',
            detail_level=StudentDetailLevel.BRIEF,
            chest=Decimal('30.5'),
            waist=Decimal('26.0')
        )
        pdf_io = generate_school_pdf_report(self.coed_school)
        content = pdf_io.getvalue()
        self.assertGreater(len(content), 1000)
        self.assertTrue(content.startswith(b"%PDF"))

    def test_school_category_quotas_and_leader_rules(self):
        """Verify quota allocations and leader rules across school categories."""
        # 1. Co-ed High School defaults
        coed = School(school_type=SchoolType.COED_HIGH)
        self.assertEqual(coed.boys_quota, 16)
        self.assertEqual(coed.girls_quota, 16)
        self.assertEqual(coed.max_leaders_count(), 2)

        # 2. Girls High School
        girls_sch = School.objects.create(
            udise_code="36170100103",
            name="ZPHS Girls Sangareddy",
            mandal=self.mandal,
            school_type=SchoolType.GIRLS_HIGH,
            boys_quota=0,
            girls_quota=32
        )
        self.assertEqual(girls_sch.allowed_genders(), ['GIRL'])
        self.assertEqual(girls_sch.max_leaders_count(), 1)

        # 3. Boys High School
        self.assertEqual(self.boys_school.allowed_genders(), ['BOY'])
        self.assertEqual(self.boys_school.max_leaders_count(), 1)

        # 4. Primary School
        pri_sch = School.objects.create(
            udise_code="36170100104",
            name="MPPS Sangareddy",
            mandal=self.mandal,
            school_type=SchoolType.PRIMARY,
            boys_quota=12,
            girls_quota=12
        )
        self.assertEqual(pri_sch.boys_quota, 12)
        self.assertEqual(pri_sch.girls_quota, 12)
        self.assertEqual(pri_sch.max_leaders_count(), 2)

    def test_unit_leader_measurements_workflow(self):
        """Verify updating unit leader uniform size and tailoring measurements."""
        # Create leader
        leader = UnitLeader.objects.create(
            school=self.coed_school,
            role="SCOUT_MASTER",
            name="K. Satyanarayana",
            gender="MALE",
            mobile="9848011223"
        )

        # Admin login and update measurements
        self.client.login(username="admin", password="Admin@Sangareddy2026")
        res = self.client.post(reverse('update_leader_measurements', kwargs={'leader_id': leader.id}), {
            'uniform_size': '42',
            'shoe_size': '8',
            'height_cm': '168.0',
            'chest_bust': '38.5',
            'waist': '32.0',
            'neck': '16.0',
            'shoulder': '18.0',
            'sleeve': '24.0',
            'top_length': '29.5',
            'bottom_length': '40.0',
            'hip': '38.0'
        })
        self.assertEqual(res.status_code, 302)

        leader.refresh_from_db()
        self.assertEqual(leader.uniform_size, '42')
        self.assertEqual(leader.shoe_size, '8')
        self.assertEqual(leader.height_cm, Decimal('168.0'))
        self.assertEqual(leader.chest_bust, Decimal('38.5'))
        self.assertEqual(leader.waist, Decimal('32.0'))
        self.assertEqual(leader.neck, Decimal('16.0'))
        self.assertEqual(leader.shoulder, Decimal('18.0'))
        self.assertEqual(leader.sleeve, Decimal('24.0'))
        self.assertEqual(leader.top_length, Decimal('29.5'))
        self.assertEqual(leader.bottom_length, Decimal('40.0'))

        # Verify Excel and PDF include leader measurements
        wb = openpyxl.load_workbook(export_school_excel(self.coed_school))
        self.assertIn('Unit Leaders', wb.sheetnames)
        ws = wb['Unit Leaders']
        # Row 2 should contain leader info and measurements
        self.assertEqual(ws.cell(row=2, column=2).value, "K. Satyanarayana")
        self.assertEqual(ws.cell(row=2, column=8).value, "42")
        self.assertEqual(ws.cell(row=2, column=9).value, "8")

        pdf_bytes = generate_school_pdf_report(self.coed_school).getvalue()
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

    def test_school_and_admin_unit_leader_edit_permissions(self):
        """Verify that both school users and district admin can edit unit leader info and sizing."""
        # Leader in Co-ed School
        coed_leader = UnitLeader.objects.create(
            school=self.coed_school,
            role="SCOUT_MASTER",
            name="Teacher A",
            gender="MALE",
            mobile="9848011111",
            designation="Teacher"
        )
        # Leader in Boys School
        boys_leader = UnitLeader.objects.create(
            school=self.boys_school,
            role="SCOUT_MASTER",
            name="Teacher B",
            gender="MALE",
            mobile="9848022222",
            designation="Teacher"
        )

        # 1. School user logs in and updates their own leader
        self.client.login(username="36170100101", password="BSG@Sangareddy2026")
        res_school = self.client.post(reverse('save_leader'), {
            'school_id': self.coed_school.id,
            'leader_id': coed_leader.id,
            'role': 'SCOUT_MASTER',
            'name': 'K. Satyanarayana Sastry',
            'gender': 'MALE',
            'designation': 'School Assistant (Maths)',
            'mobile': '9848099887',
            'email': 'sastry@bsg.org',
            'uniform_size': '42',
            'shoe_size': '8',
            'height_cm': '170.0',
            'chest_bust': '39.0',
            'waist': '33.0',
            'shoulder': '18.5',
            'neck': '16.0',
            'sleeve': '24.5',
            'top_length': '30.0',
            'bottom_length': '40.5'
        })
        self.assertEqual(res_school.status_code, 302)
        self.assertRedirects(res_school, reverse('school_dashboard'))

        coed_leader.refresh_from_db()
        self.assertEqual(coed_leader.name, 'K. Satyanarayana Sastry')
        self.assertEqual(coed_leader.designation, 'School Assistant (Maths)')
        self.assertEqual(coed_leader.mobile, '9848099887')
        self.assertEqual(coed_leader.uniform_size, '42')
        self.assertEqual(coed_leader.shoe_size, '8')

        # 2. School user attempts to edit another school's leader -> should be 404
        res_unauth = self.client.post(reverse('save_leader'), {
            'school_id': self.boys_school.id,
            'leader_id': boys_leader.id,
            'name': 'Hacked Teacher Name'
        })
        self.assertEqual(res_unauth.status_code, 404)

        # 3. District Admin logs in and edits the leader
        self.client.login(username="admin", password="Admin@Sangareddy2026")
        res_admin = self.client.post(reverse('save_leader'), {
            'school_id': self.coed_school.id,
            'leader_id': coed_leader.id,
            'role': 'SCOUT_MASTER',
            'name': 'K. Satyanarayana Sastry (Verified)',
            'gender': 'MALE',
            'designation': 'Senior SA (Maths)',
            'mobile': '9848099887',
            'uniform_size': '44',
            'shoe_size': '9'
        })
        self.assertEqual(res_admin.status_code, 302)
        self.assertRedirects(res_admin, reverse('district_dashboard'))

        coed_leader.refresh_from_db()
        self.assertEqual(coed_leader.name, 'K. Satyanarayana Sastry (Verified)')
        self.assertEqual(coed_leader.uniform_size, '44')

    def test_forgot_password_flow(self):
        """Test self-service password recovery with mobile verification."""
        # Attach a contact mobile to coed school and create a unit leader with mobile
        self.coed_school.contact_mobile = "9848011223"
        self.coed_school.save()

        # 1. Verification with incorrect mobile -> fails
        res_fail = self.client.post(reverse('forgot_password'), {
            'mandal_id': self.mandal.id,
            'udise_code': self.coed_school.udise_code,
            'verification_mobile': '9999999999',
            'reset_type': 'custom',
            'new_password': 'NewPassword@2026',
            'confirm_password': 'NewPassword@2026'
        })
        self.assertEqual(res_fail.status_code, 200) # Re-renders forgot_password with error message
        self.user_coed.refresh_from_db()
        self.assertTrue(self.user_coed.check_password("BSG@Sangareddy2026")) # Not changed

        # 2. Verification with correct mobile & custom password -> succeeds
        res_success = self.client.post(reverse('forgot_password'), {
            'mandal_id': self.mandal.id,
            'udise_code': self.coed_school.udise_code,
            'verification_mobile': '9848011223',
            'reset_type': 'custom',
            'new_password': 'NewSecurePassword@2026',
            'confirm_password': 'NewSecurePassword@2026'
        })
        self.assertEqual(res_success.status_code, 302)
        self.assertRedirects(res_success, reverse('login'))

        self.user_coed.refresh_from_db()
        self.assertTrue(self.user_coed.check_password("NewSecurePassword@2026"))

        # 3. Test default password reset
        res_default = self.client.post(reverse('forgot_password'), {
            'mandal_id': self.mandal.id,
            'udise_code': self.coed_school.udise_code,
            'verification_mobile': '9848011223',
            'reset_type': 'default'
        })
        self.assertEqual(res_default.status_code, 302)
        self.user_coed.refresh_from_db()
        self.assertTrue(self.user_coed.check_password("BSG@Sangareddy2026"))

    def test_admin_change_school_password(self):
        """Test District Admin's ability to update passwords for any school."""
        # Non-admin attempts -> redirected to login
        res_unauth = self.client.post(
            reverse('district_reset_school_password', kwargs={'udise_code': self.boys_school.udise_code}),
            {'new_password': 'HackedPassword123!'}
        )
        self.assertNotEqual(res_unauth.status_code, 200)

        # Admin logs in
        self.client.login(username="admin", password="Admin@Sangareddy2026")

        # 1. Reset via standard URL
        res_admin = self.client.post(
            reverse('district_reset_school_password', kwargs={'udise_code': self.boys_school.udise_code}),
            {'new_password': 'AdminAssigned@2026', 'must_change_password': '1'}
        )
        self.assertEqual(res_admin.status_code, 302)
        self.boys_school.user.refresh_from_db()
        self.assertTrue(self.boys_school.user.check_password('AdminAssigned@2026'))
        self.boys_school.refresh_from_db()
        self.assertTrue(self.boys_school.must_change_password)

        # 2. Reset via generic toolbar endpoint
        res_generic = self.client.post(
            reverse('district_reset_school_password_generic'),
            {'udise_code': self.coed_school.udise_code, 'new_password': 'GenericPassword@999', 'must_change_password': '1'}
        )
        self.assertEqual(res_generic.status_code, 302)
        self.coed_school.user.refresh_from_db()
        self.assertTrue(self.coed_school.user.check_password('GenericPassword@999'))

    def test_mandatory_contact_when_no_mobile_numbers(self):
        """
        Verify that if a school has no mobile numbers on file:
        1. Accessing dashboard redirects to change_password.
        2. Changing password without providing HM/Unit Leader mobile is rejected.
        3. Providing HM or Unit Leader mobile unlocks dashboard and registers recovery number.
        """
        # Create school without any mobile numbers
        user_nomob = User.objects.create_user(username="36170100999", password="BSG@Sangareddy2026")
        school_nomob = School.objects.create(
            udise_code="36170100999",
            name="GPS Without Mobile",
            mandal=self.mandal,
            school_type=SchoolType.PRIMARY,
            boys_quota=12,
            girls_quota=12,
            user=user_nomob,
            must_change_password=True,
            contact_mobile=""
        )
        leader = UnitLeader.objects.create(
            school=school_nomob,
            name="P. Ramesh",
            role=LeaderRole.CUB_MASTER,
            gender="MALE",
            mobile=""
        )

        self.assertFalse(school_nomob.has_recovery_contact())

        # 1. School logs in
        self.client.login(username="36170100999", password="BSG@Sangareddy2026")

        # Dashboard access is intercepted by require_password_changed
        res_dash = self.client.get(reverse('school_dashboard'))
        self.assertEqual(res_dash.status_code, 302)
        self.assertRedirects(res_dash, reverse('change_password'))

        # 2. Attempt to change password WITHOUT entering phone number -> fails
        res_fail = self.client.post(reverse('change_password'), {
            'new_password': 'SecurePassword@2026',
            'confirm_password': 'SecurePassword@2026',
            'hm_name': 'Headmaster Name',
            'hm_mobile': '', # blank
            f'leader_mobile_{leader.id}': '' # blank
        })
        self.assertEqual(res_fail.status_code, 200) # Re-rendered with error
        school_nomob.refresh_from_db()
        self.assertTrue(school_nomob.must_change_password) # Not completed
        self.assertFalse(school_nomob.has_recovery_contact())

        # 3. Submit valid password WITH Headmaster mobile number -> succeeds
        res_success = self.client.post(reverse('change_password'), {
            'new_password': 'SecurePassword@2026',
            'confirm_password': 'SecurePassword@2026',
            'hm_name': 'S. Venkat Rao',
            'hm_mobile': '9848011223',
            f'leader_mobile_{leader.id}': '9848044556'
        })
        self.assertEqual(res_success.status_code, 302)
        self.assertRedirects(res_success, reverse('school_dashboard'))

        # Verify database updates
        school_nomob.refresh_from_db()
        leader.refresh_from_db()
        user_nomob.refresh_from_db()

        self.assertFalse(school_nomob.must_change_password)
        self.assertTrue(school_nomob.has_recovery_contact())
        self.assertEqual(school_nomob.contact_mobile, '9848011223')
        self.assertEqual(leader.mobile, '9848044556')
        self.assertTrue(user_nomob.check_password('SecurePassword@2026'))

        # 4. Now dashboard is fully accessible
        res_dash_ok = self.client.get(reverse('school_dashboard'))
        self.assertEqual(res_dash_ok.status_code, 200)

    def test_landing_page_content_and_dignitaries(self):
        """
        Verify that the landing page renders:
        1. Official motto ('BE PREPARED') & aim.
        2. District Collector (Prateek Jain, I.A.S.).
        3. District Educational Officer (Smt. R. Rohini Garu).
        4. District Secretary & Administrator (Vancha Madhava Reddy, 9440069750).
        5. Official Instagram handle & QR code image.
        """
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'landing.html')

        content = response.content.decode('utf-8')
        # Check Motto & Aim
        self.assertIn("BE PREPARED", content)
        self.assertIn("Aim to Achieve", content)

        # Check Header Banner (containing leadership details from left corner to right corner)
        self.assertIn("bsg_header_banner.jpg", content)

        # Check Instagram & Image
        self.assertIn("scan_to_follow_photo.jpg", content)
        self.assertIn("@bsg_sangareddy", content)
        self.assertIn("https://www.instagram.com/bsg_sangareddy", content)

        # Check Official Charter Posters (Promises, Law, Songs)
        self.assertIn("bsg_scout_promise.jpg", content)
        self.assertIn("bsg_guide_promise.jpg", content)
        self.assertIn("bsg_scout_guide_law.jpg", content)
        self.assertIn("bsg_prayer_song.jpg", content)
        self.assertIn("bsg_flag_song.jpg", content)

        # Authenticated school user redirect
        self.client.login(username="36170100101", password="BSG@Sangareddy2026")
        res_auth = self.client.get(reverse('home'))
        self.assertEqual(res_auth.status_code, 302)
        self.assertRedirects(res_auth, reverse('school_dashboard'))

    def test_district_export_school_excel_view(self):
        """
        Verify District Admin can download the full school Excel workbook
        for any particular school with all enrolled students and unit leaders.
        """
        # Enroll a student and leader in the school first
        Student.objects.create(
            school=self.coed_school,
            name="Rahul Sharma",
            father_name="Ramesh Sharma",
            gender="BOY",
            class_level=8,
            dob="2012-05-15",
            height_cm=Decimal("152.5"),
            uniform_size="34",
            shoe_size="6"
        )
        UnitLeader.objects.create(
            school=self.coed_school,
            name="Srikanth Rao",
            role=LeaderRole.SCOUT_MASTER,
            mobile="9848011223",
            email="srikanth@school.edu",
            uniform_size="40"
        )

        # 1. Non-admin cannot access
        self.client.login(username="36170100101", password="BSG@Sangareddy2026")
        res_unauth = self.client.get(reverse('district_export_school_excel', kwargs={'udise_code': self.coed_school.udise_code}))
        self.assertEqual(res_unauth.status_code, 302) # Redirects to login

        # 2. District Admin can download workbook
        self.client.login(username="admin", password="Admin@Sangareddy2026")
        res_excel = self.client.get(reverse('district_export_school_excel', kwargs={'udise_code': self.coed_school.udise_code}))
        self.assertEqual(res_excel.status_code, 200)
        self.assertEqual(res_excel['Content-Type'], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        self.assertIn("BSG_Enrollment_36170100101", res_excel['Content-Disposition'])

        # Verify openpyxl can load and verify sheets
        wb = openpyxl.load_workbook(io.BytesIO(res_excel.content))
        self.assertIn("Boys Enrollment", wb.sheetnames)
        self.assertIn("Girls Enrollment", wb.sheetnames)
        self.assertIn("Unit Leaders", wb.sheetnames)
        self.assertIn("Uniform Sizing Summary", wb.sheetnames)
        self.assertIn("School Overview", wb.sheetnames)

        # Verify AuditLog created
        log = AuditLog.objects.filter(action="DISTRICT_EXPORT_SCHOOL_EXCEL", school=self.coed_school).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.user, self.admin_user)

    def test_district_export_school_excel_generic(self):
        """
        Verify generic endpoint with udise_code query parameter (from toolbar modal).
        """
        self.client.login(username="admin", password="Admin@Sangareddy2026")

        # With valid query param
        res_valid = self.client.get(reverse('district_export_school_excel_generic') + f"?udise_code={self.coed_school.udise_code}")
        self.assertEqual(res_valid.status_code, 200)
        self.assertEqual(res_valid['Content-Type'], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        # Without query param
        res_empty = self.client.get(reverse('district_export_school_excel_generic'))
        self.assertEqual(res_empty.status_code, 302)
        self.assertRedirects(res_empty, reverse('district_dashboard'))

    def test_district_export_school_pdf_view(self):
        """
        Verify District Admin can download the certified school PDF roster.
        """
        self.client.login(username="admin", password="Admin@Sangareddy2026")
        res_pdf = self.client.get(reverse('district_export_school_pdf', kwargs={'udise_code': self.coed_school.udise_code}))
        self.assertEqual(res_pdf.status_code, 200)
        self.assertEqual(res_pdf['Content-Type'], "application/pdf")
        self.assertIn("BSG_Roster_36170100101", res_pdf['Content-Disposition'])

    def test_admin_login_page_hides_credentials(self):
        """Verify login page does not pre-fill or expose default admin credentials."""
        res = self.client.get(reverse('login'))
        self.assertEqual(res.status_code, 200)
        self.assertNotContains(res, "Admin@Sangareddy2026")

    def test_admin_change_username_and_password_with_past_password(self):
        """Verify District Admin can change username & password only with valid current password."""
        self.client.login(username="admin", password="Admin@Sangareddy2026")

        # 1. Wrong current password must fail
        res_bad = self.client.post(reverse('district_admin_account'), {
            'current_password': 'WrongPassword123',
            'new_username': 'deo_sangareddy',
            'new_password': 'NewAdminPass@2027',
            'confirm_password': 'NewAdminPass@2027',
        })
        self.assertEqual(res_bad.status_code, 302)
        self.admin_user.refresh_from_db()
        self.assertEqual(self.admin_user.username, 'admin')
        self.assertTrue(self.admin_user.check_password('Admin@Sangareddy2026'))

        # 2. Correct current password updates both username and password
        res_ok = self.client.post(reverse('district_admin_account'), {
            'current_password': 'Admin@Sangareddy2026',
            'new_username': 'deo_sangareddy',
            'new_password': 'NewAdminPass@2027',
            'confirm_password': 'NewAdminPass@2027',
        })
        self.assertEqual(res_ok.status_code, 302)
        self.admin_user.refresh_from_db()
        self.assertEqual(self.admin_user.username, 'deo_sangareddy')
        self.assertTrue(self.admin_user.check_password('NewAdminPass@2027'))

        # 3. Changing password again requires the new (past) password
        res_ok2 = self.client.post(reverse('district_admin_account'), {
            'current_password': 'NewAdminPass@2027',
            'new_username': 'deo_sangareddy',
            'new_password': 'AnotherAdminPass@2028',
            'confirm_password': 'AnotherAdminPass@2028',
        })
        self.assertEqual(res_ok2.status_code, 302)
        self.admin_user.refresh_from_db()
        self.assertTrue(self.admin_user.check_password('AnotherAdminPass@2028'))

    def test_school_voluntary_change_password_requires_current(self):
        """Verify schools with must_change_password=False must provide current password to change it."""
        self.client.login(username="36170100101", password="BSG@Sangareddy2026")

        # 1. Wrong current password fails
        res_fail = self.client.post(reverse('change_password'), {
            'current_password': 'WrongPassword',
            'new_password': 'MySchoolNew@2027',
            'confirm_password': 'MySchoolNew@2027',
        })
        self.assertEqual(res_fail.status_code, 200)
        self.user_coed.refresh_from_db()
        self.assertTrue(self.user_coed.check_password('BSG@Sangareddy2026'))

        # 2. Correct current password succeeds
        res_ok = self.client.post(reverse('change_password'), {
            'current_password': 'BSG@Sangareddy2026',
            'new_password': 'MySchoolNew@2027',
            'confirm_password': 'MySchoolNew@2027',
        })
        self.assertRedirects(res_ok, reverse('school_dashboard'))
        self.user_coed.refresh_from_db()
        self.assertTrue(self.user_coed.check_password('MySchoolNew@2027'))

    def test_circular_pdf_upload_toggle_delete_and_public_landing(self):
        """Verify District Admin can publish PDF-only circulars and they appear on public landing page."""
        temp_media = tempfile.mkdtemp()
        try:
            with override_settings(
                MEDIA_ROOT=temp_media,
                USE_CLOUDINARY=False,
                STORAGES={
                    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
                },
            ):
                # 1. Non-admin cannot upload
                pdf_file = SimpleUploadedFile("notice.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF", content_type="application/pdf")
                res_unauth = self.client.post(reverse('district_upload_circular'), {
                    'title': 'Unauthorized Circular',
                    'file': pdf_file,
                })
                self.assertEqual(res_unauth.status_code, 302)
                self.assertEqual(Circular.objects.count(), 0)

                # 2. Admin rejects non-PDF
                self.client.login(username="admin", password="Admin@Sangareddy2026")
                bad_file = SimpleUploadedFile("image.jpg", b"not-a-pdf", content_type="image/jpeg")
                self.client.post(reverse('district_upload_circular'), {
                    'title': 'Invalid File Circular',
                    'file': bad_file,
                })
                self.assertEqual(Circular.objects.count(), 0)

                # 3. Admin uploads valid PDF
                valid_pdf = SimpleUploadedFile("guidelines_2026.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF", content_type="application/pdf")
                res_ok = self.client.post(reverse('district_upload_circular'), {
                    'title': 'District Enrollment Guidelines 2026',
                    'reference_number': 'Rc.No. BSG/SRD/2026/01',
                    'issued_date': '2026-11-25',
                    'file': valid_pdf,
                })
                self.assertRedirects(res_ok, reverse('district_dashboard'))
                self.assertEqual(Circular.objects.count(), 1)
                circular = Circular.objects.first()

                # 4. Public (logged out) sees circular on landing page
                self.client.logout()
                res_home = self.client.get(reverse('home'))
                self.assertEqual(res_home.status_code, 200)
                self.assertContains(res_home, 'District Enrollment Guidelines 2026')
                self.assertContains(res_home, 'Rc.No. BSG/SRD/2026/01')

                # 5. Admin toggles hidden -> disappears from landing page
                self.client.login(username="admin", password="Admin@Sangareddy2026")
                self.client.post(reverse('district_toggle_circular', kwargs={'circular_id': circular.id}))
                self.client.logout()
                res_home_hidden = self.client.get(reverse('home'))
                self.assertNotContains(res_home_hidden, 'District Enrollment Guidelines 2026')

                # 6. Admin deletes circular
                self.client.login(username="admin", password="Admin@Sangareddy2026")
                self.client.post(reverse('district_delete_circular', kwargs={'circular_id': circular.id}))
                self.assertEqual(Circular.objects.count(), 0)
        finally:
            shutil.rmtree(temp_media, ignore_errors=True)

    def test_gallery_photos_grouped_by_event_and_public_landing(self):
        """Verify District Admin can upload event photos and public landing groups them by event name."""
        temp_media = tempfile.mkdtemp()
        try:
            with override_settings(
                MEDIA_ROOT=temp_media,
                USE_CLOUDINARY=False,
                STORAGES={
                    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
                },
            ):
                def make_test_image(name):
                    buf = io.BytesIO()
                    Image.new('RGB', (100, 80), color='blue').save(buf, format='JPEG')
                    buf.seek(0)
                    return SimpleUploadedFile(name, buf.read(), content_type='image/jpeg')

                self.client.login(username="admin", password="Admin@Sangareddy2026")
                res_upload = self.client.post(reverse('district_upload_gallery_photos'), {
                    'event_name': 'District Rally 2026',
                    'event_date': '2026-11-20',
                    'title': 'March Past',
                    'photos': [make_test_image('rally1.jpg'), make_test_image('rally2.jpg')],
                })
                self.assertRedirects(res_upload, reverse('district_dashboard'))
                self.assertEqual(GalleryPhoto.objects.count(), 2)

                # Public (logged out) sees event group & photos on landing page
                self.client.logout()
                res_home = self.client.get(reverse('home'))
                self.assertEqual(res_home.status_code, 200)
                self.assertContains(res_home, 'District Rally 2026')
                self.assertContains(res_home, '2 photos')

                # Admin toggles & deletes one photo
                photo = GalleryPhoto.objects.first()
                self.client.login(username="admin", password="Admin@Sangareddy2026")
                self.client.post(reverse('district_toggle_gallery_photo', kwargs={'photo_id': photo.id}))
                photo.refresh_from_db()
                self.assertFalse(photo.is_active)

                self.client.post(reverse('district_delete_gallery_photo', kwargs={'photo_id': photo.id}))
                self.assertEqual(GalleryPhoto.objects.count(), 1)
        finally:
            shutil.rmtree(temp_media, ignore_errors=True)


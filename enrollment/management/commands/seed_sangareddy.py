from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from decimal import Decimal
from enrollment.models import (
    District, Mandal, School, Student, UnitLeader, DistrictNotice,
    SchoolType, StudentDetailLevel, LeaderRole
)

class Command(BaseCommand):
    help = "Seeds Sangareddy district mandals, 195+ schools, accounts, unit leaders, and sample enrollment data."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Starting Sangareddy BSG data seed..."))

        # 1. District
        district, _ = District.objects.get_or_create(
            name="Sangareddy",
            defaults={"code": "SRD"}
        )

        # 2. Mandals in Sangareddy
        mandal_names = [
            "Sangareddy", "Patancheru", "Ramchandrapuram", "Ameenpur", "Zaheerabad",
            "Narayankhed", "Andole-Jogipet", "Kandi", "Kondapur", "Sadasivpet",
            "Gummadidala", "Jinnaram", "Hathnoora", "Pulkal", "Munipally",
            "Kohir", "Mogudampally", "Nyalkal", "Raikode", "Kangti",
            "Kalher", "Sirgapoor", "Manoor", "Nagalgidda", "Vatpally",
            "Chowtakur", "Manoor Rural"
        ]

        mandals_dict = {}
        for idx, m_name in enumerate(mandal_names, start=1):
            m_code = f"SRD{idx:02d}"
            mandal, _ = Mandal.objects.get_or_create(
                district=district,
                name=m_name,
                defaults={"code": m_code}
            )
            mandals_dict[m_name] = mandal

        # 3. Superuser / District Admin
        admin_user, created = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "deo-sangareddy@telangana.gov.in",
                "is_staff": True,
                "is_superuser": True,
                "first_name": "District",
                "last_name": "Coordinator"
            }
        )
        if created or not admin_user.check_password("Admin@Sangareddy2026"):
            admin_user.set_password("Admin@Sangareddy2026")
            admin_user.save()
            self.stdout.write(self.style.SUCCESS("Created / updated District Admin ('admin' / 'Admin@Sangareddy2026')"))

        # 4. Generate 195 realistic schools across Sangareddy mandals
        school_name_templates = [
            ("ZPHS {mandal} Main", SchoolType.COED_HIGH, 32, 32),
            ("ZPHS Boys {mandal}", SchoolType.BOYS_HIGH, 32, 0),
            ("KGBV Girls School {mandal}", SchoolType.GIRLS_HIGH, 0, 32),
            ("TSMS Model School {mandal}", SchoolType.COED_HIGH, 32, 32),
            ("MPPS Primary {mandal} Colony", SchoolType.PRIMARY, 24, 24),
            ("MPUPS Upper Primary {mandal} South", SchoolType.UPPER_PRIMARY, 24, 24),
            ("ZPHS {mandal} North", SchoolType.COED_HIGH, 32, 32),
            ("MPPS Primary {mandal} Village", SchoolType.PRIMARY, 24, 24),
        ]

        total_schools_created = 0
        school_udise_counter = 36170100101

        all_created_schools = []

        for m_idx, (m_name, m_obj) in enumerate(mandals_dict.items(), start=1):
            # ~7-8 schools per mandal to reach 195 schools
            num_schools_for_mandal = 8 if m_idx <= 12 else 7
            for s_idx in range(num_schools_for_mandal):
                tmpl_name, s_type, b_quota, g_quota = school_name_templates[s_idx % len(school_name_templates)]
                sch_name = tmpl_name.format(mandal=m_name)
                udise = str(school_udise_counter)
                school_udise_counter += 1

                # Create Django auth user for the school
                sch_user, u_created = User.objects.get_or_create(
                    username=udise,
                    defaults={
                        "first_name": sch_name[:30],
                        "email": f"school{udise}@bsg.sangareddy.org"
                    }
                )
                sch_user.set_password("BSG@Sangareddy2026")
                sch_user.save()

                school, s_created = School.objects.get_or_create(
                    udise_code=udise,
                    defaults={
                        "name": sch_name,
                        "mandal": m_obj,
                        "school_type": s_type,
                        "boys_quota": b_quota,
                        "girls_quota": g_quota,
                        "user": sch_user,
                        "must_change_password": True,
                        "default_password": "BSG@Sangareddy2026",
                        "contact_person": f"Headmaster {m_name}",
                        "contact_mobile": f"9440{m_idx:02d}{s_idx:04d}"
                    }
                )
                if s_created:
                    total_schools_created += 1
                all_created_schools.append(school)

        self.stdout.write(self.style.SUCCESS(f"Total schools in database: {School.objects.count()} (across {Mandal.objects.count()} mandals)."))

        # 5. Populate Sample Data in first two demonstration schools
        # School 1: ZPHS Sangareddy Main (Co-ed High)
        demo_school_1 = School.objects.filter(name__icontains="Sangareddy Main").first()
        if demo_school_1 and demo_school_1.students.count() == 0:
            self.stdout.write(self.style.NOTICE(f"Seeding sample students and leaders for {demo_school_1.name}..."))
            demo_school_1.must_change_password = False
            demo_school_1.save()

            # Unit Leaders
            UnitLeader.objects.get_or_create(
                school=demo_school_1,
                role=LeaderRole.SCOUT_MASTER,
                defaults={
                    "name": "K. Srinivas Rao",
                    "gender": "MALE",
                    "mobile": "9848123456",
                    "email": "srinivas.scout@sangareddy.org",
                    "uniform_size": "40",
                    "chest_bust": Decimal("40.0"),
                    "waist": Decimal("34.0"),
                    "shoulder": Decimal("18.0"),
                }
            )
            UnitLeader.objects.get_or_create(
                school=demo_school_1,
                role=LeaderRole.GUIDE_CAPTAIN,
                defaults={
                    "name": "P. Lakshmi Devi",
                    "gender": "FEMALE",
                    "mobile": "9848654321",
                    "email": "lakshmi.guide@sangareddy.org",
                    "uniform_size": "38",
                    "chest_bust": Decimal("36.0"),
                    "waist": Decimal("32.0"),
                    "shoulder": Decimal("16.5"),
                }
            )

            # Sample Boys (Mix of BRIEF and SHORT)
            sample_boys = [
                ("Mohammed Adil", "M. Rahim", 8, "148.0", "32", "6", StudentDetailLevel.BRIEF, "2012-05-14", "9849001122", {"chest": Decimal("30.0"), "waist": Decimal("26.5"), "neck": Decimal("13.0"), "shoulder": Decimal("14.5"), "sleeve": Decimal("20.0"), "shirt_length": Decimal("24.0"), "pant_length": Decimal("34.5")}),
                ("V. Rahul Reddy", "V. Venkat Reddy", 9, "155.5", "34", "7", StudentDetailLevel.BRIEF, "2011-08-20", "9849001133", {"chest": Decimal("32.0"), "waist": Decimal("28.0"), "neck": Decimal("13.5"), "shoulder": Decimal("15.0"), "sleeve": Decimal("21.5"), "shirt_length": Decimal("25.5"), "pant_length": Decimal("36.0")}),
                ("B. Sai Teja", "B. Mallesh", 8, "144.0", "30", "5", StudentDetailLevel.SHORT, None, None, {}),
                ("K. Karthik", "K. Chandraiah", 7, "138.5", "28", "5", StudentDetailLevel.SHORT, None, None, {}),
                ("Syed Farhan", "Syed Imran", 7, "141.0", "30", "6", StudentDetailLevel.BRIEF, "2013-03-10", "9849001144", {"chest": Decimal("28.5"), "waist": Decimal("25.0"), "neck": Decimal("12.5"), "shoulder": Decimal("14.0"), "sleeve": Decimal("19.0"), "shirt_length": Decimal("23.0"), "pant_length": Decimal("32.0")}),
                ("A. Naveen Kumar", "A. Shankar", 6, "134.0", "28", "4", StudentDetailLevel.SHORT, None, None, {}),
            ]

            for b_name, f_name, cls, ht, sz, shoe, mode, dob, mob, meas in sample_boys:
                Student.objects.create(
                    school=demo_school_1,
                    gender="BOY",
                    name=b_name,
                    father_name=f_name,
                    class_level=cls,
                    height_cm=Decimal(ht),
                    uniform_size=sz,
                    shoe_size=shoe,
                    detail_level=mode,
                    dob=dob,
                    parent_mobile=mob,
                    **meas
                )

            # Sample Girls
            sample_girls = [
                ("K. Sneha", "K. Narayana", 9, "152.0", "32", "5", StudentDetailLevel.BRIEF, "2011-11-05", "9849002211", {"bust": Decimal("31.0"), "waist": Decimal("26.0"), "hip": Decimal("33.0"), "shoulder": Decimal("14.0"), "sleeve": Decimal("18.5"), "kameez_length": Decimal("35.0"), "salwar_length": Decimal("34.0")}),
                ("G. Anusha", "G. Krishna", 8, "146.5", "30", "5", StudentDetailLevel.BRIEF, "2012-07-18", "9849002222", {"bust": Decimal("29.5"), "waist": Decimal("25.0"), "hip": Decimal("31.5"), "shoulder": Decimal("13.5"), "sleeve": Decimal("17.5"), "kameez_length": Decimal("33.5"), "salwar_length": Decimal("32.0")}),
                ("R. Divya", "R. Swamy", 7, "139.0", "28", "4", StudentDetailLevel.SHORT, None, None, {}),
                ("Fatima Begum", "Abdul Karim", 7, "142.0", "30", "4", StudentDetailLevel.SHORT, None, None, {}),
                ("T. Swathi", "T. Ramesh", 6, "135.0", "28", "4", StudentDetailLevel.BRIEF, "2014-01-22", "9849002233", {"bust": Decimal("27.5"), "waist": Decimal("24.0"), "hip": Decimal("29.0"), "shoulder": Decimal("13.0"), "sleeve": Decimal("16.0"), "kameez_length": Decimal("31.0"), "salwar_length": Decimal("29.5")}),
            ]

            for g_name, f_name, cls, ht, sz, shoe, mode, dob, mob, meas in sample_girls:
                Student.objects.create(
                    school=demo_school_1,
                    gender="GIRL",
                    name=g_name,
                    father_name=f_name,
                    class_level=cls,
                    height_cm=Decimal(ht),
                    uniform_size=sz,
                    shoe_size=shoe,
                    detail_level=mode,
                    dob=dob,
                    parent_mobile=mob,
                    **meas
                )

        # 6. Sample District Notices
        DistrictNotice.objects.get_or_create(
            title="BSG Annual Sangareddy District Enrollment Drive 2026-27 is LIVE",
            defaults={
                "title_te": "BSG వార్షిక సంగారెడ్డి జిల్లా నమోదు డ్రైవ్ 2026-27 ప్రారంభించబడింది",
                "content": "All recognized High Schools, KGBVs, Model Schools and Primary Schools in Sangareddy district must complete student measurements and leader submissions by the deadline. Contact the DEO / District BSG headquarters for any quota adjustments.",
                "content_te": "సంగారెడ్డి జిల్లాలోని అన్ని గుర్తింపు పొందిన ఉన్నత పాఠశాలలు, కేజీబీవీలు, మోడల్ స్కూల్స్ మరియు ప్రాథమిక పాఠశాలలు నిర్దేశిత గడువులోగా విద్యార్థుల కొలతలు మరియు నాయకుల వివరాలను నమోదు చేయాలి.",
                "is_active": True
            }
        )

        self.stdout.write(self.style.SUCCESS("Sangareddy District BSG Portal initialized successfully!"))

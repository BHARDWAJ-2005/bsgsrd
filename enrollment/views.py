import json
import os
from decimal import Decimal
from datetime import datetime
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET
from django.core.exceptions import ValidationError

from .models import (
    Mandal, School, Student, UnitLeader, AuditLog, DistrictNotice,
    Circular, GalleryPhoto,
    SchoolType, StudentDetailLevel, LeaderRole
)
from .excel_handler import (
    generate_school_excel_template, import_students_from_excel,
    export_school_excel, export_district_consolidated_excel
)
from .pdf_generator import generate_school_pdf_report
from .translations import MESSAGES, get_translation


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def is_district_admin_check(user):
    return user.is_authenticated and (user.is_superuser or user.is_staff)


def require_password_changed(view_func):
    """
    Decorator for school-only views.
    If the school's must_change_password flag is still True,
    or if the school has no recovery mobile numbers on file,
    redirects them to the change-password page before allowing access.
    Admin/staff users are always passed through.
    """
    from functools import wraps
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if request.user.is_authenticated and not (request.user.is_superuser or request.user.is_staff):
            school = getattr(request.user, 'school_profile', None)
            if school:
                if school.must_change_password:
                    messages.warning(
                        request,
                        "🔒 Security Notice: You must set a new password before accessing your school dashboard."
                    )
                    return redirect('change_password')
                elif not school.has_recovery_contact():
                    messages.warning(
                        request,
                        "📱 Mandatory Contact Required: Your school currently has no phone numbers on file. "
                        "Please register the Headmaster's or Unit Leader's mobile number to enable password recovery."
                    )
                    return redirect('change_password')
        return view_func(request, *args, **kwargs)
    return _wrapped


# ==========================================
# PUBLIC & AUTHENTICATION VIEWS
# ==========================================

def home_view(request):
    """
    Public Landing Page showcasing the Bharat Scouts & Guides motto,
    aim to achieve, official circulars, event photo gallery,
    Instagram official social handle & QR code, and institutional gateways.
    """
    if request.user.is_authenticated and request.GET.get('public') != '1':
        if request.user.is_superuser or request.user.is_staff:
            return redirect('district_dashboard')
        elif hasattr(request.user, 'school_profile'):
            return redirect('school_dashboard')

    mandals = Mandal.objects.filter(schools__is_sanctioned=True).distinct().order_by('name')
    circulars = Circular.objects.filter(is_active=True)[:20]

    gallery_events = []
    events_map = {}
    for gp in GalleryPhoto.objects.filter(is_active=True):
        key = (gp.event_name or '').strip() or 'District Events'
        if key not in events_map:
            events_map[key] = {
                'event_name': key,
                'event_date': gp.event_date,
                'photos': [],
            }
            gallery_events.append(events_map[key])
        events_map[key]['photos'].append(gp)

    return render(request, 'landing.html', {
        'mandals': mandals,
        'circulars': circulars,
        'gallery_events': gallery_events,
    })


def login_view(request):
    """
    Login page with cascading dropdowns: Mandal -> School (UDISE).
    Default password pre-filled or easily accessible.
    """
    if request.user.is_authenticated:
        if request.user.is_superuser or request.user.is_staff:
            return redirect('district_dashboard')
        elif hasattr(request.user, 'school_profile'):
            return redirect('school_dashboard')

    mandals = Mandal.objects.filter(schools__is_sanctioned=True).distinct().order_by('name')

    if request.method == 'POST':
        login_type = request.POST.get('login_type', 'school')

        if login_type == 'admin':
            username = request.POST.get('admin_username', '').strip()
            password = request.POST.get('admin_password', '').strip()
            user = authenticate(request, username=username, password=password)
            if user is not None and (user.is_superuser or user.is_staff):
                login(request, user)
                AuditLog.objects.create(
                    user=user,
                    action="LOGIN",
                    target_type="DistrictAdmin",
                    description=f"District admin '{username}' signed in.",
                    ip_address=get_client_ip(request)
                )
                messages.success(request, f"Welcome to District Admin Dashboard, {user.username}!")
                return redirect('district_dashboard')
            else:
                messages.error(request, "Invalid District Admin credentials. Please check your username and password.")

        else: # School login
            udise_code = request.POST.get('school_udise', '').strip()
            password = request.POST.get('password', '').strip()

            if not udise_code or not password:
                messages.error(request, "Please select both Mandal and School, and enter the password.")
            else:
                try:
                    school = School.objects.get(udise_code=udise_code, is_sanctioned=True)
                except School.DoesNotExist:
                    school = None

                if not school:
                    messages.error(request, "This school is not currently sanctioned for Bharat Scouts & Guides. Contact District Admin to add/sanction your school.")
                elif not school.user:
                    messages.error(request, "School account not initialized. Please contact District Office.")
                else:
                    user = authenticate(request, username=school.user.username, password=password)
                    if user is not None:
                        login(request, user)
                        AuditLog.objects.create(
                            school=school,
                            user=user,
                            action="LOGIN",
                            target_type="School",
                            description=f"School '{school.name}' ({school.udise_code}) logged in successfully.",
                            ip_address=get_client_ip(request)
                        )
                        if school.must_change_password:
                            messages.warning(request, "Security Notice: Please update your password before proceeding.")
                            return redirect('change_password')
                        messages.success(request, f"Welcome, {school.name}!")
                        return redirect('school_dashboard')
                    else:
                        messages.error(request, "Incorrect password. Default password is 'BSG@Sangareddy2026' unless changed.")

    context = {
        'mandals': mandals,
    }
    return render(request, 'login.html', context)


@require_GET
def api_schools_by_mandal(request):
    """Endpoint for cascading dropdown: returns only sanctioned schools under the selected mandal."""
    from collections import Counter
    from django.db.models import Count

    mandal_id = request.GET.get('mandal_id')
    if not mandal_id:
        return JsonResponse({'schools': []})

    schools = list(
        School.objects
        .filter(mandal_id=mandal_id, is_sanctioned=True)
        .select_related('mandal')
        .annotate(enrolled_count=Count('students'))
        .order_by('name')
    )
    name_counts = Counter(s.name for s in schools)
    data = []
    for s in schools:
        disp = f"{s.name} - {s.mandal.name}" if name_counts[s.name] > 1 else s.name
        data.append({
            'udise_code': s.udise_code,
            'name': s.name,
            'display_name': disp,
            'school_type': s.school_type,
            'school_type_display': s.get_school_type_display(),
            'boys_quota': s.boys_quota,
            'girls_quota': s.girls_quota,
            'enrolled': s.enrolled_count,
        })
    return JsonResponse({'schools': data})


@require_GET
def health_check_view(request):
    """Lightweight zero-DB health endpoint for Render / UptimeRobot keep-alive pings."""
    return JsonResponse({'status': 'ok'})


@require_GET
def api_live_stats(request):
    """Real-time live counter endpoint for footer and dashboards."""
    from django.core.cache import cache
    from django.db.models import Count, Q

    def _compute():
        student_agg = Student.objects.filter(school__is_sanctioned=True).aggregate(
            enrolled_total=Count('id'),
            boys_total=Count('id', filter=Q(gender='BOY')),
            girls_total=Count('id', filter=Q(gender='GIRL')),
        )
        return {
            'mandals_count': Mandal.objects.filter(schools__is_sanctioned=True).distinct().count(),
            'schools_count': School.objects.filter(is_sanctioned=True).count(),
            'enrolled_total': student_agg['enrolled_total'] or 0,
            'boys_total': student_agg['boys_total'] or 0,
            'girls_total': student_agg['girls_total'] or 0,
        }

    data = cache.get_or_set('bsg_live_stats_api', _compute, 15)
    return JsonResponse(data)


@require_GET
def api_school_verification_hint(request, udise_code):
    """Returns hint on whether school has registered mobile on file for forgot password verification."""
    try:
        school = School.objects.get(udise_code=udise_code, is_sanctioned=True)
    except School.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'School not found.'}, status=404)

    mobiles = []
    if school.contact_mobile:
        clean = ''.join(c for c in school.contact_mobile if c.isdigit())
        if len(clean) >= 10:
            mobiles.append(f"HM/Contact (ending in ...{clean[-4:]})")

    for ul in school.unit_leaders.all():
        if ul.mobile:
            clean = ''.join(c for c in ul.mobile if c.isdigit())
            if len(clean) >= 10:
                mobiles.append(f"{ul.get_role_display()} (ending in ...{clean[-4:]})")

    return JsonResponse({
        'success': True,
        'school_name': school.name,
        'udise_code': school.udise_code,
        'mandal_name': school.mandal.name,
        'has_registered_mobile': len(mobiles) > 0,
        'hints': mobiles,
    })


def forgot_password_view(request):
    """
    Self-service password recovery for recognized schools.
    Verification using registered Headmaster or designated Unit Leader mobile numbers,
    or resetting back to official default password.
    """
    if request.user.is_authenticated:
        if request.user.is_superuser or request.user.is_staff:
            return redirect('district_dashboard')
        elif hasattr(request.user, 'school_profile'):
            return redirect('school_dashboard')

    mandals = Mandal.objects.filter(schools__is_sanctioned=True).distinct().order_by('name')

    if request.method == 'POST':
        udise_code = request.POST.get('school_udise', '').strip() or request.POST.get('udise_code', '').strip()
        school = None
        if udise_code:
            try:
                school = School.objects.get(udise_code=udise_code, is_sanctioned=True)
            except School.DoesNotExist:
                school = None

        if not school:
            messages.error(request, "Please select a recognized school or enter a valid 11-digit UDISE code.")
            return render(request, 'forgot_password.html', {'mandals': mandals})

        verification_mobile = request.POST.get('verification_mobile', '').strip().replace(' ', '').replace('-', '')
        reset_type = request.POST.get('reset_type', 'custom') # 'custom' or 'default'
        new_password = request.POST.get('new_password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()

        # Build list of valid 10-digit mobile endings registered with this school
        valid_mobiles = set()
        if school.contact_mobile:
            cleaned = ''.join(c for c in school.contact_mobile if c.isdigit())
            if len(cleaned) >= 10:
                valid_mobiles.add(cleaned[-10:])

        for ul in school.unit_leaders.all():
            if ul.mobile:
                cleaned = ''.join(c for c in ul.mobile if c.isdigit())
                if len(cleaned) >= 10:
                    valid_mobiles.add(cleaned[-10:])

        user_clean = ''.join(c for c in verification_mobile if c.isdigit())
        user_last10 = user_clean[-10:] if len(user_clean) >= 10 else user_clean

        is_verified = False
        if valid_mobiles:
            if user_last10 and user_last10 in valid_mobiles:
                is_verified = True
            else:
                messages.error(
                    request,
                    f"Mobile verification failed for {school.name}. "
                    "The mobile number entered does not match the registered Headmaster or Unit Leader contact on file. "
                    "Please check your number or contact the Sangareddy District Office helpline for immediate reset."
                )
                return render(request, 'forgot_password.html', {
                    'mandals': mandals,
                    'selected_udise': udise_code,
                    'selected_mandal': school.mandal_id,
                    'school': school
                })
        else:
            # If no mobile numbers are on file in the official roster, allow reset with confirmation
            is_verified = True

        if is_verified:
            if reset_type == 'default' or not new_password:
                final_pw = "BSG@Sangareddy2026"
                must_change = True
            else:
                if len(new_password) < 8:
                    messages.error(request, "New password must be at least 8 characters long.")
                    return render(request, 'forgot_password.html', {
                        'mandals': mandals,
                        'selected_udise': udise_code,
                        'selected_mandal': school.mandal_id,
                        'school': school
                    })
                if new_password == "BSG@Sangareddy2026":
                    messages.error(request, "Please choose a unique password rather than reusing the default password.")
                    return render(request, 'forgot_password.html', {
                        'mandals': mandals,
                        'selected_udise': udise_code,
                        'selected_mandal': school.mandal_id,
                        'school': school
                    })
                if new_password != confirm_password:
                    messages.error(request, "Passwords do not match. Please re-enter carefully.")
                    return render(request, 'forgot_password.html', {
                        'mandals': mandals,
                        'selected_udise': udise_code,
                        'selected_mandal': school.mandal_id,
                        'school': school
                    })
                final_pw = new_password
                must_change = False

            if school.user:
                school.user.set_password(final_pw)
                school.user.save()
                school.must_change_password = must_change
                school.save()

                AuditLog.objects.create(
                    school=school,
                    user=school.user,
                    action="FORGOT_PASSWORD_RESET",
                    target_type="School",
                    target_id=school.udise_code,
                    description=f"School '{school.name}' ({school.udise_code}) self-reset password via verification. ResetType={reset_type}.",
                    ip_address=get_client_ip(request)
                )
                messages.success(
                    request,
                    f"Password for {school.name} ({school.udise_code}) has been reset successfully! You can now log in."
                )
                return redirect('login')
            else:
                messages.error(request, "School user account is missing. Please contact District Administrator.")

    return render(request, 'forgot_password.html', {'mandals': mandals})


@login_required
@login_required
def change_password_view(request):
    """
    Mandatory or voluntary password change for school.
    If the school has no mobile numbers on file, providing at least one valid
    10-digit mobile (HM or Unit Leader) is strictly mandatory before accessing dashboard.
    When changing password voluntarily (must_change_password=False), current password is required.
    """
    school = getattr(request.user, 'school_profile', None)
    needs_contact = not school.has_recovery_contact() if school else False
    require_current_pw = (not school.must_change_password) if school else True
    leaders = list(school.unit_leaders.all().order_by('id')) if school else []

    if request.method == 'POST':
        current_password = request.POST.get('current_password', '').strip()
        new_password = request.POST.get('new_password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()
        hm_name = request.POST.get('hm_name', '').strip()
        hm_mobile = request.POST.get('hm_mobile', '').strip()

        # Clean HM mobile
        cleaned_hm = ''.join(c for c in hm_mobile if c.isdigit())
        has_valid_hm = len(cleaned_hm) >= 10

        # Check Unit Leader mobiles
        has_valid_leader = False
        for l in leaders:
            l_mob = request.POST.get(f'leader_mobile_{l.id}', '').strip()
            clean_l = ''.join(c for c in l_mob if c.isdigit())
            if len(clean_l) >= 10:
                has_valid_leader = True

        new_leader_name = request.POST.get('new_leader_name', '').strip()
        new_leader_mobile = request.POST.get('new_leader_mobile', '').strip()
        clean_new_l = ''.join(c for c in new_leader_mobile if c.isdigit())
        if len(clean_new_l) >= 10:
            has_valid_leader = True

        if require_current_pw and not request.user.check_password(current_password):
            messages.error(request, "Current password is incorrect. Please enter your existing password.")
        elif len(new_password) < 8:
            messages.error(request, "Password must be at least 8 characters long.")
        elif new_password == 'BSG@Sangareddy2026':
            messages.error(request, "You cannot reuse the default password. Please choose a unique password.")
        elif new_password != confirm_password:
            messages.error(request, "Passwords do not match. Please re-enter carefully.")
        elif needs_contact and not has_valid_hm and not has_valid_leader:
            messages.error(
                request,
                "⚠️ Mandatory Contact Required: Your school currently has no phone numbers on record. "
                "You must provide at least the Headmaster's mobile number or a Unit Leader's mobile number (10 digits) "
                "to secure your account and enable password recovery."
            )
        else:
            request.user.set_password(new_password)
            request.user.save()
            update_session_auth_hash(request, request.user)

            if school:
                updated_details = []
                if has_valid_hm:
                    school.contact_mobile = cleaned_hm[-10:]
                    updated_details.append(f"HM Mobile: {school.contact_mobile}")
                if hm_name:
                    school.headmaster_name = hm_name
                    school.contact_person = hm_name
                    updated_details.append(f"HM Name: {hm_name}")

                for l in leaders:
                    l_mob = request.POST.get(f'leader_mobile_{l.id}', '').strip()
                    clean_l = ''.join(c for c in l_mob if c.isdigit())
                    if len(clean_l) >= 10:
                        l.mobile = clean_l[-10:]
                        l.save()
                        updated_details.append(f"Leader ({l.name}) Mobile: {l.mobile}")

                if not leaders and clean_new_l and len(clean_new_l) >= 10:
                    allowed_roles = school.allowed_leader_roles()
                    role = allowed_roles[0] if allowed_roles else LeaderRole.SCOUT_MASTER
                    gender = 'MALE' if role in [LeaderRole.SCOUT_MASTER, LeaderRole.CUB_MASTER] else 'FEMALE'
                    UnitLeader.objects.create(
                        school=school,
                        name=new_leader_name or f"Unit Leader ({school.name})",
                        role=role,
                        gender=gender,
                        mobile=clean_new_l[-10:]
                    )
                    updated_details.append(f"New Unit Leader Mobile: {clean_new_l[-10:]}")

                school.must_change_password = False
                school.save()

                AuditLog.objects.create(
                    school=school,
                    user=request.user,
                    action="PASSWORD_CHANGE",
                    target_type="School",
                    target_id=school.udise_code,
                    description=f"Password updated successfully. Contacts: {', '.join(updated_details) if updated_details else 'Retained existing'}.",
                    ip_address=get_client_ip(request)
                )

            messages.success(request, "Password and recovery contact numbers updated successfully! Welcome to your school dashboard.")
            return redirect('school_dashboard' if school else 'district_dashboard')

    return render(request, 'change_password.html', {
        'school': school,
        'needs_contact': needs_contact,
        'require_current_pw': require_current_pw,
        'leaders': leaders,
    })


def logout_view(request):
    AuditLog.objects.create(
        user=request.user if request.user.is_authenticated else None,
        action="LOGOUT",
        target_type="User",
        description=f"User signed out.",
        ip_address=get_client_ip(request)
    )
    logout(request)
    messages.info(request, "You have been signed out.")
    return redirect('login')


def help_view(request):
    """Bilingual help and FAQ page toggled by ?lang=en or ?lang=te."""
    lang = request.GET.get('lang', request.session.get('lang', 'en'))
    if lang not in ['en', 'te']:
        lang = 'en'
    request.session['lang'] = lang

    # Provide all text strings for active language
    t = MESSAGES[lang]
    return render(request, 'help.html', {'t': t, 'lang': lang})


def contact_view(request):
    """Contact details for Bharat Scouts & Guides District Headquarters Sangareddy."""
    return render(request, 'contact.html')


# ==========================================
# SCHOOL DASHBOARD & ENROLLMENT CRUD
# ==========================================

@login_required
@require_password_changed
def school_dashboard_view(request):
    school = getattr(request.user, 'school_profile', None)
    if not school:
        if request.user.is_superuser or request.user.is_staff:
            return redirect('district_dashboard')
        messages.error(request, "No school profile associated with this account.")
        return redirect('login')

    # Fetch students with filters
    students_qs = school.students.all()

    # Search query
    q = request.GET.get('q', '').strip()
    if q:
        students_qs = students_qs.filter(name__icontains=q) | students_qs.filter(father_name__icontains=q)

    # Class filter
    cls_filter = request.GET.get('class')
    if cls_filter and cls_filter.isdigit():
        students_qs = students_qs.filter(class_level=int(cls_filter))

    # Gender filter
    gender_filter = request.GET.get('gender')
    if gender_filter in ['BOY', 'GIRL']:
        students_qs = students_qs.filter(gender=gender_filter)

    # Status filter (SHORT vs BRIEF)
    status_filter = request.GET.get('status')
    if status_filter in ['SHORT', 'BRIEF']:
        students_qs = students_qs.filter(detail_level=status_filter)

    students = students_qs.order_by('class_level', 'gender', 'name')
    unit_leaders = school.unit_leaders.all()

    # Pre-calculate progress percentages
    boys_pct = round((school.boys_enrolled_count() / school.boys_quota * 100), 1) if school.boys_quota > 0 else 0
    girls_pct = round((school.girls_enrolled_count() / school.girls_quota * 100), 1) if school.girls_quota > 0 else 0
    total_pct = round((school.total_enrolled_count() / school.total_quota() * 100), 1) if school.total_quota() > 0 else 0

    context = {
        'school': school,
        'students': students,
        'unit_leaders': unit_leaders,
        'allowed_classes': school.allowed_classes(),
        'allowed_genders': school.allowed_genders(),
        'allowed_sizes': school.allowed_uniform_sizes(),
        'allowed_leader_sizes': school.allowed_leader_sizes(),
        'allowed_leader_roles': school.allowed_leader_roles(),
        'leader_role_choices': LeaderRole.choices,
        'boys_pct': min(100, boys_pct),
        'girls_pct': min(100, girls_pct),
        'total_pct': min(100, total_pct),
        'q': q,
        'cls_filter': cls_filter,
        'gender_filter': gender_filter,
        'status_filter': status_filter,
    }
    return render(request, 'dashboard.html', context)


def _student_form_response(request, success, message, status=200, extra=None):
    """Return JSON for AJAX/API clients, or redirect back to dashboard for plain browser form POSTs."""
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    wants_html = 'text/html' in request.headers.get('Accept', '')
    if not is_ajax and wants_html:
        if success:
            messages.success(request, message)
        else:
            messages.error(request, message)
        return redirect('school_dashboard')
    payload = {'success': success, 'message': message}
    if extra:
        payload.update(extra)
    return JsonResponse(payload, status=status)


@login_required
@require_password_changed
@require_POST
def enroll_student_view(request):
    """
    Enrolls a student with strict quota enforcement and database row locking.
    Supports SHORT and BRIEF modes.
    """
    school = getattr(request.user, 'school_profile', None)
    if not school:
        return _student_form_response(request, False, 'Unauthorized school profile.', status=403)

    gender = request.POST.get('gender', '').strip()
    name = request.POST.get('name', '').strip()
    father_name = request.POST.get('father_name', '').strip()
    class_val = request.POST.get('class_level', '').strip()
    height_val = request.POST.get('height_cm', '').strip()
    uniform_size = request.POST.get('uniform_size', '').strip()
    shoe_size = request.POST.get('shoe_size', '').strip()
    detail_mode = request.POST.get('detail_level', 'SHORT').strip()

    # Basic validations
    if not name or not father_name or not class_val or not height_val or not uniform_size or not shoe_size:
        return _student_form_response(request, False, 'Please fill all required fields marked with *.', status=400)

    try:
        class_level = int(class_val)
    except ValueError:
        return _student_form_response(request, False, 'Invalid Class.', status=400)

    try:
        height_cm = Decimal(height_val)
        if height_cm < 90 or height_cm > 220:
            return _student_form_response(request, False, 'Height must be between 90 and 220 cm.', status=400)
    except Exception:
        return _student_form_response(request, False, 'Invalid Height in cm.', status=400)

    if gender not in school.allowed_genders():
        return _student_form_response(request, False, f"This school cannot enroll {gender}s based on school category.", status=400)

    if class_level not in school.allowed_classes():
        return _student_form_response(request, False, f"Class {class_level} is not permitted for this school category.", status=400)

    # Optional BRIEF details
    dob = None
    dob_raw = request.POST.get('dob', '').strip()
    if dob_raw:
        try:
            dob = dob_raw
        except Exception:
            pass

    parent_mobile = request.POST.get('parent_mobile', '').strip()

    # Tailoring helper
    def parse_m(name):
        val = request.POST.get(name, '').strip()
        if not val:
            return None
        try:
            d = Decimal(val)
            if d < 10 or d > 60:
                raise ValueError()
            if (float(d) * 10) % 5 != 0:
                raise ValueError()
            return d
        except Exception:
            return None

    # Strict Quota Enforcement via DB Transaction Lock
    try:
        with transaction.atomic():
            school_locked = School.objects.select_for_update().get(pk=school.pk)

            # Check quota
            if gender == 'BOY' and school_locked.boys_enrolled_count() >= school_locked.boys_quota:
                return _student_form_response(request, False, f"Boys Quota is Full ({school_locked.boys_quota}/{school_locked.boys_quota})!", status=400)
            elif gender == 'GIRL' and school_locked.girls_enrolled_count() >= school_locked.girls_quota:
                return _student_form_response(request, False, f"Girls Quota is Full ({school_locked.girls_quota}/{school_locked.girls_quota})!", status=400)

            # Duplicate / Idempotency check
            existing = Student.objects.filter(
                school=school_locked,
                gender=gender,
                name__iexact=name,
                father_name__iexact=father_name,
                class_level=class_level
            ).first()

            if existing:
                return _student_form_response(
                    request,
                    False,
                    f"Student '{name}' (Father: '{father_name}') in Class {class_level} is already enrolled in this school.",
                    status=400
                )

            student = Student(
                school=school_locked,
                gender=gender,
                name=name,
                father_name=father_name,
                class_level=class_level,
                height_cm=height_cm,
                uniform_size=uniform_size,
                shoe_size=shoe_size,
                detail_level=detail_mode,
                dob=dob,
                parent_mobile=parent_mobile
            )

            # Assign measurements based on gender
            if gender == 'BOY':
                student.chest = parse_m('chest')
                student.waist = parse_m('waist')
                student.neck = parse_m('neck')
                student.shoulder = parse_m('shoulder')
                student.sleeve = parse_m('sleeve')
                student.shirt_length = parse_m('shirt_length')
                student.pant_length = parse_m('pant_length')
            else:
                student.bust = parse_m('bust')
                student.waist = parse_m('waist')
                student.hip = parse_m('hip')
                student.shoulder = parse_m('shoulder')
                student.sleeve = parse_m('sleeve')
                student.kameez_length = parse_m('kameez_length')
                student.salwar_length = parse_m('salwar_length')

            student.full_clean()
            student.save()

            AuditLog.objects.create(
                school=school_locked,
                user=request.user,
                action="CREATE_STUDENT",
                target_type="Student",
                target_id=str(student.id),
                description=f"Enrolled {student.get_gender_display()} '{student.name}', Class {student.class_level} ({student.detail_level} mode).",
                ip_address=get_client_ip(request)
            )

        if 'text/html' not in request.headers.get('Accept', '') or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            messages.success(request, f"Student '{student.name}' enrolled successfully!")
        return _student_form_response(
            request,
            True,
            f"Student '{student.name}' enrolled successfully!",
            extra={'student_id': student.id}
        )

    except ValidationError as ve:
        return _student_form_response(request, False, str(ve), status=400)
    except Exception as e:
        return _student_form_response(request, False, f"Server error: {str(e)}", status=500)


@login_required
@require_password_changed
@require_GET
def get_student_json(request, student_id):
    """Fetch student JSON data for editing."""
    school = getattr(request.user, 'school_profile', None)
    student = get_object_or_404(Student, pk=student_id, school=school)

    data = {
        'id': student.id,
        'name': student.name,
        'father_name': student.father_name,
        'gender': student.gender,
        'class_level': student.class_level,
        'height_cm': str(student.height_cm),
        'uniform_size': student.uniform_size,
        'shoe_size': student.shoe_size,
        'detail_level': student.detail_level,
        'dob': str(student.dob) if student.dob else '',
        'parent_mobile': student.parent_mobile or '',
        # Measurements
        'chest': str(student.chest or ''),
        'waist': str(student.waist or ''),
        'neck': str(student.neck or ''),
        'shoulder': str(student.shoulder or ''),
        'sleeve': str(student.sleeve or ''),
        'shirt_length': str(student.shirt_length or ''),
        'pant_length': str(student.pant_length or ''),
        'bust': str(student.bust or ''),
        'hip': str(student.hip or ''),
        'kameez_length': str(student.kameez_length or ''),
        'salwar_length': str(student.salwar_length or ''),
    }
    return JsonResponse({'success': True, 'student': data})


@login_required
@require_password_changed
@require_POST
def edit_student_view(request, student_id):
    """Updates student records, allowing upgrade from SHORT to BRIEF with tailoring specs."""
    school = getattr(request.user, 'school_profile', None)
    student = get_object_or_404(Student, pk=student_id, school=school)

    name = request.POST.get('name', '').strip()
    father_name = request.POST.get('father_name', '').strip()
    class_val = request.POST.get('class_level', '').strip()
    height_val = request.POST.get('height_cm', '').strip()
    uniform_size = request.POST.get('uniform_size', '').strip()
    shoe_size = request.POST.get('shoe_size', '').strip()
    detail_mode = request.POST.get('detail_level', student.detail_level).strip()

    if not name or not father_name or not class_val or not height_val or not uniform_size or not shoe_size:
        return _student_form_response(request, False, 'Missing required fields.', status=400)

    try:
        class_level = int(class_val)
        height_cm = Decimal(height_val)
    except Exception:
        return _student_form_response(request, False, 'Invalid numerical values.', status=400)

    student.name = name
    student.father_name = father_name
    student.class_level = class_level
    student.height_cm = height_cm
    student.uniform_size = uniform_size
    student.shoe_size = shoe_size
    student.detail_level = detail_mode

    dob_raw = request.POST.get('dob', '').strip()
    student.dob = dob_raw if dob_raw else None
    student.parent_mobile = request.POST.get('parent_mobile', '').strip()

    def parse_m(k):
        val = request.POST.get(k, '').strip()
        if not val:
            return None
        try:
            return Decimal(val)
        except Exception:
            return None

    if student.gender == 'BOY':
        student.chest = parse_m('chest')
        student.waist = parse_m('waist')
        student.neck = parse_m('neck')
        student.shoulder = parse_m('shoulder')
        student.sleeve = parse_m('sleeve')
        student.shirt_length = parse_m('shirt_length')
        student.pant_length = parse_m('pant_length')
    else:
        student.bust = parse_m('bust')
        student.waist = parse_m('waist')
        student.hip = parse_m('hip')
        student.shoulder = parse_m('shoulder')
        student.sleeve = parse_m('sleeve')
        student.kameez_length = parse_m('kameez_length')
        student.salwar_length = parse_m('salwar_length')

    try:
        student.full_clean()
        student.save()

        AuditLog.objects.create(
            school=school,
            user=request.user,
            action="UPDATE_STUDENT",
            target_type="Student",
            target_id=str(student.id),
            description=f"Updated details for student '{student.name}', Class {student.class_level}.",
            ip_address=get_client_ip(request)
        )
        if 'text/html' not in request.headers.get('Accept', '') or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            messages.success(request, f"Student '{student.name}' updated successfully!")
        return _student_form_response(request, True, f"Student '{student.name}' updated successfully!")
    except Exception as e:
        return _student_form_response(request, False, str(e), status=400)


@login_required
@require_password_changed
@require_POST
def delete_student_view(request, student_id):
    """Deletes a student record and immediately restores school quota."""
    school = getattr(request.user, 'school_profile', None)
    student = get_object_or_404(Student, pk=student_id, school=school)
    student_name = student.name
    gender_display = student.get_gender_display()

    student.delete()

    AuditLog.objects.create(
        school=school,
        user=request.user,
        action="DELETE_STUDENT",
        target_type="Student",
        target_id=str(student_id),
        description=f"Deleted {gender_display} student '{student_name}'. Restored quota.",
        ip_address=get_client_ip(request)
    )
    messages.success(request, f"Student '{student_name}' deleted. Quota restored.")
    return redirect('school_dashboard')


# ==========================================
# UNIT LEADERS MANAGEMENT (DISTRICT ADMIN ONLY)
# ==========================================

@login_required
@require_POST
def save_leader_view(request):
    """
    Adds or updates teacher unit leader.
    Accessible to:
      1. District Admin (can manage leaders for any school)
      2. School User (can edit/update leaders for their own school)
    """
    is_admin = request.user.is_superuser or request.user.is_staff
    leader_id = request.POST.get('leader_id')
    school_id = request.POST.get('school_id')

    if is_admin:
        if school_id:
            school = get_object_or_404(School, pk=school_id)
        elif leader_id:
            leader = get_object_or_404(UnitLeader, pk=leader_id)
            school = leader.school
        else:
            messages.error(request, "School ID is required.")
            return redirect('district_dashboard')
    else:
        school = getattr(request.user, 'school_profile', None)
        if not school:
            messages.error(request, "Permission denied: School profile not found.")
            return redirect('login')

    role = request.POST.get('role', '').strip()
    name = request.POST.get('name', '').strip()
    gender = request.POST.get('gender', '').strip()
    mobile = request.POST.get('mobile', '').strip()
    designation = request.POST.get('designation', '').strip()
    email = request.POST.get('email', '').strip()
    uniform_size = request.POST.get('uniform_size', '').strip()
    shoe_size = request.POST.get('shoe_size', '').strip()

    def parse_dec(k):
        v = request.POST.get(k, '').strip()
        try:
            return Decimal(v) if v else None
        except Exception:
            return None

    if leader_id:
        if is_admin:
            leader = get_object_or_404(UnitLeader, pk=leader_id)
        else:
            leader = get_object_or_404(UnitLeader, pk=leader_id, school=school)
    else:
        # Check max leaders limit for this school
        if school.unit_leaders.count() >= school.max_leaders_count():
            messages.error(request, f"This school category cannot exceed {school.max_leaders_count()} unit leader(s).")
            if is_admin:
                return redirect('district_dashboard')
            return redirect('school_dashboard')
        leader = UnitLeader(school=school)

    # Validate or set role
    if role:
        leader.role = role
    elif not leader.role:
        allowed = school.allowed_leader_roles()
        leader.role = allowed[0] if allowed else LeaderRole.SCOUT_MASTER

    # Infer gender if not explicitly passed
    if gender:
        leader.gender = gender
    elif not leader.gender:
        if leader.role in [LeaderRole.GUIDE_CAPTAIN, LeaderRole.FLOCK_LEADER]:
            leader.gender = 'FEMALE'
        else:
            leader.gender = 'MALE'

    if name:
        leader.name = name
    leader.mobile = mobile
    leader.designation = designation
    leader.email = email
    leader.uniform_size = uniform_size
    leader.shoe_size = shoe_size
    leader.height_cm = parse_dec('height_cm')
    leader.is_frozen = True
    leader.chest_bust = parse_dec('chest_bust')
    leader.waist = parse_dec('waist')
    leader.neck = parse_dec('neck')
    leader.shoulder = parse_dec('shoulder')
    leader.sleeve = parse_dec('sleeve')
    leader.top_length = parse_dec('top_length')
    leader.bottom_length = parse_dec('bottom_length')
    leader.hip = parse_dec('hip')
    leader.save()

    actor = "District Admin" if is_admin else f"School '{school.name}'"
    AuditLog.objects.create(
        school=school,
        user=request.user,
        action="SAVE_UNIT_LEADER",
        target_type="UnitLeader",
        target_id=str(leader.id),
        description=f"{actor} updated Unit Leader '{leader.name}' ({leader.get_role_display()}) for {school.name}.",
        ip_address=get_client_ip(request)
    )
    messages.success(request, f"Unit Leader '{leader.name}' information saved successfully!")

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == '1':
        return JsonResponse({'success': True, 'message': f"Unit Leader '{leader.name}' saved successfully!"})

    if is_admin:
        return redirect('district_dashboard')
    return redirect('school_dashboard')


@user_passes_test(is_district_admin_check, login_url='/login/')
@require_POST
def delete_leader_view(request, leader_id):
    """District Admin exclusive: Removes a unit leader."""
    leader = get_object_or_404(UnitLeader, pk=leader_id)
    school = leader.school
    name = leader.name
    leader.delete()

    AuditLog.objects.create(
        school=school,
        user=request.user,
        action="DELETE_UNIT_LEADER",
        target_type="UnitLeader",
        target_id=str(leader_id),
        description=f"District Admin removed Unit Leader '{name}' from {school.name}.",
        ip_address=get_client_ip(request)
    )
    messages.success(request, f"Unit Leader '{name}' removed from {school.name}.")
    return redirect('district_dashboard')


@require_GET
def api_get_school_leaders(request, school_id):
    """Returns JSON list of leaders for a school for the Leader Management & Measurement modals."""
    school = get_object_or_404(School, pk=school_id)
    # Check permission: District admin or the school itself
    if not (request.user.is_superuser or request.user.is_staff):
        user_school = getattr(request.user, 'school_profile', None)
        if not user_school or user_school.id != school.id:
            return JsonResponse({'success': False, 'message': 'Permission denied.'}, status=403)

    leaders = []
    for l in school.unit_leaders.all():
        leaders.append({
            'id': l.id,
            'role': l.role,
            'role_display': l.get_role_display(),
            'name': l.name,
            'gender': l.gender,
            'mobile': l.mobile,
            'designation': l.designation,
            'email': l.email,
            'uniform_size': l.uniform_size,
            'shoe_size': l.shoe_size,
            'height_cm': float(l.height_cm) if l.height_cm else None,
            'chest_bust': float(l.chest_bust) if l.chest_bust else None,
            'waist': float(l.waist) if l.waist else None,
            'neck': float(l.neck) if l.neck else None,
            'shoulder': float(l.shoulder) if l.shoulder else None,
            'sleeve': float(l.sleeve) if l.sleeve else None,
            'top_length': float(l.top_length) if l.top_length else None,
            'bottom_length': float(l.bottom_length) if l.bottom_length else None,
            'hip': float(l.hip) if l.hip else None,
        })
    return JsonResponse({'success': True, 'school_name': school.name, 'udise_code': school.udise_code, 'leaders': leaders})


@login_required
@require_POST
def update_leader_measurements_view(request, leader_id):
    """Allows School or District Admin to record/update tailoring measurements for a Unit Leader."""
    if request.user.is_superuser or request.user.is_staff:
        leader = get_object_or_404(UnitLeader, pk=leader_id)
    else:
        user_school = getattr(request.user, 'school_profile', None)
        if not user_school:
            return JsonResponse({'success': False, 'message': 'Permission denied.'}, status=403)
        leader = get_object_or_404(UnitLeader, pk=leader_id, school=user_school)

    def parse_dec(k):
        v = request.POST.get(k, '').strip()
        try:
            return Decimal(v) if v else None
        except Exception:
            return None

    uniform_size = request.POST.get('uniform_size', leader.uniform_size).strip()
    shoe_size = request.POST.get('shoe_size', leader.shoe_size).strip()

    leader.uniform_size = uniform_size
    leader.shoe_size = shoe_size
    leader.height_cm = parse_dec('height_cm')
    leader.chest_bust = parse_dec('chest_bust')
    leader.waist = parse_dec('waist')
    leader.neck = parse_dec('neck')
    leader.shoulder = parse_dec('shoulder')
    leader.sleeve = parse_dec('sleeve')
    leader.top_length = parse_dec('top_length')
    leader.bottom_length = parse_dec('bottom_length')
    leader.hip = parse_dec('hip')
    leader.save()

    AuditLog.objects.create(
        school=leader.school,
        user=request.user,
        action="UPDATE_LEADER_MEASUREMENTS",
        target_type="UnitLeader",
        target_id=str(leader.id),
        description=f"Updated uniform measurements for Unit Leader '{leader.name}' ({leader.get_role_display()}).",
        ip_address=get_client_ip(request)
    )

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == '1':
        return JsonResponse({
            'success': True,
            'message': f"Measurements for {leader.name} successfully updated!"
        })

    messages.success(request, f"Uniform measurements for Unit Leader {leader.name} saved successfully!")
    if request.user.is_superuser or request.user.is_staff:
        return redirect('district_dashboard')
    return redirect('school_dashboard')


# ==========================================
# EXPORT & IMPORT VIEWS
# ==========================================

@login_required
@require_password_changed
def export_excel_template_view(request):
    school = getattr(request.user, 'school_profile', None)
    if not school:
        return redirect('login')

    excel_io = generate_school_excel_template(school)
    response = HttpResponse(
        excel_io.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    filename = f"BSG_Template_{school.udise_code}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@require_password_changed
@require_POST
def import_excel_view(request):
    school = getattr(request.user, 'school_profile', None)
    if not school:
        return redirect('login')

    excel_file = request.FILES.get('excel_file')
    if not excel_file:
        messages.error(request, "Please choose an Excel file (.xlsx) to upload.")
        return redirect('school_dashboard')

    if not excel_file.name.endswith(('.xlsx', '.xlsm')):
        messages.error(request, "Only valid Excel (.xlsx) workbooks are supported.")
        return redirect('school_dashboard')

    success, errors, count = import_students_from_excel(
        school=school,
        file_obj=excel_file,
        user=request.user,
        ip_address=get_client_ip(request)
    )

    if success:
        messages.success(request, f"Import Successful! {count} students were successfully enrolled/updated.")
    else:
        # Pass errors to session for detailed display
        request.session['excel_import_errors'] = errors
        messages.error(request, f"Import Aborted! {len(errors)} error(s) detected. Please review the error list below.")

    return redirect('school_dashboard')


@login_required
@require_password_changed
def export_school_excel_view(request):
    school = getattr(request.user, 'school_profile', None)
    if not school:
        return redirect('login')

    excel_io = export_school_excel(school)
    response = HttpResponse(
        excel_io.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    filename = f"BSG_Enrollment_{school.udise_code}_{datetime.now().strftime('%Y%m%d')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@require_password_changed
def export_school_pdf_view(request):
    school = getattr(request.user, 'school_profile', None)
    if not school:
        return redirect('login')

    pdf_io = generate_school_pdf_report(school)
    response = HttpResponse(pdf_io.getvalue(), content_type="application/pdf")
    filename = f"BSG_Roster_{school.udise_code}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


@user_passes_test(is_district_admin_check, login_url='/login/')
def district_admin_account_view(request):
    """
    Allows the District Admin to update their authorized username and/or password.
    Requires verification of the current (past) password for security.
    """
    if request.method != 'POST':
        return redirect('district_dashboard')

    import re
    current_password = request.POST.get('current_password', '').strip()
    new_username = request.POST.get('new_username', '').strip()
    new_password = request.POST.get('new_password', '').strip()
    confirm_password = request.POST.get('confirm_password', '').strip()

    if not current_password or not request.user.check_password(current_password):
        messages.error(request, "Current (past) password is incorrect. Admin credentials were not modified.")
        return redirect('district_dashboard')

    changes = []
    if new_username and new_username != request.user.username:
        if len(new_username) < 4 or not re.match(r'^[a-zA-Z0-9_.-]+$', new_username):
            messages.error(request, "Admin username must be at least 4 characters (letters, numbers, _, ., - only).")
            return redirect('district_dashboard')
        if User.objects.filter(username=new_username).exclude(pk=request.user.pk).exists():
            messages.error(request, f"Username '{new_username}' is already in use. Please choose another.")
            return redirect('district_dashboard')
        old_username = request.user.username
        request.user.username = new_username
        changes.append(f"username changed from '{old_username}' to '{new_username}'")

    if new_password:
        if len(new_password) < 8:
            messages.error(request, "New admin password must be at least 8 characters long.")
            return redirect('district_dashboard')
        if new_password == 'Admin@Sangareddy2026':
            messages.error(request, "You cannot reuse the default password. Please choose a strong unique password.")
            return redirect('district_dashboard')
        if new_password != confirm_password:
            messages.error(request, "New password and confirmation do not match.")
            return redirect('district_dashboard')
        request.user.set_password(new_password)
        changes.append("password updated")

    if not changes:
        messages.info(request, "No changes were submitted to your admin account.")
        return redirect('district_dashboard')

    request.user.save()
    update_session_auth_hash(request, request.user)

    AuditLog.objects.create(
        user=request.user,
        action="ADMIN_CREDENTIAL_CHANGE",
        target_type="DistrictAdmin",
        description=f"District Admin credentials updated: {', '.join(changes)}.",
        ip_address=get_client_ip(request)
    )
    messages.success(request, f"Admin account updated successfully ({', '.join(changes)}).")
    return redirect('district_dashboard')


# ==========================================
# DISTRICT ADMIN COMMAND CENTER
# ==========================================

@user_passes_test(is_district_admin_check, login_url='/login/')
def district_dashboard_view(request):
    # ── Single-query student & leader count annotation ─────────────────────────
    # Use distinct=True on Count when joining multiple reverse relations
    # (students + unit_leaders) so SQL joins never multiply counts.
    from django.db.models import Count, Q, Sum

    mandals = list(Mandal.objects.all().order_by('name'))

    # Base annotated school queryset — counts in SQL, not Python loops
    base_qs = School.objects.select_related('mandal').annotate(
        boys_enrolled=Count('students', filter=Q(students__gender='BOY'), distinct=True),
        girls_enrolled=Count('students', filter=Q(students__gender='GIRL'), distinct=True),
        unit_leaders_count=Count('unit_leaders', distinct=True),
    )

    schools_qs = base_qs

    # Search & Mandal filter
    mandal_id = request.GET.get('mandal_id')
    if mandal_id and mandal_id.isdigit():
        schools_qs = schools_qs.filter(mandal_id=int(mandal_id))

    q = request.GET.get('q', '').strip()
    if q:
        schools_qs = schools_qs.filter(name__icontains=q) | schools_qs.filter(udise_code__icontains=q)

    schools = schools_qs.order_by('mandal__name', 'name')

    # ── Mandal progress stats — 2 separate aggregation queries (no join inflation)
    school_mandal_agg = {
        row['mandal_id']: row
        for row in School.objects.values('mandal_id').annotate(
            school_count=Count('id'),
            boys_quota=Sum('boys_quota'),
            girls_quota=Sum('girls_quota'),
        )
    }
    student_mandal_agg = {
        row['school__mandal_id']: row
        for row in Student.objects.values('school__mandal_id').annotate(
            boys_enrolled=Count('id', filter=Q(gender='BOY')),
            girls_enrolled=Count('id', filter=Q(gender='GIRL')),
        )
    }

    mandal_stats = []
    for m in mandals:
        s_agg = school_mandal_agg.get(m.id, {})
        st_agg = student_mandal_agg.get(m.id, {})
        b_q = s_agg.get('boys_quota') or 0
        g_q = s_agg.get('girls_quota') or 0
        b_enr = st_agg.get('boys_enrolled') or 0
        g_enr = st_agg.get('girls_enrolled') or 0
        tot_q = b_q + g_q
        tot_enr = b_enr + g_enr
        pct = round((tot_enr / tot_q * 100), 1) if tot_q > 0 else 0
        mandal_stats.append({
            'mandal': m,
            'school_count': s_agg.get('school_count') or 0,
            'boys_quota': b_q,
            'boys_enrolled': b_enr,
            'girls_quota': g_q,
            'girls_enrolled': g_enr,
            'total_quota': tot_q,
            'total_enrolled': tot_enr,
            'pct': min(100, pct),
        })

    # Recent Audit Logs
    audit_logs = AuditLog.objects.select_related('school', 'user').order_by('-created_at')[:50]

    # ── Overall KPIs — single DB aggregation each ─────────────────────────────
    all_schools = School.objects.select_related('mandal').only('id', 'udise_code', 'name', 'mandal__name').order_by('mandal__name', 'name')

    kpi = School.objects.aggregate(
        total_schools=Count('id'),
        total_boys_q=Sum('boys_quota'),
        total_girls_q=Sum('girls_quota'),
    )
    student_kpi = Student.objects.aggregate(
        total_boys_enr=Count('id', filter=Q(gender='BOY')),
        total_girls_enr=Count('id', filter=Q(gender='GIRL')),
    )
    total_schools = kpi['total_schools'] or 0
    total_boys_q = kpi['total_boys_q'] or 0
    total_girls_q = kpi['total_girls_q'] or 0
    total_boys_enr = student_kpi['total_boys_enr'] or 0
    total_girls_enr = student_kpi['total_girls_enr'] or 0
    total_enr = total_boys_enr + total_girls_enr
    total_quota = total_boys_q + total_girls_q
    overall_pct = round((total_enr / total_quota * 100), 1) if total_quota > 0 else 0

    # Circulars & Photo Gallery
    circulars = Circular.objects.all()
    gallery_photos = GalleryPhoto.objects.all()

    context = {
        'mandals': mandals,
        'schools': schools,
        'all_schools': all_schools,
        'mandal_stats': mandal_stats,
        'audit_logs': audit_logs,
        'circulars': circulars,
        'gallery_photos': gallery_photos,
        'use_cloudinary': getattr(settings, 'USE_CLOUDINARY', False),
        'total_schools': total_schools,
        'total_boys_q': total_boys_q,
        'total_girls_q': total_girls_q,
        'total_boys_enr': total_boys_enr,
        'total_girls_enr': total_girls_enr,
        'total_enr': total_enr,
        'total_quota': total_quota,
        'overall_pct': min(100, overall_pct),
        'q': q,
        'selected_mandal': mandal_id,
        'school_types': SchoolType.choices,
    }
    return render(request, 'district_dashboard.html', context)


@user_passes_test(is_district_admin_check, login_url='/login/')
@require_POST
def district_reset_school_password(request, udise_code):
    school = get_object_or_404(School, udise_code=udise_code)
    new_password = request.POST.get('new_password', '').strip()
    must_change = request.POST.get('must_change_password') in ['1', 'on', 'true', True] or ('must_change_password' not in request.POST)
    if not new_password:
        new_password = "BSG@Sangareddy2026"

    if school.user:
        school.user.set_password(new_password)
        school.user.save()
        school.must_change_password = must_change
        school.save()

        AuditLog.objects.create(
            school=school,
            user=request.user,
            action="PASSWORD_RESET",
            target_type="School",
            target_id=school.udise_code,
            description=f"District admin changed password for school '{school.name}' ({school.udise_code}) to '{new_password}'. PromptOnLogin={must_change}.",
            ip_address=get_client_ip(request)
        )
        messages.success(request, f"Password for {school.name} ({school.udise_code}) successfully updated to '{new_password}'! (Prompt on login: {'Yes' if must_change else 'No'})")
    else:
        messages.error(request, "School user account not found.")

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == '1':
        return JsonResponse({
            'success': True,
            'udise': school.udise_code,
            'school_name': school.name,
            'password': new_password,
            'must_change': must_change,
            'message': f"Password for {school.name} updated to '{new_password}'!"
        })

    return redirect('district_dashboard')


@user_passes_test(is_district_admin_check, login_url='/login/')
@require_POST
def district_reset_school_password_generic(request):
    """Generic endpoint accepting udise_code from POST for toolbar quick password reset."""
    udise_code = request.POST.get('udise_code', '').strip()
    if not udise_code:
        messages.error(request, "Please select a school to reset password.")
        return redirect('district_dashboard')
    return district_reset_school_password(request, udise_code)


@user_passes_test(is_district_admin_check, login_url='/login/')
@require_POST
def district_edit_quota(request, udise_code):
    school = get_object_or_404(School, udise_code=udise_code)
    try:
        boys_q = int(request.POST.get('boys_quota', school.boys_quota))
        girls_q = int(request.POST.get('girls_quota', school.girls_quota))
        school.boys_quota = max(0, boys_q)
        school.girls_quota = max(0, girls_q)
        school.save()

        AuditLog.objects.create(
            school=school,
            user=request.user,
            action="QUOTA_UPDATE",
            target_type="School",
            target_id=school.udise_code,
            description=f"District admin adjusted quotas: Boys={school.boys_quota}, Girls={school.girls_quota}.",
            ip_address=get_client_ip(request)
        )
        messages.success(request, f"Quotas updated for {school.name} (Boys: {school.boys_quota}, Girls: {school.girls_quota}).")
    except Exception as e:
        messages.error(request, f"Error updating quotas: {str(e)}")

    return redirect('district_dashboard')


@user_passes_test(is_district_admin_check, login_url='/login/')
@require_POST
def district_add_school(request):
    """
    District Admin exclusive feature: Add newly sanctioned school to BSG Sangareddy.
    Only District Admin is authorized to sanction and enroll new schools.
    """
    udise_code = request.POST.get('udise_code', '').strip()
    name = request.POST.get('name', '').strip()
    mandal_id = request.POST.get('mandal_id')
    school_type = request.POST.get('school_type', SchoolType.COED_HIGH)
    sanction_order = request.POST.get('sanction_order_number', '').strip()
    hm_name = request.POST.get('headmaster_name', '').strip()
    contact_mob = request.POST.get('contact_mobile', '').strip()
    # Determine default quotas if not explicitly specified
    raw_b_q = request.POST.get('boys_quota')
    raw_g_q = request.POST.get('girls_quota')

    if raw_b_q and raw_b_q.isdigit():
        boys_quota = int(raw_b_q)
    elif school_type == SchoolType.GIRLS_HIGH:
        boys_quota = 0
    elif school_type == SchoolType.BOYS_HIGH:
        boys_quota = 32
    elif school_type in [SchoolType.PRIMARY, SchoolType.UPPER_PRIMARY]:
        boys_quota = 12
    else:
        boys_quota = 16

    if raw_g_q and raw_g_q.isdigit():
        girls_quota = int(raw_g_q)
    elif school_type == SchoolType.BOYS_HIGH:
        girls_quota = 0
    elif school_type == SchoolType.GIRLS_HIGH:
        girls_quota = 32
    elif school_type in [SchoolType.PRIMARY, SchoolType.UPPER_PRIMARY]:
        girls_quota = 12
    else:
        girls_quota = 16

    male_teacher_name = request.POST.get('male_teacher_name', '').strip()
    male_teacher_mobile = request.POST.get('male_teacher_mobile', '').strip()
    female_teacher_name = request.POST.get('female_teacher_name', '').strip()
    female_teacher_mobile = request.POST.get('female_teacher_mobile', '').strip()

    if not udise_code or not name or not mandal_id:
        messages.error(request, "UDISE code, school name, and mandal are required.")
        return redirect('district_dashboard')

    if School.objects.filter(udise_code=udise_code).exists():
        messages.error(request, f"School with UDISE '{udise_code}' is already registered in the system.")
        return redirect('district_dashboard')

    mandal = get_object_or_404(Mandal, pk=mandal_id)

    # Create school authentication user account
    user, _ = User.objects.get_or_create(
        username=udise_code,
        defaults={
            "first_name": name[:30],
            "email": f"school{udise_code}@bsg.sangareddy.org"
        }
    )
    user.set_password("BSG@Sangareddy2026")
    user.save()

    school = School.objects.create(
        udise_code=udise_code,
        name=name,
        mandal=mandal,
        school_type=school_type,
        boys_quota=boys_quota,
        girls_quota=girls_quota,
        user=user,
        must_change_password=True,
        default_password="BSG@Sangareddy2026",
        headmaster_name=hm_name,
        contact_person=hm_name,
        contact_mobile=contact_mob,
        is_sanctioned=True,
        sanction_order_number=sanction_order or "BSG/SRD/SANCTION/ADMIN-ADD",
    )

    # Automatically appoint designated male unit leader if provided (non-girls schools only)
    if male_teacher_name and school_type != SchoolType.GIRLS_HIGH:
        role = LeaderRole.CUB_MASTER if school_type in [SchoolType.PRIMARY, SchoolType.UPPER_PRIMARY] else LeaderRole.SCOUT_MASTER
        UnitLeader.objects.create(
            school=school,
            role=role,
            name=male_teacher_name,
            gender="MALE",
            mobile=male_teacher_mobile,
            uniform_size="40"
        )

    # Automatically appoint designated female unit leader if provided (non-boys schools only)
    if female_teacher_name and school_type != SchoolType.BOYS_HIGH:
        role = LeaderRole.FLOCK_LEADER if school_type in [SchoolType.PRIMARY, SchoolType.UPPER_PRIMARY] else LeaderRole.GUIDE_CAPTAIN
        UnitLeader.objects.create(
            school=school,
            role=role,
            name=female_teacher_name,
            gender="FEMALE",
            mobile=female_teacher_mobile,
            uniform_size="38"
        )

    AuditLog.objects.create(
        school=school,
        user=request.user,
        action="SANCTION_NEW_SCHOOL",
        target_type="School",
        target_id=school.udise_code,
        description=f"District Admin officially sanctioned and added '{school.name}' (UDISE: {school.udise_code}) under {mandal.name}. Ref: {school.sanction_order_number}.",
        ip_address=get_client_ip(request)
    )
    messages.success(request, f"School '{school.name}' ({school.udise_code}) officially sanctioned and added successfully! Default login credentials generated.")
    return redirect('district_dashboard')


@user_passes_test(is_district_admin_check, login_url='/login/')
def district_export_excel_view(request):
    excel_io = export_district_consolidated_excel()
    response = HttpResponse(
        excel_io.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    filename = f"BSG_Sangareddy_Master_District_Export_{datetime.now().strftime('%Y%m%d')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@user_passes_test(is_district_admin_check, login_url='/login/')
def district_export_school_excel_view(request, udise_code):
    """
    Allows District Admin to download the full, complete Excel workbook
    for a particular school containing all enrolled students, unit leaders,
    tailoring measurements, and sizing summaries.
    """
    school = get_object_or_404(School, udise_code=udise_code)
    excel_io = export_school_excel(school)
    response = HttpResponse(
        excel_io.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    clean_name = "".join(c for c in school.name if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')
    filename = f"BSG_Enrollment_{school.udise_code}_{clean_name}_{datetime.now().strftime('%Y%m%d')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    AuditLog.objects.create(
        school=school,
        user=request.user,
        action="DISTRICT_EXPORT_SCHOOL_EXCEL",
        target_type="School",
        target_id=school.udise_code,
        description=f"District Admin downloaded full school enrollment Excel workbook for '{school.name}' ({school.udise_code}).",
        ip_address=get_client_ip(request)
    )
    return response


@user_passes_test(is_district_admin_check, login_url='/login/')
def district_export_school_excel_generic(request):
    """
    Generic endpoint accepting udise_code from GET or POST query parameter
    (e.g., from toolbar quick school selector).
    """
    udise_code = request.GET.get('udise_code') or request.POST.get('udise_code', '').strip()
    if not udise_code:
        messages.error(request, "Please select a school to download the workbook.")
        return redirect('district_dashboard')
    return district_export_school_excel_view(request, udise_code)


@user_passes_test(is_district_admin_check, login_url='/login/')
def district_export_school_pdf_view(request, udise_code):
    """
    Allows District Admin to download the certified PDF roster
    for a particular school.
    """
    school = get_object_or_404(School, udise_code=udise_code)
    pdf_io = generate_school_pdf_report(school)
    response = HttpResponse(pdf_io.getvalue(), content_type="application/pdf")
    clean_name = "".join(c for c in school.name if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')
    filename = f"BSG_Roster_{school.udise_code}_{clean_name}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


@user_passes_test(is_district_admin_check, login_url='/login/')
def district_admin_account_view(request):
    """
    Allows the District Admin to update their authorized username and/or password.
    Requires verification of the current (past) password for security.
    """
    if request.method != 'POST':
        return redirect('district_dashboard')

    import re
    current_password = request.POST.get('current_password', '').strip()
    new_username = request.POST.get('new_username', '').strip()
    new_password = request.POST.get('new_password', '').strip()
    confirm_password = request.POST.get('confirm_password', '').strip()

    if not current_password or not request.user.check_password(current_password):
        messages.error(request, "Current (past) password is incorrect. Admin credentials were not modified.")
        return redirect('district_dashboard')

    changes = []
    if new_username and new_username != request.user.username:
        if len(new_username) < 4 or not re.match(r'^[a-zA-Z0-9_.-]+$', new_username):
            messages.error(request, "Admin username must be at least 4 characters (letters, numbers, _, ., - only).")
            return redirect('district_dashboard')
        if User.objects.filter(username=new_username).exclude(pk=request.user.pk).exists():
            messages.error(request, f"Username '{new_username}' is already in use. Please choose another.")
            return redirect('district_dashboard')
        old_username = request.user.username
        request.user.username = new_username
        changes.append(f"username changed from '{old_username}' to '{new_username}'")

    if new_password:
        if len(new_password) < 8:
            messages.error(request, "New admin password must be at least 8 characters long.")
            return redirect('district_dashboard')
        if new_password == 'Admin@Sangareddy2026':
            messages.error(request, "You cannot reuse the default password. Please choose a strong unique password.")
            return redirect('district_dashboard')
        if new_password != confirm_password:
            messages.error(request, "New password and confirmation do not match.")
            return redirect('district_dashboard')
        request.user.set_password(new_password)
        changes.append("password updated")

    if not changes:
        messages.info(request, "No changes were submitted to your admin account.")
        return redirect('district_dashboard')

    request.user.save()
    update_session_auth_hash(request, request.user)

    AuditLog.objects.create(
        user=request.user,
        action="ADMIN_CREDENTIAL_CHANGE",
        target_type="DistrictAdmin",
        description=f"District Admin credentials updated: {', '.join(changes)}.",
        ip_address=get_client_ip(request)
    )
    messages.success(request, f"Admin account updated successfully ({', '.join(changes)}).")
    return redirect('district_dashboard')


# ==========================================
# CIRCULARS & PHOTO GALLERY ADMIN VIEWS
# ==========================================

MAX_CIRCULAR_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_GALLERY_PHOTO_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_GALLERY_BATCH_COUNT = 10
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}


@user_passes_test(is_district_admin_check, login_url='/login/')
@require_POST
def district_upload_circular_view(request):
    title = request.POST.get('title', '').strip()
    reference_number = request.POST.get('reference_number', '').strip()
    description = request.POST.get('description', '').strip()
    issued_date_str = request.POST.get('issued_date', '').strip()
    uploaded_file = request.FILES.get('file')

    if not title:
        messages.error(request, "Circular title is required.")
        return redirect('district_dashboard')

    if not uploaded_file:
        messages.error(request, "Please select a PDF file to upload.")
        return redirect('district_dashboard')

    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext != '.pdf':
        messages.error(request, "Only PDF (.pdf) files are allowed for official circulars.")
        return redirect('district_dashboard')

    if uploaded_file.size > MAX_CIRCULAR_SIZE_BYTES:
        messages.error(request, "Circular PDF exceeds the 10 MB size limit.")
        return redirect('district_dashboard')

    header = uploaded_file.read(5)
    uploaded_file.seek(0)
    if header != b'%PDF-':
        messages.error(request, "Invalid PDF file. Please upload a genuine PDF document.")
        return redirect('district_dashboard')

    if issued_date_str:
        try:
            issued_date = datetime.strptime(issued_date_str, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, "Invalid issued date format.")
            return redirect('district_dashboard')
    else:
        issued_date = timezone.localdate()

    try:
        circular = Circular.objects.create(
            title=title,
            reference_number=reference_number,
            description=description,
            file=uploaded_file,
            issued_date=issued_date,
        )
    except Exception as exc:
        messages.error(request, f"Failed to upload circular: {exc}")
        return redirect('district_dashboard')

    AuditLog.objects.create(
        user=request.user,
        action="CIRCULAR_UPLOADED",
        target_type="Circular",
        target_id=str(circular.id),
        description=f"Uploaded circular '{circular.title}' ({circular.reference_number or 'No Ref'}).",
        ip_address=get_client_ip(request),
    )
    messages.success(request, f"Circular '{circular.title}' published to landing page.")
    return redirect('district_dashboard')


@user_passes_test(is_district_admin_check, login_url='/login/')
@require_POST
def district_toggle_circular_view(request, circular_id):
    circular = get_object_or_404(Circular, id=circular_id)
    circular.is_active = not circular.is_active
    circular.save(update_fields=['is_active'])
    state = "visible" if circular.is_active else "hidden"
    messages.success(request, f"Circular '{circular.title}' is now {state} on the landing page.")
    return redirect('district_dashboard')


@user_passes_test(is_district_admin_check, login_url='/login/')
@require_POST
def district_delete_circular_view(request, circular_id):
    circular = get_object_or_404(Circular, id=circular_id)
    title = circular.title
    try:
        if circular.file:
            circular.file.delete(save=False)
    except Exception:
        pass
    circular.delete()
    AuditLog.objects.create(
        user=request.user,
        action="CIRCULAR_DELETED",
        target_type="Circular",
        target_id=str(circular_id),
        description=f"Deleted circular '{title}'.",
        ip_address=get_client_ip(request),
    )
    messages.success(request, f"Circular '{title}' deleted.")
    return redirect('district_dashboard')


@user_passes_test(is_district_admin_check, login_url='/login/')
@require_POST
def district_upload_gallery_photos_view(request):
    event_name = request.POST.get('event_name', '').strip()
    title = request.POST.get('title', '').strip()
    event_date_str = request.POST.get('event_date', '').strip()
    photos = request.FILES.getlist('photos')

    if not event_name:
        messages.error(request, "Event name is required to group gallery photos.")
        return redirect('district_dashboard')

    if not photos:
        messages.error(request, "Please select at least one photo to upload.")
        return redirect('district_dashboard')

    if len(photos) > MAX_GALLERY_BATCH_COUNT:
        messages.error(request, f"You can upload up to {MAX_GALLERY_BATCH_COUNT} photos at a time.")
        return redirect('district_dashboard')

    event_date = None
    if event_date_str:
        try:
            event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, "Invalid event date format.")
            return redirect('district_dashboard')

    for photo in photos:
        ext = os.path.splitext(photo.name)[1].lower()
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            messages.error(request, f"'{photo.name}' is not a supported image (JPG, PNG, WEBP only).")
            return redirect('district_dashboard')
        if photo.size > MAX_GALLERY_PHOTO_SIZE_BYTES:
            messages.error(request, f"'{photo.name}' exceeds the 5 MB photo size limit.")
            return redirect('district_dashboard')

    created_count = 0
    try:
        for photo in photos:
            GalleryPhoto.objects.create(
                event_name=event_name,
                title=title,
                event_date=event_date,
                photo=photo,
            )
            created_count += 1
    except Exception as exc:
        messages.error(request, f"Failed to upload photos: {exc}")
        return redirect('district_dashboard')

    AuditLog.objects.create(
        user=request.user,
        action="GALLERY_UPLOADED",
        target_type="GalleryPhoto",
        description=f"Uploaded {created_count} photo(s) under event '{event_name}'.",
        ip_address=get_client_ip(request),
    )
    messages.success(request, f"Uploaded {created_count} photo(s) to '{event_name}'.")
    return redirect('district_dashboard')


@user_passes_test(is_district_admin_check, login_url='/login/')
@require_POST
def district_toggle_gallery_photo_view(request, photo_id):
    gp = get_object_or_404(GalleryPhoto, id=photo_id)
    gp.is_active = not gp.is_active
    gp.save(update_fields=['is_active'])
    state = "visible" if gp.is_active else "hidden"
    messages.success(request, f"Photo from '{gp.event_name}' is now {state} on the landing page.")
    return redirect('district_dashboard')


@user_passes_test(is_district_admin_check, login_url='/login/')
@require_POST
def district_delete_gallery_photo_view(request, photo_id):
    gp = get_object_or_404(GalleryPhoto, id=photo_id)
    event_name = gp.event_name
    try:
        if gp.photo:
            gp.photo.delete(save=False)
    except Exception:
        pass
    gp.delete()
    AuditLog.objects.create(
        user=request.user,
        action="GALLERY_DELETED",
        target_type="GalleryPhoto",
        target_id=str(photo_id),
        description=f"Deleted gallery photo from '{event_name}'.",
        ip_address=get_client_ip(request),
    )
    messages.success(request, f"Photo from '{event_name}' deleted.")
    return redirect('district_dashboard')


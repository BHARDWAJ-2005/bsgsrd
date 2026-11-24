from .models import Mandal, School, Student, DistrictNotice

def bsg_global_context(request):
    lang = request.GET.get('lang')
    if lang in ['en', 'te']:
        request.session['lang'] = lang
    else:
        lang = request.session.get('lang', 'en')

    # Cached counts for performance (only sanctioned BSG schools)
    total_mandals = Mandal.objects.filter(schools__is_sanctioned=True).distinct().count()
    total_schools = School.objects.filter(is_sanctioned=True).count()
    total_enrolled = Student.objects.filter(school__is_sanctioned=True).count()
    total_boys = Student.objects.filter(school__is_sanctioned=True, gender='BOY').count()
    total_girls = Student.objects.filter(school__is_sanctioned=True, gender='GIRL').count()

    active_notices = DistrictNotice.objects.filter(is_active=True).order_by('-created_at')[:3]

    school_profile = None
    if request.user.is_authenticated:
        if hasattr(request.user, 'school_profile'):
            school_profile = request.user.school_profile

    return {
        'current_lang': lang,
        'global_mandals_count': total_mandals,
        'global_schools_count': total_schools,
        'global_enrolled_count': total_enrolled,
        'global_boys_count': total_boys,
        'global_girls_count': total_girls,
        'active_notices': active_notices,
        'user_school': school_profile,
        'is_district_admin': request.user.is_authenticated and (request.user.is_superuser or request.user.is_staff),
    }

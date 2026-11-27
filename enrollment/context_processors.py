from django.core.cache import cache
from django.db.models import Count, Q
from .models import Mandal, School, Student, DistrictNotice


def _get_cached_global_stats():
    """Cache global portal counters for 15s to avoid 6 COUNT queries per page load."""
    def _compute():
        student_agg = Student.objects.filter(school__is_sanctioned=True).aggregate(
            total=Count('id'),
            boys=Count('id', filter=Q(gender='BOY')),
            girls=Count('id', filter=Q(gender='GIRL')),
        )
        return {
            'total_mandals': Mandal.objects.filter(schools__is_sanctioned=True).distinct().count(),
            'total_schools': School.objects.filter(is_sanctioned=True).count(),
            'total_enrolled': student_agg['total'] or 0,
            'total_boys': student_agg['boys'] or 0,
            'total_girls': student_agg['girls'] or 0,
            'active_notices': list(DistrictNotice.objects.filter(is_active=True).order_by('-created_at')[:3]),
        }

    return cache.get_or_set('bsg_global_context_stats', _compute, 15)


def bsg_global_context(request):
    lang = request.GET.get('lang')
    if lang in ['en', 'te']:
        request.session['lang'] = lang
    else:
        lang = request.session.get('lang', 'en')

    stats = _get_cached_global_stats()

    school_profile = None
    if request.user.is_authenticated:
        if hasattr(request.user, 'school_profile'):
            school_profile = request.user.school_profile

    return {
        'current_lang': lang,
        'global_mandals_count': stats['total_mandals'],
        'global_schools_count': stats['total_schools'],
        'global_enrolled_count': stats['total_enrolled'],
        'global_boys_count': stats['total_boys'],
        'global_girls_count': stats['total_girls'],
        'active_notices': stats['active_notices'],
        'user_school': school_profile,
        'is_district_admin': request.user.is_authenticated and (request.user.is_superuser or request.user.is_staff),
    }

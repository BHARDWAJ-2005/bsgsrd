from django.contrib import admin
from .models import District, Mandal, School, Student, UnitLeader, AuditLog, DistrictNotice, Circular, GalleryPhoto

@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'created_at')

@admin.register(Mandal)
class MandalAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'district')
    list_filter = ('district',)
    search_fields = ('name', 'code')

@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ('udise_code', 'name', 'mandal', 'school_type', 'boys_quota', 'girls_quota', 'must_change_password')
    list_filter = ('school_type', 'mandal', 'must_change_password')
    search_fields = ('udise_code', 'name')

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('name', 'gender', 'class_level', 'school', 'uniform_size', 'shoe_size', 'detail_level', 'created_at')
    list_filter = ('gender', 'class_level', 'detail_level', 'school__mandal')
    search_fields = ('name', 'father_name', 'school__name', 'school__udise_code')

@admin.register(UnitLeader)
class UnitLeaderAdmin(admin.ModelAdmin):
    list_display = ('name', 'role', 'gender', 'school', 'mobile', 'uniform_size')
    list_filter = ('role', 'gender')
    search_fields = ('name', 'school__name')

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'action', 'school', 'user', 'target_type', 'description')
    list_filter = ('action', 'target_type')
    search_fields = ('description', 'target_id', 'school__name')

@admin.register(DistrictNotice)
class DistrictNoticeAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_active', 'created_at')
    list_filter = ('is_active',)


@admin.register(Circular)
class CircularAdmin(admin.ModelAdmin):
    list_display = ('title', 'reference_number', 'issued_date', 'is_active', 'created_at')
    list_filter = ('is_active', 'issued_date')
    search_fields = ('title', 'reference_number')


@admin.register(GalleryPhoto)
class GalleryPhotoAdmin(admin.ModelAdmin):
    list_display = ('event_name', 'title', 'event_date', 'is_active', 'created_at')
    list_filter = ('is_active', 'event_name')
    search_fields = ('event_name', 'title')

from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    path('change-password/', views.change_password_view, name='change_password'),
    path('help/', views.help_view, name='help'),
    path('contact/', views.contact_view, name='contact'),

    # APIs
    path('api/schools-by-mandal/', views.api_schools_by_mandal, name='api_schools_by_mandal'),
    path('api/schools/<str:udise_code>/hint/', views.api_school_verification_hint, name='api_school_verification_hint'),
    path('api/live-stats/', views.api_live_stats, name='api_live_stats'),

    # School Dashboard & Operations
    path('dashboard/', views.school_dashboard_view, name='school_dashboard'),
    path('students/enroll/', views.enroll_student_view, name='enroll_student'),
    path('students/<int:student_id>/json/', views.get_student_json, name='get_student_json'),
    path('students/<int:student_id>/edit/', views.edit_student_view, name='edit_student'),
    path('students/<int:student_id>/delete/', views.delete_student_view, name='delete_student'),

    # Unit Leaders (Admin Controlled & Measurements)
    path('api/schools/<int:school_id>/leaders/', views.api_get_school_leaders, name='api_get_school_leaders'),
    path('leaders/save/', views.save_leader_view, name='save_leader'),
    path('leaders/<int:leader_id>/measurements/', views.update_leader_measurements_view, name='update_leader_measurements'),
    path('leaders/<int:leader_id>/delete/', views.delete_leader_view, name='delete_leader'),

    # Import / Export
    path('export/template/', views.export_excel_template_view, name='export_excel_template'),
    path('import/excel/', views.import_excel_view, name='import_excel'),
    path('export/excel/', views.export_school_excel_view, name='export_school_excel'),
    path('export/pdf/', views.export_school_pdf_view, name='export_school_pdf'),

    # District Admin
    path('district/', views.district_dashboard_view, name='district_dashboard'),
    path('district/schools/add/', views.district_add_school, name='district_add_school'),
    path('district/schools/reset-password/', views.district_reset_school_password_generic, name='district_reset_school_password_generic'),
    path('district/schools/<str:udise_code>/reset-password/', views.district_reset_school_password, name='district_reset_school_password'),
    path('district/schools/<str:udise_code>/edit-quota/', views.district_edit_quota, name='district_edit_quota'),
    path('district/schools/export/excel/', views.district_export_school_excel_generic, name='district_export_school_excel_generic'),
    path('district/schools/<str:udise_code>/export/excel/', views.district_export_school_excel_view, name='district_export_school_excel'),
    path('district/schools/<str:udise_code>/export/pdf/', views.district_export_school_pdf_view, name='district_export_school_pdf'),
    path('district/export/excel/', views.district_export_excel_view, name='district_export_excel'),
]

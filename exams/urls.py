from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('exam/<int:exam_id>/', views.take_exam, name='take_exam'),
    path('result/<int:result_id>/', views.result_page, name='result'),
    path('teacher/', views.teacher_dashboard, name='teacher_dashboard'),
    path('teacher/export-results/', views.export_results_csv, name='export_results_csv'),
    path('teacher/create-exam/', views.create_exam, name='create_exam'),
    path('subjects/', views.subject_list, name='subject_list'),
    path('subjects/create/', views.subject_create, name='subject_create'),
    path('subjects/<int:subject_id>/edit/', views.subject_edit, name='subject_edit'),
    path('subjects/<int:subject_id>/delete/', views.subject_delete, name='subject_delete'),
    path('profile/', views.profile_view, name='profile'),
    path('teacher/exam/<int:exam_id>/questions/', views.question_create, name='question_create'),
    path('teacher/grade-text/', views.grade_text_answers, name='grade_text_answers'),
    path('teacher/grade-text/<int:answer_id>/', views.grade_single_answer, name='grade_single_answer'),
    path('teacher/exam/<int:exam_id>/questions/import/', views.question_import, name='question_import'),
    path('teacher/exam/<int:exam_id>/analytics/', views.question_analytics, name='question_analytics'),
]
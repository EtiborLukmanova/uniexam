from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('exam/<int:exam_id>/', views.take_exam, name='take_exam'),
    path('result/<int:result_id>/', views.result_page, name='result'),
    path('teacher/', views.teacher_dashboard, name='teacher_dashboard'),
    path('teacher/export-results/', views.export_results_csv, name='export_results_csv'),
    path('teacher/create-exam/', views.create_exam, name='create_exam'),
    path('api/', include('exams.api_urls')),
    path('dashboard/', views.DashboardAPIView.as_view()),
] 
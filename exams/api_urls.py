from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    SubjectViewSet,
    ExamViewSet,
    QuestionViewSet,
    ChoiceViewSet,
    ResultViewSet,
    StudentAnswerViewSet,
    TestCaseViewSet,
    DashboardAPIView,
)

router = DefaultRouter()

router.register(r'subjects', SubjectViewSet)
router.register(r'exams', ExamViewSet)
router.register(r'questions', QuestionViewSet)
router.register(r'choices', ChoiceViewSet)
router.register(r'results', ResultViewSet, basename='result')
router.register(r'answers', StudentAnswerViewSet)
router.register(r'testcases', TestCaseViewSet)

urlpatterns = [
    path('dashboard/', DashboardAPIView.as_view()),
]

urlpatterns += router.urls
import csv
import subprocess
import sys
import sqlite3
import ast
import re
import requests
import json

from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Sum, Q, Prefetch
from django.contrib.auth.models import User
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend

from .models import Profile, Exam, Result, Question, Choice, Subject, StudentAnswer, TestCase
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes as drf_permission_classes
from rest_framework.response import Response
from .serializers import ExamSerializer, QuestionSerializer, SubjectSerializer, ChoiceSerializer, ResultSerializer, StudentAnswerSerializer, TestCaseSerializer
from rest_framework import viewsets
from rest_framework.views import APIView


def home(request):
    return render(request, 'exams/home.html')


@login_required
def dashboard(request):
    profile = Profile.objects.filter(user=request.user).first()
    if profile and profile.role == 'teacher':
        return redirect('teacher_dashboard')
    query = request.GET.get('q', '').strip()
    now = timezone.now()

    exams_queryset = Exam.objects.filter(is_active=True).order_by('title')

    if query:
        exams_queryset = exams_queryset.filter(
            Q(title__icontains=query) |
            Q(subject__name__icontains=query) |
            Q(subject__code__icontains=query)
        )

    subjects = Subject.objects.filter(
        exam__in=exams_queryset
    ).distinct().prefetch_related(
        Prefetch('exam_set', queryset=exams_queryset, to_attr='filtered_exams')
    ).order_by('name')

    results_list = Result.objects.filter(
        student=request.user
    ).select_related('exam', 'exam__subject').order_by('-submitted_at')

    completed_exam_ids = set(results_list.values_list('exam_id', flat=True))

    paginator = Paginator(results_list, 5)
    page_number = request.GET.get('page')
    results = paginator.get_page(page_number)

    profile = Profile.objects.filter(user=request.user).first()

    context = {
        'subjects': subjects,
        'results': results,
        'completed_exam_ids': completed_exam_ids,
        'query': query,
        'now': now,
        'profile': profile,
    }

    return render(request, 'exams/dashboard.html', context)


DANGEROUS_MODULES = re.compile(
    r'\b(os|sys|subprocess|importlib|shutil|socket|__import__|builtins|eval|exec|open|compile)\b'
)

def run_python_code(code, input_data):
    """
    Run student-submitted Python code safely.
    Rejects code that imports dangerous modules.
    """
    if DANGEROUS_MODULES.search(code):
        return "Error: Use of restricted modules is not allowed."

    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            input=input_data,
            text=True,
            capture_output=True,
            timeout=3,
            env={"PATH": "/usr/bin:/bin"},
        )

        if result.stderr:
            return result.stderr.strip()

        return result.stdout.strip()

    except subprocess.TimeoutExpired:
        return "Time Limit Exceeded"


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def get_location(ip):
    try:
        response = requests.get(f"http://ip-api.com/json/{ip}", timeout=3)
        data = response.json()

        if data.get("status") == "success":
            return f"{data.get('country')}, {data.get('city')}"
        return "Unknown location"

    except Exception:
        return "Location fetch failed"


def normalize_sql_result(rows):
    normalized = []

    for row in rows:
        normalized_row = tuple(str(value).strip() for value in row)
        normalized.append(normalized_row)

    return sorted(normalized)


def run_sql_query(student_sql, setup_sql):
    """
    Run a student SQL query safely.
    Only allows SELECT statements to prevent destructive SQL.
    """
    stripped = student_sql.strip().rstrip(';')

    if not re.match(r'^\s*SELECT\b', stripped, re.IGNORECASE):
        return "SQL Error: Only SELECT statements are allowed."

    if ';' in stripped:
        return "SQL Error: Only a single statement is allowed."

    try:
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()

        cursor.executescript(setup_sql)
        cursor.execute(stripped)

        rows = cursor.fetchall()
        conn.close()

        return normalize_sql_result(rows)

    except Exception as e:
        return f"SQL Error: {str(e)}"


@login_required
def take_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)

    entered_code = request.POST.get("code") or request.session.get(f"exam_code_{exam_id}")

    if request.method == "GET":
        get_code = request.GET.get("code")
        if get_code:
            request.session[f"exam_code_{exam_id}"] = get_code
            entered_code = get_code

    if exam.access_code and entered_code != exam.access_code:
        messages.error(request, "Invalid exam access code.")
        return redirect('dashboard')

    profile = Profile.objects.filter(user=request.user).first()

    if not profile or profile.role != 'student':
        messages.error(request, "Only students can take exams.")
        return redirect('teacher_dashboard')

    if Result.objects.filter(student=request.user, exam=exam).exists():
        messages.warning(request, "You have already completed this exam.")
        return redirect('dashboard')

    now = timezone.now()

    if exam.start_time and now < exam.start_time:
        messages.warning(request, "This exam has not started yet.")
        return redirect('dashboard')

    if exam.end_time and now > exam.end_time:
        messages.error(request, "This exam deadline has passed.")
        return redirect('dashboard')

     
    questions = Question.objects.filter(exam=exam).order_by('id')

    if request.method == "POST":
        score = 0
        total = 0

        ip = get_client_ip(request)
        location = get_location(ip)

        result = Result.objects.create(
            student=request.user,
            exam=exam,
            score=0,
            total=0,
            ip_address=ip,
            location=location
        )

        for question in questions:
            if question.question_type != "text":
                total += question.points

            selected_choice = None
            text_answer = ""
            code_answer = ""
            actual_output = ""
            passed_tests = 0
            total_tests = 0
            is_correct = False
            is_reviewed = False

            if question.question_type == "mcq":
                selected_choice_id = request.POST.get(f"question_{question.id}")

                if selected_choice_id:
                    selected_choice = Choice.objects.filter(id=selected_choice_id).first()

                    if selected_choice and selected_choice.is_correct:
                        score += question.points
                        is_correct = True

                is_reviewed = True

            elif question.question_type == "text":
                text_answer = request.POST.get(f"text_{question.id}", "")
                is_reviewed = False

            elif question.question_type == "code":
                code_answer = request.POST.get(f"code_{question.id}", "")

                test_cases = question.test_cases.all()
                total_tests = test_cases.count()
                output_logs = []

                for test in test_cases:
                    test_output = run_python_code(code_answer, test.input_data)

                    output_logs.append(
                        f"Input:\n{test.input_data}\n\n"
                        f"Expected Output:\n{test.expected_output.strip()}\n\n"
                        f"Actual Output:\n{test_output}\n"
                    )

                    if test_output.strip() == test.expected_output.strip():
                        passed_tests += 1

                actual_output = "\n\n--------------------\n\n".join(output_logs)

                if total_tests > 0:
                    earned_points = int((passed_tests / total_tests) * question.points)
                    score += earned_points

                is_correct = total_tests > 0 and passed_tests == total_tests
                is_reviewed = True

            elif question.question_type == "sql":
                code_answer = request.POST.get(f"code_{question.id}", "")

                test_cases = question.test_cases.all()
                total_tests = test_cases.count()
                output_logs = []

                for test in test_cases:
                    test_output = run_sql_query(code_answer, test.setup_sql)

                    try:
                        expected = ast.literal_eval(test.expected_output.strip())
                        expected = normalize_sql_result(expected)

                        if test_output == expected:
                            passed_tests += 1

                    except Exception:
                        expected = "Invalid expected output format"

                    output_logs.append(
                        f"Expected Output:\n{expected}\n\n"
                        f"Actual Output:\n{test_output}\n"
                    )

                actual_output = "\n\n--------------------\n\n".join(output_logs)

                if total_tests > 0:
                    earned_points = int((passed_tests / total_tests) * question.points)
                    score += earned_points

                is_correct = total_tests > 0 and passed_tests == total_tests
                is_reviewed = True

            StudentAnswer.objects.create(
                result=result,
                question=question,
                selected_choice=selected_choice,
                text_answer=text_answer,
                code_answer=code_answer,
                actual_output=actual_output,
                passed_tests=passed_tests,
                total_tests=total_tests,
                is_correct=is_correct,
                is_reviewed=is_reviewed
            )

        result.score = score
        result.total = total
        result.save()

        request.session.pop(f"exam_code_{exam_id}", None)

        return redirect('result', result_id=result.id)

    return render(request, 'exams/take_exam.html', {
        'exam': exam,
        'questions': questions
    })


@login_required
def result_page(request, result_id):
    result = get_object_or_404(Result, id=result_id, student=request.user)
    answers = result.answers.all()

    return render(request, 'exams/result.html', {
        'result': result,
        'answers': answers
    })


@login_required
def teacher_dashboard(request):
    profile = Profile.objects.filter(user=request.user).first()

    if not profile or profile.role != 'teacher':
        return redirect('dashboard')

    query = request.GET.get('q', '').strip()

    total_students = Profile.objects.filter(role='student').count()
    total_exams = Exam.objects.count()
    total_results = Result.objects.count()

    average_score = Result.objects.aggregate(avg=Avg('score'))['avg']

    exam_stats = Exam.objects.annotate(
        attempts=Count('result'),
        avg_score=Avg('result__score')
    ).order_by('title')

    top_students = User.objects.filter(result__isnull=False).annotate(
        total_score=Sum('result__score'),
        exams_taken=Count('result')
    ).order_by('-total_score')[:5]

    recent_results = Result.objects.select_related(
        'student', 'exam', 'exam__subject'
    ).order_by('-submitted_at')

    if query:
        exam_stats = exam_stats.filter(
            Q(title__icontains=query) |
            Q(subject__name__icontains=query) |
            Q(subject__code__icontains=query)
        )

        recent_results = recent_results.filter(
            Q(student__username__icontains=query) |
            Q(exam__title__icontains=query) |
            Q(exam__subject__name__icontains=query) |
            Q(exam__subject__code__icontains=query)
        )

    recent_results = recent_results[:10]
    exam_labels_json = json.dumps([exam.title for exam in exam_stats])
    exam_scores_json = json.dumps([
        float(exam.avg_score or 0) for exam in exam_stats
    ])
    context = {
        'total_students': total_students,
        'total_exams': total_exams,
        'total_results': total_results,
        'average_score': round(average_score or 0, 2),
        'exam_stats': exam_stats,
        'top_students': top_students,
        'recent_results': recent_results,
        'query': query,
        'exam_labels_json': exam_labels_json,
        'exam_scores_json': exam_scores_json
    }

    return render(request, 'exams/teacher_dashboard.html', context)


@login_required
def export_results_csv(request):
    if not request.user.is_staff:
        return redirect('dashboard')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="exam_results.csv"'

    writer = csv.writer(response)
    writer.writerow(['Student', 'Exam', 'Subject', 'Score', 'Total', 'Submitted At'])

    results = Result.objects.select_related('student', 'exam', 'exam__subject').all()

    for result in results:
        writer.writerow([
            result.student.username,
            result.exam.title,
            result.exam.subject.name,
            result.score,
            result.total,
            result.submitted_at
        ])

    return response


@login_required
def create_exam(request):
    profile = Profile.objects.filter(user=request.user).first()

    if not profile or profile.role != 'teacher':
        return redirect('dashboard')

    if request.method == 'POST':
        title = request.POST.get('title')
        subject_id = request.POST.get('subject')
        duration = request.POST.get('duration')

        subject = get_object_or_404(Subject, id=subject_id)

        Exam.objects.create(
            title=title,
            subject=subject,
            duration_minutes=duration,
            created_by=request.user
        )

        return redirect('teacher_dashboard')

    subjects = Subject.objects.all()

    return render(request, 'exams/create_exam.html', {'subjects': subjects})


@api_view(['GET'])
@drf_permission_classes([IsAuthenticated])
def subject_list(request):
    subjects = Subject.objects.all()
    serializer = SubjectSerializer(subjects, many=True)
    return Response(serializer.data)


class SubjectViewSet(viewsets.ModelViewSet):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    permission_classes = [IsAuthenticated]  


class ExamViewSet(viewsets.ModelViewSet):
    queryset = Exam.objects.all()
    serializer_class = ExamSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['subject', 'is_active']


class QuestionViewSet(viewsets.ModelViewSet):
    queryset = Question.objects.all()
    serializer_class = QuestionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['exam', 'question_type']


class ChoiceViewSet(viewsets.ModelViewSet):
    queryset = Choice.objects.all()
    serializer_class = ChoiceSerializer
    permission_classes = [IsAuthenticated]


class ResultViewSet(viewsets.ModelViewSet):
    serializer_class = ResultSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['exam']

    def get_queryset(self):
        if self.request.user.is_staff:
            return Result.objects.all()
        return Result.objects.filter(student=self.request.user)


class StudentAnswerViewSet(viewsets.ModelViewSet):
    queryset = StudentAnswer.objects.all()
    serializer_class = StudentAnswerSerializer
    permission_classes = [IsAuthenticated]


class TestCaseViewSet(viewsets.ModelViewSet):
    queryset = TestCase.objects.all()
    serializer_class = TestCaseSerializer
    permission_classes = [IsAuthenticated]


class DashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = {
            "subjects": Subject.objects.count(),
            "exams": Exam.objects.count(),
            "questions": Question.objects.count(),
            "students": User.objects.count(),
            "results": Result.objects.count(),
        }

        return Response(data)

from django.db import models
from django.contrib.auth.models import User


class Profile(models.Model):
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('admin', 'Admin'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    university_id = models.CharField(max_length=30, blank=True)
    group_name = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return self.user.username


class Subject(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.code} - {self.name}"


class Exam(models.Model):
    title = models.CharField(max_length=200)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)    
    duration_minutes = models.IntegerField(default=30)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    access_code = models.CharField(max_length=50, blank=True)
    
    def __str__(self):
        return self.title


class Question(models.Model):
    QUESTION_TYPES = (
        ('mcq', 'Multiple Choice'),
        ('text', 'Text Answer'),
        ('code', 'Coding Question'),
        ('sql', 'SQL Query Question'),
    )

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    text = models.TextField()
    question_type = models.CharField(
        max_length=20,
        choices=QUESTION_TYPES,
        default='mcq'
    )
    points = models.IntegerField(default=1)

    sample_input = models.TextField(blank=True)
    sample_output = models.TextField(blank=True)

    def __str__(self):
        return self.text[:50]


class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    text = models.CharField(max_length=300)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.text


class Result(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    score = models.IntegerField(default=0)
    total = models.IntegerField(default=0)
    submitted_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.CharField(max_length=50, blank=True)
    location = models.CharField(max_length=255, blank=True)

    def percentage(self):
        if self.total == 0:
            return 0
        return round((self.score / self.total) * 100, 2)

    def is_passed(self):
        return self.percentage() >= 60

    def __str__(self):
        return f"{self.student.username} - {self.exam.title}"


    class Meta:
        unique_together = ('student', 'exam')
        

class StudentAnswer(models.Model):
    result = models.ForeignKey(Result, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_choice = models.ForeignKey(Choice, on_delete=models.CASCADE, null=True, blank=True)
    text_answer = models.TextField(blank=True)
    code_answer = models.TextField(blank=True)
    is_correct = models.BooleanField(default=False)
    is_reviewed = models.BooleanField(default=False)
    actual_output = models.TextField(blank=True)
    passed_tests = models.IntegerField(default=0)
    total_tests = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.result.student.username} - {self.question.text[:30]}"


class TestCase(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='test_cases')
    input_data = models.TextField(blank=True)
    expected_output = models.TextField()
    setup_sql = models.TextField(blank=True)
    is_hidden = models.BooleanField(default=True)

    def __str__(self):
        return f"Test case for {self.question.text[:30]}"
from rest_framework import serializers
from .models import Subject, Exam,  Question, Choice, Result, StudentAnswer, TestCase


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = '__all__'


class ExamSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(
        source='subject.name',
        read_only=True
    )

    created_by_username = serializers.CharField(
        source='created_by.username',
        read_only=True
    )

    class Meta:
        model = Exam
        fields = '__all__'


class QuestionSerializer(serializers.ModelSerializer):
    exam_title = serializers.CharField(
        source = 'exam.title',
        read_only=True
    )

    class Meta:
        model = Question
        fields = '__all__'


class ChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Choice
        fields = '__all__'


class ResultSerializer(serializers.ModelSerializer):
    student_username = serializers.CharField(
        source='student.username',
        read_only=True
    )

    exam_title = serializers.CharField(
        source='exam.title',
        read_only=True
    )

    class Meta:
        model = Result
        fields = '__all__'


class StudentAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentAnswer
        fields = '__all__'


class TestCaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestCase
        fields = '__all__'
from django.contrib import admin
from .models import Profile, Exam, Question, Choice, Result, Subject, StudentAnswer, TestCase

admin.site.register(Profile)
admin.site.register(Subject)
admin.site.register(Exam)
admin.site.register(Question)
admin.site.register(Choice)
@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ('student', 'exam', 'score', 'ip_address', 'location', 'submitted_at')
admin.site.register(StudentAnswer)
admin.site.register(TestCase)
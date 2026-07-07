from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from .models import Profile, Subject, Exam, Question, Choice, Result, StudentAnswer


class BaseTestCase(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(username='teacher_test', password='pass12345')
        Profile.objects.create(user=self.teacher, role='teacher')

        self.student = User.objects.create_user(username='student_test', password='pass12345')
        Profile.objects.create(user=self.student, role='student')

        self.subject = Subject.objects.create(name='Test Subject', code='TS101')
        self.exam = Exam.objects.create(
            title='Test Exam',
            subject=self.subject,
            duration_minutes=30,
            created_by=self.teacher,
            is_active=True
        )

        self.mcq_question = Question.objects.create(
            exam=self.exam, question_type='mcq', text='2+2=?', points=5
        )
        self.correct_choice = Choice.objects.create(
            question=self.mcq_question, text='4', is_correct=True
        )
        Choice.objects.create(question=self.mcq_question, text='5', is_correct=False)

        self.text_question = Question.objects.create(
            exam=self.exam, question_type='text', text='Explain OOP.', points=10
        )


class ScoringLogicTests(BaseTestCase):

    def test_text_question_points_counted_in_total(self):
        self.client.login(username='student_test', password='pass12345')

        response = self.client.post(
            reverse('take_exam', args=[self.exam.id]),
            {
                f'question_{self.mcq_question.id}': self.correct_choice.id,
                f'text_{self.text_question.id}': 'A decent OOP explanation.',
            }
        )

        result = Result.objects.get(student=self.student, exam=self.exam)

        self.assertEqual(result.total, self.mcq_question.points + self.text_question.points)

    def test_score_never_exceeds_total_after_grading(self):
        self.client.login(username='student_test', password='pass12345')
        self.client.post(
            reverse('take_exam', args=[self.exam.id]),
            {
                f'question_{self.mcq_question.id}': self.correct_choice.id,
                f'text_{self.text_question.id}': 'Some answer.',
            }
        )

        result = Result.objects.get(student=self.student, exam=self.exam)
        answer = StudentAnswer.objects.get(result=result, question=self.text_question)

        self.client.login(username='teacher_test', password='pass12345')
        self.client.post(
            reverse('grade_single_answer', args=[answer.id]),
            {'points_awarded': self.text_question.points}
        )

        result.refresh_from_db()
        self.assertLessEqual(result.score, result.total)


class DoubleSubmissionTests(BaseTestCase):

    def test_cannot_submit_exam_twice(self):
        self.client.login(username='student_test', password='pass12345')

        payload = {
            f'question_{self.mcq_question.id}': self.correct_choice.id,
            f'text_{self.text_question.id}': 'Answer.',
        }

        self.client.post(reverse('take_exam', args=[self.exam.id]), payload)
        self.client.post(reverse('take_exam', args=[self.exam.id]), payload)

        result_count = Result.objects.filter(student=self.student, exam=self.exam).count()
        self.assertEqual(result_count, 1)

    def test_cannot_grade_same_answer_twice(self):
        self.client.login(username='student_test', password='pass12345')
        self.client.post(
            reverse('take_exam', args=[self.exam.id]),
            {
                f'question_{self.mcq_question.id}': self.correct_choice.id,
                f'text_{self.text_question.id}': 'Answer.',
            }
        )

        result = Result.objects.get(student=self.student, exam=self.exam)
        answer = StudentAnswer.objects.get(result=result, question=self.text_question)

        self.client.login(username='teacher_test', password='pass12345')
        self.client.post(reverse('grade_single_answer', args=[answer.id]), {'points_awarded': 10})
        self.client.post(reverse('grade_single_answer', args=[answer.id]), {'points_awarded': 10})

        result.refresh_from_db()
        self.assertEqual(result.score, self.mcq_question.points + 10)


class PermissionTests(BaseTestCase):

    def test_student_cannot_access_teacher_dashboard(self):
        self.client.login(username='student_test', password='pass12345')
        response = self.client.get(reverse('teacher_dashboard'))
        self.assertRedirects(response, reverse('dashboard'))

    def test_student_cannot_create_exam(self):
        self.client.login(username='student_test', password='pass12345')
        response = self.client.get(reverse('create_exam'))
        self.assertRedirects(response, reverse('dashboard'))

    def test_teacher_cannot_manage_another_teachers_exam(self):
        other_teacher = User.objects.create_user(username='other_teacher', password='pass12345')
        Profile.objects.create(user=other_teacher, role='teacher')

        self.client.login(username='other_teacher', password='pass12345')
        response = self.client.get(reverse('question_create', args=[self.exam.id]))
        self.assertRedirects(response, reverse('teacher_dashboard'))

    def test_anonymous_user_redirected_from_dashboard(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)


class ExamValidationTests(BaseTestCase):
    def test_cannot_create_exam_with_empty_title(self):
        self.client.login(username='teacher_test', password='pass12345')
        response = self.client.post(reverse('create_exam'), {
            'title': '',
            'subject': self.subject.id,
            'duration': 30,
        })
        self.assertEqual(Exam.objects.filter(title='').count(), 0)

    def test_cannot_create_exam_with_negative_duration(self):
        self.client.login(username='teacher_test', password='pass12345')
        self.client.post(reverse('create_exam'), {
            'title': 'Bad Exam',
            'subject': self.subject.id,
            'duration': -5,
        })
        self.assertFalse(Exam.objects.filter(title='Bad Exam').exists())


class SubjectCRUDTests(BaseTestCase):
    def test_teacher_can_create_subject(self):
        self.client.login(username='teacher_test', password='pass12345')
        response = self.client.post(reverse('subject_create'), {
            'name': 'New Subject', 'code': 'NS101'
        })
        self.assertTrue(Subject.objects.filter(code='NS101').exists())

    def test_student_cannot_create_subject(self):
        self.client.login(username='student_test', password='pass12345')
        response = self.client.get(reverse('subject_create'))
        self.assertRedirects(response, reverse('dashboard'))

    def test_teacher_can_delete_subject(self):
        self.client.login(username='teacher_test', password='pass12345')
        extra_subject = Subject.objects.create(name='Temp', code='TMP1')
        self.client.post(reverse('subject_delete', args=[extra_subject.id]))
        self.assertFalse(Subject.objects.filter(id=extra_subject.id).exists())

    def test_student_cannot_delete_subject(self):
        self.client.login(username='student_test', password='pass12345')
        response = self.client.post(reverse('subject_delete', args=[self.subject.id]))
        self.assertTrue(Subject.objects.filter(id=self.subject.id).exists())


class ProfileTests(BaseTestCase):
    def test_user_can_update_own_profile(self):
        self.client.login(username='student_test', password='pass12345')
        self.client.post(reverse('profile'), {
            'first_name': 'Test',
            'last_name': 'Student',
            'university_id': 'U12345',
            'group_name': 'Group A',
        })
        profile = Profile.objects.get(user=self.student)
        self.assertEqual(profile.university_id, 'U12345')
        self.assertEqual(profile.group_name, 'Group A')

    def test_anonymous_cannot_access_profile(self):
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 302)


class DashboardFilterTests(BaseTestCase):
    def test_pending_filter_excludes_completed_exams(self):
        self.client.login(username='student_test', password='pass12345')

        Result.objects.create(
            student=self.student, exam=self.exam, score=5, total=15
        )

        response = self.client.get(reverse('dashboard'), {'pending': '1'})
        # The completed exam should not appear in the pending list
        subjects = response.context['subjects']
        for subject in subjects:
            exam_ids = [e.id for e in getattr(subject, 'filtered_exams', [])]
            self.assertNotIn(self.exam.id, exam_ids)

    def test_search_filters_by_title(self):
        self.client.login(username='student_test', password='pass12345')
        response = self.client.get(reverse('dashboard'), {'q': 'Test Exam'})
        self.assertEqual(response.status_code, 200)

    def test_search_no_match_returns_empty(self):
        self.client.login(username='student_test', password='pass12345')
        response = self.client.get(reverse('dashboard'), {'q': 'Nonexistent Exam XYZ'})
        subjects = list(response.context['subjects'])
        for subject in subjects:
            self.assertEqual(len(getattr(subject, 'filtered_exams', [])), 0)


class QuestionOwnershipTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.other_teacher = User.objects.create_user(username='other_teacher2', password='pass12345')
        Profile.objects.create(user=self.other_teacher, role='teacher')

    def test_other_teacher_cannot_import_questions(self):
        self.client.login(username='other_teacher2', password='pass12345')
        response = self.client.get(reverse('question_import', args=[self.exam.id]))
        self.assertRedirects(response, reverse('teacher_dashboard'))

    def test_other_teacher_cannot_view_analytics(self):
        self.client.login(username='other_teacher2', password='pass12345')
        response = self.client.get(reverse('question_analytics', args=[self.exam.id]))
        self.assertRedirects(response, reverse('teacher_dashboard'))

    def test_owner_teacher_can_import_questions(self):
        self.client.login(username='teacher_test', password='pass12345')
        response = self.client.get(reverse('question_import', args=[self.exam.id]))
        self.assertEqual(response.status_code, 200)

    def test_owner_teacher_can_view_analytics(self):
        self.client.login(username='teacher_test', password='pass12345')
        response = self.client.get(reverse('question_analytics', args=[self.exam.id]))
        self.assertEqual(response.status_code, 200)


class AccessCodeTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.protected_exam = Exam.objects.create(
            title='Protected Exam',
            subject=self.subject,
            duration_minutes=30,
            created_by=self.teacher,
            is_active=True,
            access_code='SECRET123'
        )

    def test_wrong_access_code_blocks_entry(self):
        self.client.login(username='student_test', password='pass12345')
        response = self.client.get(
            reverse('take_exam', args=[self.protected_exam.id]),
            {'code': 'WRONGCODE'}
        )
        self.assertRedirects(response, reverse('dashboard'))

    def test_correct_access_code_allows_entry(self):
        self.client.login(username='student_test', password='pass12345')
        response = self.client.get(
            reverse('take_exam', args=[self.protected_exam.id]),
            {'code': 'SECRET123'}
        )
        self.assertEqual(response.status_code, 200)

    def test_no_access_code_needed_when_exam_has_none(self):
        self.client.login(username='student_test', password='pass12345')
        response = self.client.get(reverse('take_exam', args=[self.exam.id]))
        self.assertEqual(response.status_code, 200)


class ExamDateRestrictionTests(BaseTestCase):
    def test_cannot_take_exam_before_start_time(self):
        from django.utils import timezone
        from datetime import timedelta

        future_exam = Exam.objects.create(
            title='Future Exam',
            subject=self.subject,
            duration_minutes=30,
            created_by=self.teacher,
            is_active=True,
            start_time=timezone.now() + timedelta(days=1)
        )

        self.client.login(username='student_test', password='pass12345')
        response = self.client.get(reverse('take_exam', args=[future_exam.id]))
        self.assertRedirects(response, reverse('dashboard'))

    def test_cannot_take_exam_after_end_time(self):
        from django.utils import timezone
        from datetime import timedelta

        past_exam = Exam.objects.create(
            title='Past Exam',
            subject=self.subject,
            duration_minutes=30,
            created_by=self.teacher,
            is_active=True,
            end_time=timezone.now() - timedelta(days=1)
        )

        self.client.login(username='student_test', password='pass12345')
        response = self.client.get(reverse('take_exam', args=[past_exam.id]))
        self.assertRedirects(response, reverse('dashboard'))


class MCQGradingTests(BaseTestCase):
    def test_correct_mcq_answer_awards_points(self):
        self.client.login(username='student_test', password='pass12345')
        self.client.post(
            reverse('take_exam', args=[self.exam.id]),
            {
                f'question_{self.mcq_question.id}': self.correct_choice.id,
                f'text_{self.text_question.id}': 'Answer.',
            }
        )
        result = Result.objects.get(student=self.student, exam=self.exam)
        self.assertGreaterEqual(result.score, self.mcq_question.points)

    def test_wrong_mcq_answer_awards_no_points_for_that_question(self):
        wrong_choice = Choice.objects.filter(question=self.mcq_question, is_correct=False).first()

        self.client.login(username='student_test', password='pass12345')
        self.client.post(
            reverse('take_exam', args=[self.exam.id]),
            {
                f'question_{self.mcq_question.id}': wrong_choice.id,
                f'text_{self.text_question.id}': 'Answer.',
            }
        )
        answer = StudentAnswer.objects.get(
            result__student=self.student, question=self.mcq_question
        )
        self.assertFalse(answer.is_correct)
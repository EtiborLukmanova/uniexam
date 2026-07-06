from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsTeacher(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        profile = getattr(request.user, 'profile', None)
        return profile is not None and profile.role == 'teacher'


class IsTeacherOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        profile = getattr(request.user, 'profile', None)
        return profile is not None and profile.role == 'teacher'
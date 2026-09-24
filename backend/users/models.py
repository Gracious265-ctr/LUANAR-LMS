from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user model with role-based access control."""

    class Role(models.TextChoices):
        EMPLOYEE = "employee", "Employee"
        SUPERVISOR = "supervisor", "Supervisor"
        HOD = "hod", "Head of Department"
        DEAN = "dean", "Dean"
        REGISTRAR = "registrar", "Registrar"
        DVC = "dvc", "Deputy Vice-Chancellor"
        HR = "hr", "Human Resources"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.EMPLOYEE,
    )

    def __str__(self) -> str:
        return f"{self.get_full_name()} ({self.role})"


class EmployeeProfile(models.Model):
    """HR-managed employee record linked to a user account."""

    class Category(models.TextChoices):
        ACADEMIC = "academic", "Academic"
        ADMINISTRATION = "administration", "Administration"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="employee_profile",
    )
    designation = models.CharField(max_length=200, blank=True)
    department = models.CharField(max_length=200, blank=True)
    faculty = models.CharField(
        max_length=200,
        blank=True,
        help_text="Faculty/school for the Dean's review scope (Unit 16).",
    )
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.ACADEMIC,
    )
    grade = models.CharField(max_length=20, blank=True)
    appointment_date = models.DateField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.user.get_full_name()} ({self.department or 'No department'})"
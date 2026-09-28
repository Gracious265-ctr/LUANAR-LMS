from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user model with role-based access control.

    ``role`` is a *system access level*, not a place in an approval chain. The
    three values answer only "what can this account reach in the product":
    an ordinary employee's own leave, HR's administration back office, or the
    approval desk. Who actually approves an application, and in what order, is
    HR-managed ``Team``/``ApproverRole`` data — see
    ``workflows.services.is_approver_user``.
    """

    class Role(models.TextChoices):
        EMPLOYEE = "employee", "Employee"
        APPROVER = "approver", "Approver"
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

    class Gender(models.TextChoices):
        MALE = "M", "Male"
        FEMALE = "F", "Female"

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
    gender = models.CharField(
        max_length=1,
        choices=Gender.choices,
        blank=True,
        default="",
        help_text="Used by the eligibility engine (gender-based leave rules).",
    )
    grade = models.CharField(max_length=20, blank=True)
    appointment_date = models.DateField(null=True, blank=True)
    team = models.ForeignKey(
        "workflows.Team",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="members",
        help_text=(
            "The team this employee belongs to. The team selects the approval "
            "workflow applied to their leave; blank means the employee cannot "
            "submit until HR assigns them to a team."
        ),
    )

    def __str__(self) -> str:
        return f"{self.user.get_full_name()} ({self.department or 'No department'})"
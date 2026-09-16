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

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
    """HR-managed employee record linked to a user account.

    A newly created employee is an ordinary **normal employee**: no workflow
    role, no approver status, and no team. Being able to approve something is a
    property of the configuration — a ``Section.approver`` row, or an
    institution-wide ``RoleAssignment`` — never of the account. HR assigns a
    position later, by configuring the team the employee belongs to.
    """

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
    faculty = models.CharField(
        max_length=200,
        blank=True,
        help_text="Faculty/school. Read-only reporting context; it scopes no approval and gates no approver.",
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
        "teams.Team",
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
        return f"{self.user.get_full_name()} ({self.category})"


class PasswordSetToken(models.Model):
    """One single-use secret that lets a person set their own password.

    HR creates accounts without a password (``EmployeeSerializer.create`` calls
    ``set_unusable_password()``), so before this existed a new employee had no
    way in at all: the only way to give them one was a superuser typing it into
    Django admin. This is the token that fixes that, and it is emailed like every
    other message the system sends.

    The design keeps three properties that matter more than the convenience:

    * **Only the hash is stored.** ``token_hash`` is the SHA-256 of the secret,
        so a leaked database row cannot be turned back into a usable link.
    * **One live link per account.** Issuing a new one stamps ``invalidated_at``
        on the outstanding tokens, so an older link in an old inbox stops working
        the moment HR resends. ``used_at`` stays reserved for a real consumption,
        which is what keeps "consumed" and "superseded" distinguishable.
    * **Time-boxed.** ``expires_at`` is set at issuance, and :meth:`is_usable`
        is the single definition of "still good" that the request and confirm
        paths both go through.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="password_set_tokens",
    )
    token_hash = models.CharField(
        max_length=64,
        unique=True,
        help_text="SHA-256 of the emailed secret. The secret itself is never stored.",
    )
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    invalidated_at = models.DateTimeField(null=True, blank=True)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="HR who reissued this link, or null when the user requested it themselves.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "expires_at"])]

    def __str__(self) -> str:
        return f"password-set token for {self.user_id} (expires {self.expires_at:%Y-%m-%d})"

    def is_usable(self, now=None) -> bool:
        """True while this token can still set a password."""
        from django.utils import timezone

        now = now or timezone.now()
        return (
            self.used_at is None
            and self.invalidated_at is None
            and self.expires_at > now
            and self.user.is_active
        )

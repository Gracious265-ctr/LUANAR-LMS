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


class Department(models.Model):
    """A department, which holds one or more ``workflows.Team`` rows.

    A department exists so that HR can say "the ICT Leave Team" and mean
    something a person can act on: the teams under it, the employees in it, and
    therefore who may be made an approver for any of those teams. Department used
    to be a free-text column on both sides, which made "the teams in ICT"
    something a person had to group by eye and made two departments that looked
    identical on screen.

    It carries a name and nothing else. No team, employee, workflow, or role is
    attached to it as data — those are relationships, and they are held by the
    rows that own them (``EmployeeProfile.department``, ``Team.department``).
    Storing any of them here would be a second, denormalized answer to a
    question those tables already answer.

    Two rules make a department more than a label, and both are enforced where
    the approver is written, not here:

    * only an employee **in the department** may be a team's approver;
    * one employee holds **one role across every team in the department**, so the
      same person is never the Supervisor for one ICT team and the Head of
      Department for another.

    ``is_active`` retires a department without deleting it. An application
    snapshot and a historical ``ApplicationStage`` both record the department as
    text, so retiring rather than removing is what keeps those rows renderable.
    """

    name = models.CharField(max_length=200, unique=True)
    is_active = models.BooleanField(
        default=True,
        help_text=(
            "A retired department cannot be chosen for a new team or a new "
            "employee. It is kept so historical applications still name a "
            "department that can be read."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


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
    department = models.ForeignKey(
        "users.Department",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="employees",
        help_text=(
            "The department this employee belongs to. It is what makes the "
            "employee eligible to be a team's approver: an approver must be in "
            "the same department as the team they approve for."
        ),
    )
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
        return (
            f"{self.user.get_full_name()} "
            f"({self.department.name if self.department_id else 'No department'})"
        )


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

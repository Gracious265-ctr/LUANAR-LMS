from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from leave.models import GradeEntitlement, LeaveRule, LeaveType
from users.models import EmployeeProfile

User = get_user_model()

DEV_PASSWORD = "testpass123"

USERS = [
    {
        "username": "employee@test.luanar",
        "email": "employee@test.luanar",
        "first_name": "Test",
        "last_name": "Employee",
        "role": User.Role.EMPLOYEE,
        "profile": {
            "department": "Administration",
            "designation": "Administrative Officer",
            "category": EmployeeProfile.Category.ADMINISTRATION,
            "grade": "B",
            "appointment_date": date(2022, 3, 15),
        },
    },
    {
        "username": "supervisor@test.luanar",
        "email": "supervisor@test.luanar",
        "first_name": "Test",
        "last_name": "Supervisor",
        "role": User.Role.SUPERVISOR,
        "profile": {
            "department": "Bunda College",
            "designation": "Lecturer",
            "category": EmployeeProfile.Category.ACADEMIC,
            "grade": "E",
            "appointment_date": date(2018, 9, 1),
        },
    },
    {
        "username": "hod@test.luanar",
        "email": "hod@test.luanar",
        "first_name": "Test",
        "last_name": "HOD",
        "role": User.Role.HOD,
        "profile": {
            "department": "Bunda College",
            "designation": "Head of Department",
            "category": EmployeeProfile.Category.ACADEMIC,
            "grade": "G",
            "appointment_date": date(2015, 1, 10),
        },
    },
    {
        "username": "dean@test.luanar",
        "email": "dean@test.luanar",
        "first_name": "Test",
        "last_name": "Dean",
        "role": User.Role.DEAN,
        "profile": {
            "department": "Faculty of Agriculture",
            "designation": "Dean",
            "category": EmployeeProfile.Category.ACADEMIC,
            "grade": "H",
            "appointment_date": date(2012, 6, 1),
        },
    },
    {
        "username": "registrar@test.luanar",
        "email": "registrar@test.luanar",
        "first_name": "Test",
        "last_name": "Registrar",
        "role": User.Role.REGISTRAR,
        "profile": {
            "department": "Central Administration",
            "designation": "University Registrar",
            "category": EmployeeProfile.Category.ADMINISTRATION,
            "grade": "H",
            "appointment_date": date(2010, 8, 15),
        },
    },
    {
        "username": "dvc@test.luanar",
        "email": "dvc@test.luanar",
        "first_name": "Test",
        "last_name": "DVC",
        "role": User.Role.DVC,
        "profile": {
            "department": "Central Administration",
            "designation": "Deputy Vice-Chancellor",
            "category": EmployeeProfile.Category.ADMINISTRATION,
            "grade": "H",
            "appointment_date": date(2008, 4, 1),
        },
    },
    {
        "username": "hr@test.luanar",
        "email": "hr@test.luanar",
        "first_name": "Test",
        "last_name": "HR",
        "role": User.Role.HR,
        "profile": {
            "department": "Human Resources",
            "designation": "HR Manager",
            "category": EmployeeProfile.Category.ADMINISTRATION,
            "grade": "E",
            "appointment_date": date(2019, 2, 1),
        },
    },
]


class Command(BaseCommand):
    help = "Seed development test users (one per role)"

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0

        for user_data in USERS:
            profile_data = user_data["profile"]
            user_fields = {
                key: value for key, value in user_data.items() if key != "profile"
            }
            user, created = User.objects.update_or_create(
                username=user_fields["username"],
                defaults={
                    "email": user_fields["email"],
                    "first_name": user_fields["first_name"],
                    "last_name": user_fields["last_name"],
                    "role": user_fields["role"],
                },
            )
            if created:
                user.set_password(DEV_PASSWORD)
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(f"Created user: {user.username} ({user.role})")
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f"Updated user: {user.username} ({user.role})")
                )

            if created:
                created_count += 1
            else:
                updated_count += 1

            EmployeeProfile.objects.update_or_create(
                user=user,
                defaults=profile_data,
            )

        self._seed_default_entitlements()
        self._seed_default_leave_types()

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone! Users created: {created_count}, updated: {updated_count}"
            )
        )

    def _seed_default_entitlements(self):
        """Seed the default grade/entitlement bands (idempotent)."""
        default_bands = [
            ("A", "C", 21),
            ("D", "G", 24),
            ("H", "U", 30),
        ]
        effective_from = timezone.localdate()
        created_count = 0

        for grade_start, grade_end, days in default_bands:
            _, created = GradeEntitlement.objects.get_or_create(
                grade_start=grade_start,
                grade_end=grade_end,
                effective_from=effective_from,
                defaults={"days": days},
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created entitlement: {grade_start}–{grade_end} → {days} days"
                    )
                )

        if created_count:
            self.stdout.write(self.style.SUCCESS(f"Entitlements created: {created_count}"))
    def _seed_default_leave_types(self):
        """Seed the built-in leave types and default rules (idempotent)."""
        default_rules = [
            {
                "code": "annual",
                "name": "Annual leave",
                "max_duration_days": 30,
                "consumes_annual_entitlement": True,
            },
            {
                "code": "maternity",
                "name": "Maternity leave",
                "max_duration_days": 90,
            },
            {
                "code": "paternity",
                "name": "Paternity leave",
                "max_duration_days": 10,
            },
            {
                "code": "compassionate",
                "name": "Compassionate leave",
                "max_duration_days": 5,
            },
        ]
        effective_from = timezone.localdate()
        created_count = 0

        for item in default_rules:
            leave_type, _ = LeaveType.objects.get_or_create(
                code=item["code"],
                defaults={"name": item["name"]},
            )
            _, created = LeaveRule.objects.get_or_create(
                leave_type=leave_type,
                effective_from=effective_from,
                defaults={
                    "max_duration_days": item["max_duration_days"],
                    "consumes_annual_entitlement": item.get(
                        "consumes_annual_entitlement", False
                    ),
                },
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created leave rule: {leave_type.name} → "
                        f"{item['max_duration_days']} days"
                    )
                )

        if created_count:
            self.stdout.write(self.style.SUCCESS(f"Leave rules created: {created_count}"))

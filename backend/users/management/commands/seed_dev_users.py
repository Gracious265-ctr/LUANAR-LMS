from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from users.models import EmployeeProfile

User = get_user_model()

DEV_PASSWORD = "testpass123"

# The ``department`` values below are documentation of where these people would
# sit in a real deployment. They are deliberately not applied: seeding a
# department would be business data, and HR is the one who creates departments
# through the frontend.
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
            "gender": EmployeeProfile.Gender.FEMALE,
            "grade": "B",
            "appointment_date": date(2022, 3, 15),
        },
    },
    {
        "username": "supervisor@test.luanar",
        "email": "supervisor@test.luanar",
        "first_name": "Test",
        "last_name": "Supervisor",
        "role": User.Role.APPROVER,
        "profile": {
            "department": "Bunda College",
            "designation": "Lecturer",
            "category": EmployeeProfile.Category.ACADEMIC,
            "gender": EmployeeProfile.Gender.MALE,
            "grade": "E",
            "appointment_date": date(2018, 9, 1),
        },
    },
    {
        "username": "hod@test.luanar",
        "email": "hod@test.luanar",
        "first_name": "Test",
        "last_name": "HOD",
        "role": User.Role.APPROVER,
        "profile": {
            "department": "Bunda College",
            "designation": "Head of Department",
            "category": EmployeeProfile.Category.ACADEMIC,
            "gender": EmployeeProfile.Gender.MALE,
            "grade": "G",
            "appointment_date": date(2015, 1, 10),
        },
    },
    {
        "username": "dean@test.luanar",
        "email": "dean@test.luanar",
        "first_name": "Test",
        "last_name": "Dean",
        "role": User.Role.APPROVER,
        "profile": {
            # Bunda College, not a separate "Faculty of Agriculture": under Unit
            # 10 an approver may only be appointed on a team in their own
            # department, and the dean is appointed on the Bunda College Team.
            "department": "Bunda College",
            "designation": "Dean",
            "category": EmployeeProfile.Category.ACADEMIC,
            "gender": EmployeeProfile.Gender.MALE,
            "grade": "H",
            "appointment_date": date(2012, 6, 1),
        },
    },
    {
        "username": "registrar@test.luanar",
        "email": "registrar@test.luanar",
        "first_name": "Test",
        "last_name": "Registrar",
        "role": User.Role.APPROVER,
        "profile": {
            "department": "Central Administration",
            "designation": "University Registrar",
            "category": EmployeeProfile.Category.ADMINISTRATION,
            "gender": EmployeeProfile.Gender.FEMALE,
            "grade": "H",
            "appointment_date": date(2010, 8, 15),
        },
    },
    {
        "username": "dvc@test.luanar",
        "email": "dvc@test.luanar",
        "first_name": "Test",
        "last_name": "DVC",
        "role": User.Role.APPROVER,
        "profile": {
            "department": "Central Administration",
            "designation": "Deputy Vice-Chancellor",
            "category": EmployeeProfile.Category.ADMINISTRATION,
            "gender": EmployeeProfile.Gender.FEMALE,
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
            "gender": EmployeeProfile.Gender.MALE,
            "grade": "E",
            "appointment_date": date(2019, 2, 1),
        },
    },
    # Central Administration's own supervisor and HOD. They exist because the
    # Administration Team is staffed from its own department (Unit 10): the
    # academic supervisor and HOD sit in Bunda College and so cannot be
    # appointed on this chain, which is why it needs its own pair.
    {
        "username": "admin-supervisor@test.luanar",
        "email": "admin-supervisor@test.luanar",
        "first_name": "Test",
        "last_name": "Admin",
        "role": User.Role.APPROVER,
        "profile": {
            "department": "Administration",
            "designation": "Administrative Supervisor",
            "category": EmployeeProfile.Category.ADMINISTRATION,
            "gender": EmployeeProfile.Gender.MALE,
            "grade": "E",
            "appointment_date": date(2017, 5, 1),
        },
    },
    {
        "username": "admin-hod@test.luanar",
        "email": "admin-hod@test.luanar",
        "first_name": "Test",
        "last_name": "Admin",
        "role": User.Role.APPROVER,
        "profile": {
            "department": "Administration",
            "designation": "Head of Administration",
            "category": EmployeeProfile.Category.ADMINISTRATION,
            "gender": EmployeeProfile.Gender.FEMALE,
            "grade": "H",
            "appointment_date": date(2013, 9, 1),
        },
    },
]


class Command(BaseCommand):
    help = (
        "Create development login accounts (and their empty profiles). This is a "
        "convenience for local sign-in only: it seeds no business data — no "
        "departments, roles, teams, workflows, entitlements, or leave types. Those "
        "are configured through the frontend, by a superadmin and then HR, so the "
        "application has to work from an empty database without this command."
    )

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

            # A profile carries per-person facts (designation, grade, gender),
            # not configuration. The department is deliberately left unset: a
            # seeded department would be exactly the kind of hidden business data
            # this command must not create. HR assigns departments through the
            # frontend.
            profile_defaults = dict(profile_data)
            profile_defaults.pop("department", None)
            EmployeeProfile.objects.update_or_create(
                user=user,
                defaults=profile_defaults,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone! Users created: {created_count}, updated: {updated_count}"
            )
        )

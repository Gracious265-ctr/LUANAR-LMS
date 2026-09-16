from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()

DEV_PASSWORD = "testpass123"

USERS = [
    {
        "username": "employee@test.luanar",
        "email": "employee@test.luanar",
        "first_name": "Test",
        "last_name": "Employee",
        "role": User.Role.EMPLOYEE,
    },
    {
        "username": "supervisor@test.luanar",
        "email": "supervisor@test.luanar",
        "first_name": "Test",
        "last_name": "Supervisor",
        "role": User.Role.SUPERVISOR,
    },
    {
        "username": "hod@test.luanar",
        "email": "hod@test.luanar",
        "first_name": "Test",
        "last_name": "HOD",
        "role": User.Role.HOD,
    },
    {
        "username": "dean@test.luanar",
        "email": "dean@test.luanar",
        "first_name": "Test",
        "last_name": "Dean",
        "role": User.Role.DEAN,
    },
    {
        "username": "registrar@test.luanar",
        "email": "registrar@test.luanar",
        "first_name": "Test",
        "last_name": "Registrar",
        "role": User.Role.REGISTRAR,
    },
    {
        "username": "dvc@test.luanar",
        "email": "dvc@test.luanar",
        "first_name": "Test",
        "last_name": "DVC",
        "role": User.Role.DVC,
    },
    {
        "username": "hr@test.luanar",
        "email": "hr@test.luanar",
        "first_name": "Test",
        "last_name": "HR",
        "role": User.Role.HR,
    },
]


class Command(BaseCommand):
    help = "Seed development test users (one per role)"

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0

        for user_data in USERS:
            user, created = User.objects.update_or_create(
                username=user_data["username"],
                defaults={
                    "email": user_data["email"],
                    "first_name": user_data["first_name"],
                    "last_name": user_data["last_name"],
                    "role": user_data["role"],
                },
            )
            if created:
                user.set_password(DEV_PASSWORD)
                user.save()
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"Created: {user.username} ({user.role})")
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f"Updated: {user.username} ({user.role})")
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone! Created: {created_count}, Updated: {updated_count}"
            )
        )

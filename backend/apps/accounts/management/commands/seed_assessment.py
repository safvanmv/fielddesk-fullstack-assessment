import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Membership, Organization


class Command(BaseCommand):
    help = "Create two assessment organizations and owner, dispatcher and technician users."

    @transaction.atomic
    def handle(self, *args, **options):
        password = os.environ.get("SEED_PASSWORD", "FieldDesk!2026")
        User = get_user_model()
        seed = (
            ("Northstar Maintenance", "northstar", "Northstar"),
            ("Harbor Services", "harbor", "Harbor"),
        )
        created_count = 0
        for organization_name, prefix, label in seed:
            organization, _ = Organization.objects.get_or_create(name=organization_name)
            for role in Membership.Role.values:
                username = f"{prefix}_{role}"
                user, user_created = User.objects.get_or_create(
                    username=username,
                    defaults={"email": f"{username}@example.test"},
                )
                if user_created:
                    user.set_password(password)
                    user.save(update_fields=["password"])
                    created_count += 1
                Membership.objects.get_or_create(
                    user=user, defaults={"organization": organization, "role": role}
                )
        self.stdout.write(self.style.SUCCESS(
            f"Seed complete ({created_count} users created). Sample password: {password}"
        ))

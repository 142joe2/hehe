from django.core.management.base import BaseCommand
from core_system.models import PositionRank


class Command(BaseCommand):
    help = 'Seed initial position ranks'

    def handle(self, *args, **options):
        initial_positions = [
            # Instructor Ranks
            {"name": "Instructor I", "category": "Instructor"},
            {"name": "Instructor II", "category": "Instructor"},
            {"name": "Instructor III", "category": "Instructor"},
            # Assistant Professor Ranks
            {"name": "Assistant Professor I", "category": "Assistant Professor"},
            {"name": "Assistant Professor II", "category": "Assistant Professor"},
            {"name": "Assistant Professor III", "category": "Assistant Professor"},
            {"name": "Assistant Professor IV", "category": "Assistant Professor"},
            # Associate Professor Ranks
            {"name": "Associate Professor I", "category": "Associate Professor"},
            {"name": "Associate Professor II", "category": "Associate Professor"},
            {"name": "Associate Professor III", "category": "Associate Professor"},
            {"name": "Associate Professor IV", "category": "Associate Professor"},
            {"name": "Associate Professor V", "category": "Associate Professor"},
            # Full Professor Ranks
            {"name": "Professor I", "category": "Full Professor"},
            {"name": "Professor II", "category": "Full Professor"},
            {"name": "Professor III", "category": "Full Professor"},
            {"name": "Professor IV", "category": "Full Professor"},
            {"name": "Professor V", "category": "Full Professor"},
            {"name": "Professor VI", "category": "Full Professor"},
            # Ultimate Rank
            {"name": "College / University Professor", "category": "Full Professor"},
            # Administrative
            {"name": "Department Head", "category": "Administrative"},
            {"name": "Dean", "category": "Administrative"},
            {"name": "Vice President", "category": "Administrative"},
            {"name": "President", "category": "Administrative"},
            # Staff
            {"name": "Teaching Assistant", "category": "Staff"},
            {"name": "Research Assistant", "category": "Staff"},
            {"name": "Administrative Staff", "category": "Staff"},
            {"name": "Support Staff", "category": "Staff"},
            {"name": "Staff", "category": "Staff"},
            # Other
            {"name": "Instructor", "category": "Other"},
            {"name": "Lecturer", "category": "Other"},
            {"name": "Other", "category": "Other"},
        ]

        created_count = 0
        for pos_data in initial_positions:
            obj, created = PositionRank.objects.get_or_create(
                name=pos_data["name"],
                defaults={
                    "category": pos_data["category"],
                    "is_active": True,
                }
            )
            if created:
                created_count += 1
                self.stdout.write(f'Created: {pos_data["name"]}')
            else:
                self.stdout.write(f'Already exists: {pos_data["name"]}')

        self.stdout.write(self.style.SUCCESS(f'Successfully seeded {created_count} position ranks'))

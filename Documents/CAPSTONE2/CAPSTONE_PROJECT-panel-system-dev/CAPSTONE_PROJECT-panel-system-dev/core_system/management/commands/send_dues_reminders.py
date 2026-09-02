from django.core.management.base import BaseCommand

from core_system.services.dues_reminder import run_dues_reminders


class Command(BaseCommand):
    help = "Send monthly dues reminders to overdue members per configured intervals."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show which reminders would be sent without creating notifications.",
        )

    def handle(self, *args, **options):
        result = run_dues_reminders(dry_run=bool(options["dry_run"]))
        prefix = "[DRY RUN] " if result["dry_run"] else ""
        self.stdout.write(
            f"{prefix}Dues reminders for {result['month_label']}: "
            f"{result['reminders_sent']} reminder(s) issued."
        )

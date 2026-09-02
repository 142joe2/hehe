from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q


class Command(BaseCommand):
    help = (
        "Delete push subscriptions registered under origins that are not the "
        "current production host (e.g. leftover ngrok tunnels that cause "
        "spam-branded notifications)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be deleted without deleting anything.",
        )
        parser.add_argument(
            "--purge-all",
            action="store_true",
            help="Delete every push subscription (forces a fresh re-subscribe).",
        )

    def handle(self, *args, **options):
        from core_system.models import PushSubscription

        dry_run = options["dry_run"]
        purge_all = options["purge_all"]

        host = (getattr(settings, "BASE_URL", "") or "").split("://")[-1].split("/")[0].lower()

        if purge_all:
            qs = PushSubscription.objects.all()
            label = "ALL push subscriptions"
        else:
            qs = PushSubscription.objects.filter(
                Q(origin__isnull=True) | ~Q(origin__icontains=host)
            )
            label = f"push subscriptions not tied to '{host or 'current host'}'"

        total = qs.count()
        self.stdout.write(f"Found {total} {label}.")

        if dry_run:
            self.stdout.write("Dry run — nothing deleted.")
            return

        deleted, _ = qs.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} stale push subscription(s)."))

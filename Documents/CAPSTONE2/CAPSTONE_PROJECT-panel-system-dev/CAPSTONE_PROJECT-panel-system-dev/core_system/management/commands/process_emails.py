from django.core.management.base import BaseCommand

from core_system.services.email_service import process_email_queue


class Command(BaseCommand):
    help = "Process pending emails from the OutgoingEmail queue"

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=10,
            help="Number of pending emails to process (default: 10)",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        sent = process_email_queue(batch_size=batch_size)
        if sent:
            self.stdout.write(self.style.SUCCESS(f"Sent {sent} queued email(s)."))
        else:
            self.stdout.write("No pending emails to process.")

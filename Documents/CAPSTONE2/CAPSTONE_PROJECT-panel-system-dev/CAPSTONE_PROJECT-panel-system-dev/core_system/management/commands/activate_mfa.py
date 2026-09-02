from django.core.management.base import BaseCommand

from core_system.models import OfficerUser
from core_system.services.mfa_service import generate_mfa_secret


class Command(BaseCommand):
    help = "Enable or disable MFA for an officer by username, or all officers at once."

    def add_arguments(self, parser):
        parser.add_argument("username", nargs="?", help="Officer username")
        parser.add_argument(
            "--all",
            action="store_true",
            help="Apply action to all officers",
        )
        parser.add_argument(
            "--status",
            choices=["on", "off", "toggle", "show"],
            default="on",
            help="Action: on / off / toggle / show (default: on)",
        )

    def handle(self, *args, **options):
        username = options["username"]
        all_flag = options["all"]
        action = options["status"]

        if all_flag:
            officers = OfficerUser.objects.all()
            if not officers.exists():
                self.stdout.write("No officers found.")
                return

            self.stdout.write(f"Applying MFA {action} to {officers.count()} officer(s)...")

            if action == "show":
                for officer in officers:
                    status = "ON" if officer.mfa_enabled else "OFF"
                    self.stdout.write(f"  {officer.username}: MFA {status}")
                return

            if action == "toggle":
                updated = 0
                for officer in officers:
                    officer.mfa_enabled = not officer.mfa_enabled
                    if officer.mfa_enabled and not officer.mfa_secret:
                        officer.mfa_secret = generate_mfa_secret()
                    if not officer.mfa_enabled:
                        officer.mfa_secret = None
                    officer.save(update_fields=["mfa_enabled", "mfa_secret"])
                    updated += 1
                self.stdout.write(self.style.SUCCESS(f"Toggled MFA for {updated} officer(s)."))
                return

            if action == "on":
                updated = 0
                for officer in officers:
                    if not officer.mfa_enabled:
                        officer.mfa_enabled = True
                        officer.mfa_secret = generate_mfa_secret()
                        officer.save(update_fields=["mfa_enabled", "mfa_secret"])
                        updated += 1
                self.stdout.write(self.style.SUCCESS(f"Enabled MFA for {updated} officer(s)."))
                return

            if action == "off":
                updated = 0
                for officer in officers:
                    if officer.mfa_enabled:
                        officer.mfa_enabled = False
                        officer.mfa_secret = None
                        officer.save(update_fields=["mfa_enabled", "mfa_secret"])
                        updated += 1
                self.stdout.write(self.style.SUCCESS(f"Disabled MFA for {updated} officer(s)."))
                return

            return

        if not username:
            self.stderr.write(self.style.ERROR("Provide a username or use --all."))
            return

        try:
            officer = OfficerUser.objects.get(username=username)
        except OfficerUser.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"Officer not found: {username}"))
            return

        if action == "show":
            status = "ON" if officer.mfa_enabled else "OFF"
            self.stdout.write(f"{username}: MFA {status}")
            if officer.mfa_enabled and officer.mfa_secret:
                self.stdout.write(f"Secret: {officer.mfa_secret}")
            return

        if action == "toggle":
            action = "off" if officer.mfa_enabled else "on"

        if action == "on":
            if not officer.mfa_enabled:
                officer.mfa_enabled = True
                officer.mfa_secret = generate_mfa_secret()
                officer.save(update_fields=["mfa_enabled", "mfa_secret"])
                self.stdout.write(
                    self.style.SUCCESS(f"MFA enabled for {username}. Secret: {officer.mfa_secret}")
                )
            else:
                self.stdout.write(f"MFA is already enabled for {username}.")
        elif action == "off":
            if officer.mfa_enabled:
                officer.mfa_enabled = False
                officer.mfa_secret = None
                officer.save(update_fields=["mfa_enabled", "mfa_secret"])
                self.stdout.write(self.style.SUCCESS(f"MFA disabled for {username}."))
            else:
                self.stdout.write(f"MFA is already disabled for {username}.")

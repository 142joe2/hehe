from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone

from core_system.models import (
    Member,
    SystemSetting,
)
from core_system.shared_view_utils import _record_audit_trail
from core_system.services.compliance import (
    member_dues_status,
    _get_grace_period_days,
)


class Command(BaseCommand):
    help = "Deactivate members whose overdue period exceeds the configured grace period."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show which members would be deactivated without making changes.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        today = timezone.localdate()
        grace_days = _get_grace_period_days()

        active_members = Member.objects.filter(
            membership_status__iexact="Active",
        )
        deactivated_count = 0

        for member in active_members:
            status = member_dues_status(member, today.year, today.month)
            if status != "overdue":
                continue

            due_date = date(today.year, today.month, 1)
            days_overdue = (today - due_date).days

            if days_overdue > grace_days:
                deactivated_count += 1
                if dry_run:
                    self.stdout.write(
                        f"[DRY RUN] Would deactivate: {member.full_name} "
                        f"(ID={member.member_id_PK}, overdue={days_overdue}d, "
                        f"grace={grace_days}d)"
                    )
                else:
                    old_status = member.membership_status
                    member.membership_status = "Deactivated"
                    member.save(update_fields=["membership_status"])

                    _record_audit_trail(
                        table="MEMBER",
                        record_id=member.member_id_PK,
                        action="DEACTIVATED",
                        actor=None,
                        actor_type_override="SYSTEM",
                        actor_name_override="Auto-Deactivation Cron",
                        notes=(
                            f"Auto-deactivated after {days_overdue} days overdue "
                            f"(grace period: {grace_days} days). "
                            f"Previous status: {old_status}."
                        ),
                    )

        if dry_run:
            self.stdout.write(
                f"[DRY RUN] Would deactivate {deactivated_count} member(s)."
            )
        else:
            self.stdout.write(
                f"Deactivated {deactivated_count} member(s) exceeding "
                f"{grace_days}-day grace period."
            )

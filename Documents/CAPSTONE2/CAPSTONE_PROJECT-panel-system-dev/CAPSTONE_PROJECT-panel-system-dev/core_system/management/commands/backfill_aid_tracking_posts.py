from django.core.management.base import BaseCommand
from django.utils import timezone

from core_system.constants.policy_constants import get_contribution_amount_for_aid
from core_system.models import (
    AidTrackingPost,
    Contribution,
    DeathAid,
    MedicalAid,
    Member,
    TransactionArchive,
)
from core_system.shared_view_utils import archive_transaction


APPROVED_STATUSES = {"Approved", "President Approved"}


class Command(BaseCommand):
    help = "Create missing AidTrackingPost records for approved aids that lack one."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be created without writing to the database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        medical_aids = MedicalAid.objects.filter(status__in=APPROVED_STATUSES).order_by("medical_aid_id_PK")
        death_aids = DeathAid.objects.filter(status__in=APPROVED_STATUSES).order_by("death_aid_id_PK")

        created = 0
        skipped = 0
        errors = 0

        for aid in medical_aids:
            result = self._ensure_tracking_post("medical_aid", aid.medical_aid_id_PK, aid, dry_run)
            if result == "created":
                created += 1
            elif result == "skipped":
                skipped += 1
            elif result == "error":
                errors += 1

        for aid in death_aids:
            result = self._ensure_tracking_post("death_aid", aid.death_aid_id_PK, aid, dry_run)
            if result == "created":
                created += 1
            elif result == "skipped":
                skipped += 1
            elif result == "error":
                errors += 1

        mode = "dry run" if dry_run else "completed"
        self.stdout.write(self.style.SUCCESS(
            f"Backfill {mode}: created={created}, skipped={skipped}, errors={errors}."
        ))

    def _ensure_tracking_post(self, aid_type, record_id, record, dry_run):
        existing = AidTrackingPost.objects.filter(
            aid_type=aid_type,
            archive_id_FK__record_id=record_id,
        ).exists()

        if existing:
            return "skipped"

        try:
            if dry_run:
                self.stdout.write(f"Would create AidTrackingPost for {aid_type} #{record_id}")
                return "skipped"

            archive = TransactionArchive.objects.filter(
                transaction_type=aid_type,
                record_id=record_id,
            ).first()

            if archive is None:
                archive = archive_transaction(aid_type, record_id)
                if archive is None:
                    self.stdout.write(self.style.WARNING(
                        f"Could not archive {aid_type} #{record_id}. Skipping."
                    ))
                    return "error"

            relationship = ""
            if aid_type == "death_aid":
                relationship = getattr(record, "relationship_to_member", "")

            per_member_amount = get_contribution_amount_for_aid(aid_type, relationship)
            active_members = Member.objects.exclude(
                membership_status__iexact="Retired",
            )
            total_expected = active_members.count() * per_member_amount

            post = AidTrackingPost.objects.create(
                archive_id_FK=archive,
                aid_type=aid_type,
                target_month=timezone.now().strftime("%Y-%m"),
                total_expected=total_expected,
                total_collected=0,
            )

            Contribution.objects.bulk_create([
                Contribution(
                    aid_tracking_post_id_FK=post,
                    member_id_FK=member,
                    expected_amount=per_member_amount,
                    paid_amount=0,
                    status="NOT_PAID",
                )
                for member in active_members
            ])

            self.stdout.write(self.style.SUCCESS(
                f"Created AidTrackingPost #{post.post_id_PK} for {aid_type} #{record_id}"
            ))
            return "created"

        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f"Failed to create AidTrackingPost for {aid_type} #{record_id}: {e}"
            ))
            return "error"

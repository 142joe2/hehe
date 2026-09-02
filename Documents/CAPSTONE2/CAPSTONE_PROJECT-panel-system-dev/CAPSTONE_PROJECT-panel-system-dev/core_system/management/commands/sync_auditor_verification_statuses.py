from django.core.management.base import BaseCommand
from django.db.models import Q

from core_system.constants.status_constants import Status
from core_system.models import (
    DeathAid,
    MedicalAid,
    TransactionVerification,
)

TABLE_MODEL_MAP = {
    "medical_aid": (MedicalAid, "medical_aid_id_PK", "status"),
    "death_aid": (DeathAid, "death_aid_id_PK", "status"),
}

VERIFIED_STATUSES = list(Status.ALL_AUDITOR_ACTED | Status.ALL_APPROVED | {Status.REJECTED, Status.RELEASED})


class Command(BaseCommand):
    help = "Sync model status fields to match TransactionVerification.verification_status for all auditor-processed records."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show planned updates without writing to database.",
        )
        parser.add_argument(
            "--table",
            type=str,
            choices=list(TABLE_MODEL_MAP) + ["all"],
            default="all",
            help="Only sync records for a specific table.",
        )
        parser.add_argument(
            "--status",
            type=str,
            choices=VERIFIED_STATUSES + ["all"],
            default="all",
            help="Only sync records with a specific verification status.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        table_filter = options["table"]
        status_filter = options["status"]

        q = Q(auditor_id_FK__isnull=False)
        if status_filter != "all":
            q &= Q(verification_status=status_filter)

        tvs = TransactionVerification.objects.filter(q).order_by("table_name", "record_id")

        updated = 0
        skipped = 0
        errors = 0

        for tv in tvs:
            tn = tv.table_name
            rid = tv.record_id
            target_status = tv.verification_status

            if table_filter != "all" and tn != table_filter:
                continue

            if target_status not in VERIFIED_STATUSES:
                skipped += 1
                continue

            model_info = TABLE_MODEL_MAP.get(tn)
            if model_info is None:
                self.stdout.write(self.style.WARNING(
                    f"Unknown table '{tn}', record_id={rid}. Skipping."
                ))
                skipped += 1
                continue

            model_cls, pk_field, status_field = model_info

            try:
                obj = model_cls.objects.get(**{pk_field: rid})
            except model_cls.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    f"{model_cls.__name__} with {pk_field}={rid} not found (TV #{tv.verification_id}, table={tn}). Skipping."
                ))
                skipped += 1
                continue

            current_status = getattr(obj, status_field)
            if current_status == target_status:
                continue

            if dry_run:
                self.stdout.write(
                    f"Would update {model_cls.__name__} #{rid} "
                    f"({status_field}: '{current_status}' -> '{target_status}') "
                    f"[TV #{tv.verification_id}, table={tn}]"
                )
            else:
                try:
                    model_cls.objects.filter(**{pk_field: rid}).update(
                        **{status_field: target_status}
                    )
                    self.stdout.write(self.style.SUCCESS(
                        f"Updated {model_cls.__name__} #{rid} "
                        f"({status_field}: '{current_status}' -> '{target_status}')"
                    ))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(
                        f"Failed to update {model_cls.__name__} #{rid}: {e}"
                    ))
                    errors += 1
                    continue

            updated += 1

        mode = "dry run" if dry_run else "completed"
        self.stdout.write(self.style.SUCCESS(
            f"Sync {mode}: updated={updated}, skipped={skipped}, errors={errors}."
        ))

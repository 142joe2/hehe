import hashlib
import mimetypes
from pathlib import Path

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import File
from django.core.management.base import BaseCommand
from django.utils import timezone

from core_system.models import DeathAid, MedicalAid, OfficerUser, SupportingProof


MEDIA_ROOT = Path(settings.MEDIA_ROOT)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _row_signature(file_digest: str, object_id: int) -> str:
    message = f"{file_digest}:{object_id}:{settings.SECRET_KEY}".encode()
    import hmac

    return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()


def _compact_date(value):
    return str(value).replace("-", "")[:8]


def _filename_contains_claim_id(filename: str, claim_id: int, prefix: str) -> bool:
    lowered = filename.lower()
    return f"{prefix.lower()}-{claim_id}" in lowered or f"{prefix.lower()}_{claim_id}" in lowered


def _filename_contains_member_id(filename: str, member_id: int) -> bool:
    lowered = filename.lower()
    return f"m-{member_id}" in lowered or f"_{member_id}_" in lowered or f"-{member_id}-" in lowered


def _select_file_for_claim(claim, files, kind, allow_latest_fallback):
    claim_id = int(claim.pk)
    claim_date = _compact_date(getattr(claim, "request_date", None) or getattr(claim, "claim_date", None))
    member_id = getattr(getattr(claim, "member_id_FK", None), "member_id_PK", None)

    for file_path in files:
        filename = file_path.name
        if _filename_contains_claim_id(filename, claim_id, "MED" if kind == "medical" else "DTH"):
            return file_path, "claim id in filename"
        if claim_date and claim_date in filename:
            return file_path, "claim date in filename"
        if member_id and _filename_contains_member_id(filename, int(member_id)):
            return file_path, "member id in filename"

    if allow_latest_fallback and files:
        return max(files, key=lambda p: p.stat().st_mtime), "latest file fallback"

    return None, "no safe match"


def _link_file_to_claim(content_type, claim, file_path, uploaded_by):
    file_digest = _sha256_file(file_path)
    file_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"

    with file_path.open("rb") as handle:
        proof = SupportingProof(
            content_type=content_type,
            object_id=int(claim.pk),
            file=File(handle, name=file_path.name),
            file_name=file_path.name,
            file_type=file_type,
            file_sha256=file_digest,
            uploaded_by=uploaded_by,
        )
        proof.row_signature = _row_signature(file_digest, int(claim.pk))
        proof.save()

    return proof


class Command(BaseCommand):
    help = "Backfill SupportingProof rows for existing Medical Aid and Death Aid media files."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show planned links without writing rows.")
        parser.add_argument(
            "--no-latest-fallback",
            action="store_true",
            help="Disable linking by latest file when no filename match exists.",
        )
        parser.add_argument(
            "--uploaded-by-id",
            type=int,
            help="Optional OfficerUser ID to assign as uploaded_by on backfilled rows.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        allow_latest_fallback = not options["no_latest_fallback"]
        uploaded_by = None

        if options["uploaded_by_id"]:
            try:
                uploaded_by = OfficerUser.objects.get(user_id_PK=options["uploaded_by_id"])
            except OfficerUser.DoesNotExist:
                self.stdout.write(self.style.ERROR("OfficerUser not found for --uploaded-by-id."))
                return

        medical_ct = ContentType.objects.get_for_model(MedicalAid)
        death_ct = ContentType.objects.get_for_model(DeathAid)

        medical_claims = list(MedicalAid.objects.exclude(
            pk__in=SupportingProof.objects.filter(content_type=medical_ct).values("object_id")
        ).order_by("medical_aid_id_PK"))
        death_claims = list(DeathAid.objects.exclude(
            pk__in=SupportingProof.objects.filter(content_type=death_ct).values("object_id")
        ).order_by("death_aid_id_PK"))

        medical_files = sorted(p for p in (MEDIA_ROOT / "medical_aid").glob("*") if p.is_file()) if (MEDIA_ROOT / "medical_aid").exists() else []
        death_files = sorted(p for p in (MEDIA_ROOT / "death_aid_uploads").glob("*") if p.is_file()) if (MEDIA_ROOT / "death_aid_uploads").exists() else []

        linked = 0
        skipped = 0

        for claim in medical_claims:
            file_path, reason = _select_file_for_claim(claim, medical_files, "medical", allow_latest_fallback)
            if not file_path:
                skipped += 1
                self.stdout.write(self.style.WARNING(f"Skipped MedicalAid #{claim.pk}: {reason}"))
                continue
            if dry_run:
                self.stdout.write(f"Would link MedicalAid #{claim.pk} to {file_path.name} ({reason}).")
            else:
                _link_file_to_claim(medical_ct, claim, file_path, uploaded_by)
                self.stdout.write(self.style.SUCCESS(f"Linked MedicalAid #{claim.pk} to {file_path.name} ({reason})."))
            linked += 1

        for claim in death_claims:
            file_path, reason = _select_file_for_claim(claim, death_files, "death", allow_latest_fallback)
            if not file_path:
                skipped += 1
                self.stdout.write(self.style.WARNING(f"Skipped DeathAid #{claim.pk}: {reason}"))
                continue
            if dry_run:
                self.stdout.write(f"Would link DeathAid #{claim.pk} to {file_path.name} ({reason}).")
            else:
                _link_file_to_claim(death_ct, claim, file_path, uploaded_by)
                self.stdout.write(self.style.SUCCESS(f"Linked DeathAid #{claim.pk} to {file_path.name} ({reason})."))
            linked += 1

        mode = "dry run" if dry_run else "completed"
        self.stdout.write(self.style.SUCCESS(f"Backfill {mode}: linked={linked}, skipped={skipped}."))

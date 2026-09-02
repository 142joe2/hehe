import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from datetime import datetime


from pathlib import Path

from django.conf import settings
from django.utils import timezone

from core_system.constants.policy_constants import POLICY
from core_system.models import BackupJob, SystemSetting


@dataclass
class BackupPaths:
    base_dir: Path
    db_dir: Path
    media_dir: Path
    config_dir: Path


def get_backup_paths() -> BackupPaths:
    # media/backups/... is already in tasks.md and matches repo structure.
    base_dir = Path(settings.MEDIA_ROOT) / "backups"
    db_dir = base_dir / "db"
    media_dir = base_dir / "files"
    config_dir = base_dir / "config"

    for d in (db_dir, media_dir, config_dir):
        d.mkdir(parents=True, exist_ok=True)

    return BackupPaths(
        base_dir=base_dir,
        db_dir=db_dir,
        media_dir=media_dir,
        config_dir=config_dir,
    )


def _now_stamp() -> str:
    return timezone.now().strftime("%Y%m%d_%H%M%S")


def _get_db_connection_env() -> dict:
    # Build best-effort parameters from Django settings.
    db = settings.DATABASES["default"]
    user = db.get("USER") or "root"
    password = db.get("PASSWORD") or "new_pasword"
    host = db.get("HOST") or "127.0.0.1"
    port = str(db.get("PORT") or "3307")
    name = db.get("NAME") or ""
    return {
        "user": user,
        "password": password,
        "host": host,
        "port": port,
        "name": name,
    }


def _run_cmd(cmd: list[str], cwd: str | None = None) -> None:
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed ({proc.returncode}): {' '.join(cmd)}\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}")


def create_db_backup(*, retention_count: int = 7) -> BackupJob:
    paths = get_backup_paths()
    stamp = _now_stamp()
    dump_path = paths.db_dir / f"db_{stamp}.sql.gz"

    dbc = _get_db_connection_env()

    # Use mysqldump -> gzip stream
    with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as tmp_sql:
        tmp_path = tmp_sql.name

    try:
        env = os.environ.copy()
        env["MYSQL_PWD"] = dbc["password"]

        cmd_dump = [
            "mysqldump",
            "-h",
            dbc["host"],
            "-P",
            dbc["port"],
            "-u",
            dbc["user"],
            dbc["name"],
        ]
        proc = subprocess.run(cmd_dump, capture_output=True, text=False, env=env)
        if proc.returncode != 0:
            raise RuntimeError(
                f"mysqldump failed ({proc.returncode}): {proc.stderr.decode(errors='replace')}"
            )

        with open(tmp_path, "wb") as f:
            f.write(proc.stdout)

        import gzip
        with open(tmp_path, "rb") as f_in, gzip.open(dump_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass

    # retention
    db_jobs = BackupJob.objects.filter(backup_type="db").order_by("-created_at")
    ids = list(db_jobs.values_list("job_id", flat=True))
    if len(ids) > retention_count:
        extra = ids[retention_count:]
        BackupJob.objects.filter(job_id__in=extra).delete()

    job = BackupJob.objects.create(
        backup_type="db",
        backup_status="Completed",
        db_dump_path=str(dump_path),
        created_at=timezone.now(),
        metadata_json=json.dumps({"host": dbc["host"], "db": dbc["name"]}),
    )
    return job


def create_media_backup(*, retention_count: int = 4) -> BackupJob:
    paths = get_backup_paths()
    stamp = _now_stamp()
    archive_path = paths.media_dir / f"media_{stamp}.tar.gz"

    media_root = Path(settings.MEDIA_ROOT)

    def _is_backup(p: Path) -> bool:
        try:
            return str(p).lower().startswith(str(media_root / "backups").lower())
        except Exception:
            return False

    with tarfile.open(archive_path, "w:gz") as tar:
        for root, dirs, files in os.walk(media_root):
            root_path = Path(root)
            dirs[:] = [d for d in dirs if not _is_backup(root_path / d)]
            for fn in files:
                fp = root_path / fn
                if _is_backup(fp):
                    continue
                arcname = str(fp.relative_to(media_root))
                tar.add(fp, arcname=arcname)

    # retention (keep last N media backups)
    jobs = BackupJob.objects.filter(backup_type="media").order_by("-created_at")
    ids = list(jobs.values_list("job_id", flat=True))
    if len(ids) > retention_count:
        extra = ids[retention_count:]
        BackupJob.objects.filter(job_id__in=extra).delete()

    job = BackupJob.objects.create(
        backup_type="media",
        backup_status="Completed",
        media_archive_path=str(archive_path),
        created_at=timezone.now(),
        metadata_json=json.dumps({"media_root": str(media_root)}),
    )
    return job


def create_config_backup(*, retention_count: int = 4) -> BackupJob:
    paths = get_backup_paths()
    stamp = _now_stamp()
    config_path = paths.config_dir / f"config_{stamp}.json"

    settings_qs = SystemSetting.objects.all().values("setting_key", "setting_value")
    payload = {
        "system_settings": list(settings_qs),
        "policy_constants": {k: getattr(POLICY, k) for k in dir(POLICY) if not k.startswith("_")},
        "generated_at": timezone.now().isoformat(),
    }

    config_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # retention
    jobs = BackupJob.objects.filter(backup_type="config").order_by("-created_at")
    ids = list(jobs.values_list("job_id", flat=True))
    if len(ids) > retention_count:
        extra = ids[retention_count:]
        BackupJob.objects.filter(job_id__in=extra).delete()

    job = BackupJob.objects.create(
        backup_type="config",
        backup_status="Completed",
        metadata_json=json.dumps({"config_path": str(config_path)}),
        created_at=timezone.now(),
    )
    return job


def list_backup_jobs(*, limit: int = 50) -> list[BackupJob]:
    limit = max(1, min(int(limit), 200))
    return list(BackupJob.objects.order_by("-created_at")[:limit])


def create_backup_bundle(*, include_config: bool = True) -> list[BackupJob]:
    """
    Create a manual “bundle” backup set:
      - db dump backup
      - media archive backup
      - config snapshot backup (optional)

    Returns the created BackupJob rows in [db, media, (config?)] order.
    """
    jobs: list[BackupJob] = []
    jobs.append(create_db_backup())
    jobs.append(create_media_backup())
    if include_config:
        jobs.append(create_config_backup())
    return jobs


def trigger_manual_backup(*, include_config: bool = True) -> list[BackupJob]:
    # Manual backup is a “bundle”: db + media + (optionally) config
    return create_backup_bundle(include_config=include_config)


def restore_db_from_dump(*, db_dump_path: str) -> None:
    dbc = _get_db_connection_env()

    dump_file = Path(db_dump_path)
    if not dump_file.exists():
        raise FileNotFoundError(f"DB dump not found: {db_dump_path}")

    # mysql command needs uncompressed SQL
    import gzip
    with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as tmp_sql:
        tmp_sql_path = tmp_sql.name

    try:
        with gzip.open(dump_file, "rb") as f_in, open(tmp_sql_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)

        env = os.environ.copy()
        env["MYSQL_PWD"] = dbc["password"]

        cmd_mysql = [
            "mysql",
            "-h",
            dbc["host"],
            "-P",
            dbc["port"],
            "-u",
            dbc["user"],
            dbc["name"],
        ]
        with open(tmp_sql_path, "rb") as f:
            proc = subprocess.run(cmd_mysql, input=f.read(), capture_output=True, env=env)
        if proc.returncode != 0:
            raise RuntimeError(
                f"mysql restore failed ({proc.returncode}): {proc.stderr.decode(errors='replace')}"
            )
    finally:
        try:
            if os.path.exists(tmp_sql_path):
                os.remove(tmp_sql_path)
        except Exception:
            pass


def restore_media_from_archive(*, media_archive_path: str) -> None:
    archive = Path(media_archive_path)
    if not archive.exists():
        raise FileNotFoundError(f"Media archive not found: {media_archive_path}")

    media_root = Path(settings.MEDIA_ROOT)
    backups_root = media_root / "backups"

    # Remove everything in media_root except backups directory
    for entry in media_root.iterdir():
        if entry.name == "backups":
            continue
        if entry.is_dir():
            shutil.rmtree(entry, ignore_errors=True)
        else:
            try:
                entry.unlink()
            except Exception:
                pass

    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(path=media_root)


def restore_config_from_snapshot(*, payload: dict) -> None:
    system_settings = payload.get("system_settings") or []

    # Replace all SystemSetting rows in snapshot for deterministic restore.
    # Keep unrelated keys? Here we restore exactly what exists in snapshot.
    keys = {row.get("setting_key") for row in system_settings if row.get("setting_key")}
    keys = {k for k in keys if isinstance(k, str) and k.strip()}

    if keys:
        SystemSetting.objects.exclude(setting_key__in=list(keys)).delete()

    for row in system_settings:
        k = row.get("setting_key")
        v = row.get("setting_value")
        if not k:
            continue
        SystemSetting.objects.update_or_create(
            setting_key=k,
            defaults={"setting_value": str(v)},
        )


def restore_backup_job(*, job_id: int, actor_officer=None, ip: str | None = None) -> dict:
    job = BackupJob.objects.filter(job_id=job_id).first()
    if not job:
        return {"ok": False, "error": "Backup job not found."}

    # Update status
    job.backup_status = "Pending"
    job.save(update_fields=["backup_status"])

    try:
        if job.backup_type == "db":
            if not job.db_dump_path:
                raise ValueError("Missing db_dump_path")
            restore_db_from_dump(db_dump_path=job.db_dump_path)
        elif job.backup_type == "media":
            if not job.media_archive_path:
                raise ValueError("Missing media_archive_path")
            restore_media_from_archive(media_archive_path=job.media_archive_path)
        elif job.backup_type == "config":
            meta = job.metadata_json
            if isinstance(meta, str):
                meta = json.loads(meta)
            config_path = (meta or {}).get("config_path")
            if not config_path:
                raise ValueError("Missing config_path in metadata_json")
            cfg_file = Path(config_path)
            if not cfg_file.exists():
                raise FileNotFoundError(f"Config snapshot not found: {config_path}")
            payload = json.loads(cfg_file.read_text(encoding="utf-8"))
            restore_config_from_snapshot(payload=payload)
        else:
            raise ValueError(f"Unknown backup_type: {job.backup_type}")

        job.backup_status = "Completed"
        job.save(update_fields=["backup_status"])
        return {"ok": True, "job": {"job_id": job.job_id, "backup_type": job.backup_type, "backup_status": job.backup_status}}
    except Exception as e:
        job.backup_status = "Failed"
        job.save(update_fields=["backup_status"])
        return {"ok": False, "error": str(e), "job": {"job_id": job.job_id, "backup_type": job.backup_type, "backup_status": job.backup_status}}


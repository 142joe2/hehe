from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django.core.management.base import BaseCommand
from django.utils import timezone

from core_system.services.backup_service import create_backup_bundle, create_config_backup, create_db_backup, create_media_backup
from core_system.services.dues_reminder import run_dues_reminders

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run the backup scheduler (autobackup)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--once",
            action="store_true",
            help="Run backup tasks once immediately, then exit.",
        )

        parser.add_argument(
            "--db-retention",
            type=int,
            default=7,
            help="Retention count for DB backups.",
        )
        parser.add_argument(
            "--media-retention",
            type=int,
            default=4,
            help="Retention count for media backups.",
        )
        parser.add_argument(
            "--config-retention",
            type=int,
            default=4,
            help="Retention count for config backups.",
        )

    def handle(self, *args, **options):
        once: bool = bool(options.get("once"))
        db_retention: int = int(options.get("db_retention"))
        media_retention: int = int(options.get("media_retention"))
        config_retention: int = int(options.get("config_retention"))

        logger.info("Backup scheduler starting at %s", timezone.now().isoformat())

        if once:
            self.stdout.write("Running backup tasks once...")
            create_db_backup(retention_count=db_retention)
            create_media_backup(retention_count=media_retention)
            create_config_backup(retention_count=config_retention)
            self.stdout.write(self.style.SUCCESS("Backup tasks completed."))
            return

        scheduler = BackgroundScheduler(timezone=timezone.get_current_timezone())

        # Daily DB backup at 02:00
        scheduler.add_job(
            lambda: create_db_backup(retention_count=db_retention),
            trigger=CronTrigger(hour=2, minute=0),
            id="backup_db_daily_0200",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=60 * 60,
        )

        # Weekly media backup: every Sunday 02:00
        scheduler.add_job(
            lambda: create_media_backup(retention_count=media_retention),
            trigger=CronTrigger(day_of_week="sun", hour=2, minute=0),
            id="backup_media_weekly_sun_0200",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=60 * 60,
        )

        # Config backup: weekly at same time (Sun 02:00) (simple + safe default)
        scheduler.add_job(
            lambda: create_config_backup(retention_count=config_retention),
            trigger=CronTrigger(day_of_week="sun", hour=2, minute=0),
            id="backup_config_weekly_sun_0200",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=60 * 60,
        )

        # Monthly dues reminders: daily 08:00
        scheduler.add_job(
            lambda: run_dues_reminders(dry_run=False),
            trigger=CronTrigger(hour=8, minute=0),
            id="dues_reminders_daily_0800",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=60 * 60,
        )

        scheduler.start()
        self.stdout.write(self.style.SUCCESS("Backup scheduler is running. Press Ctrl+C to stop."))

        try:
            # Keep process alive.
            import time

            while True:
                time.sleep(5)
        except KeyboardInterrupt:
            scheduler.shutdown(wait=False)
            logger.info("Backup scheduler stopped")


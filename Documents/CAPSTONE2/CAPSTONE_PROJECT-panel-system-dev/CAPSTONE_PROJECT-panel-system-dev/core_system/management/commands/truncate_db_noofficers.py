import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "caufa_portal.settings")
django.setup()

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Truncate all tables EXCEPT officer_user and django_migrations."

    def handle(self, *args, **options):
        preserve = {"officer_user", "django_migrations", "django_content_type"}

        # Disable foreign key checks for MySQL
        with connection.cursor() as cursor:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")

            # Get all table names
            cursor.execute("SHOW TABLES;")
            tables = [row[0] for row in cursor.fetchall()]

            for table in tables:
                if table.lower() in preserve:
                    self.stdout.write(f"[PRESERVED] {table}")
                    continue

                cursor.execute(f"TRUNCATE TABLE `{table}`;")
                self.stdout.write(f"[TRUNCATED] {table}")

            cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")

        self.stdout.write(self.style.SUCCESS("\nDone. officer_user table preserved."))

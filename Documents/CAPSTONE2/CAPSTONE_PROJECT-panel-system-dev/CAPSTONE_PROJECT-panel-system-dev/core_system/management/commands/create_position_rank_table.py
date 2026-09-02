from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Create position_rank table manually'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS position_rank (
                    position_rank_id_PK INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL UNIQUE,
                    category VARCHAR(50) NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at DATETIME(6) NOT NULL DEFAULT NOW(6),
                    created_by_user_id_FK INT NULL,
                    CONSTRAINT fk_position_rank_officer FOREIGN KEY (created_by_user_id_FK) REFERENCES OFFICER_USER(user_id_PK)
                )
            """)
            self.stdout.write(self.style.SUCCESS('Successfully created position_rank table'))

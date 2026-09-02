import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['DJANGO_SETTINGS_MODULE'] = 'caufa_portal.settings'
import django
django.setup()
from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE()")
    tables = [r[0] for r in cursor.fetchall()]
    print(f"Found {len(tables)} tables")
    for table in tables:
        cursor.execute(f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = '{table}' AND (COLUMN_NAME LIKE '%email%' OR COLUMN_NAME LIKE '%mail%')")
        cols = [r[0] for r in cursor.fetchall()]
        for col in cols:
            cursor.execute(f"SELECT `{col}` FROM `{table}` WHERE `{col}` LIKE '%evelyn%' OR `{col}` LIKE '%government%' LIMIT 5")
            for row in cursor.fetchall():
                print(f"{table}.{col} = {row[0]}")

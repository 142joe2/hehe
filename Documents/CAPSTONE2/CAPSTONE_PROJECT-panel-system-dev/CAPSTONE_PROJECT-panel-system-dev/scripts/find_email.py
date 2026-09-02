import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['DJANGO_SETTINGS_MODULE'] = 'caufa_portal.settings'
import django
django.setup()
from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("SELECT TABLE_NAME, COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE COLUMN_NAME LIKE '%email%' AND TABLE_SCHEMA = DATABASE()")
    tables = cursor.fetchall()
    for table, col in tables:
        cursor.execute(f"SELECT `{col}` FROM `{table}` WHERE `{col}` LIKE '%@government.gov' LIMIT 5")
        for row in cursor.fetchall():
            print(f"{table}.{col} = {row[0]}")

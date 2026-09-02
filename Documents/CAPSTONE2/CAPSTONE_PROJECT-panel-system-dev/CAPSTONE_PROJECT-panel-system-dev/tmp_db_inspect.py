import sqlite3

conn = sqlite3.connect('db.sqlite3')
cur = conn.cursor()
rows = cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
print('TABLE_COUNT', len(rows))
for (name,) in rows:
    try:
        count = cur.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
    except Exception as e:
        count = f'ERR:{e}'
    print(name, count)
print('--- auth_user ---')
for row in cur.execute('SELECT id, username, is_superuser, email, is_staff, is_active FROM auth_user ORDER BY id LIMIT 20').fetchall():
    print(row)
print('--- officer_user ---')
for row in cur.execute('SELECT user_id_PK, username, full_name, role, account_status, email FROM OFFICER_USER ORDER BY user_id_PK LIMIT 20').fetchall():
    print(row)
conn.close()

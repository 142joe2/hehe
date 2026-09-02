import sqlite3

conn = sqlite3.connect('db.sqlite3')
cur = conn.cursor()
print('SYSTEM_SETTING rows:')
for row in cur.execute('SELECT * FROM SYSTEM_SETTING').fetchall():
    print(row)
print('OFFICER_USER rows:')
for row in cur.execute('SELECT * FROM OFFICER_USER').fetchall():
    print(row)
print('OFFICER_USER columns:')
for col in cur.execute("PRAGMA table_info(OFFICER_USER)").fetchall():
    print(col)
print('AUTH_USER columns:')
for col in cur.execute("PRAGMA table_info(auth_user)").fetchall():
    print(col)
print('AUTH_PERMISSION count:', cur.execute('SELECT COUNT(*) FROM auth_permission').fetchone()[0])
conn.close()

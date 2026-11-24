import sqlite3
conn = sqlite3.connect(r'C:\Users\ZirconX\AppData\Local\ZXD44-IG-Cleaner\unfollowx.db')
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = c.fetchall()
print('Tables:', tables)
for t in tables:
    name = t[0]
    c.execute(f'SELECT COUNT(*) FROM {name}')
    cnt = c.fetchone()[0]
    print(f'Table {name}: {cnt} rows')
    if 0 < cnt < 20:
        c.execute(f'SELECT * FROM {name}')
        print(f'Rows in {name}:', c.fetchall())

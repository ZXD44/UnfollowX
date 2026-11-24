import sqlite3, os

db_path = os.path.expandvars(r'%LOCALAPPDATA%\ZXD44-IG-Cleaner\unfollowx.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("SELECT username FROM scan_snapshots WHERE snapshot_type = 'following'")
following = [r[0].lower() for r in c.fetchall()]

c.execute("SELECT username FROM scan_snapshots WHERE snapshot_type = 'followers'")
followers = [r[0].lower() for r in c.fetchall()]

conn.close()

print(f"Total Following rows in DB: {len(following)}")
print(f"Total Followers rows in DB: {len(followers)}")
print(f"Unique Following in DB: {len(set(following))}")
print(f"Unique Followers in DB: {len(set(followers))}")

following_set = set(following)
followers_set = set(followers)

diff = following_set - followers_set
print(f"Difference (Following - Followers): {len(diff)}")
for u in diff:
    print(f" - @{u}")

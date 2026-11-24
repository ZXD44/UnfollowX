import os, json, sqlite3
from playwright.sync_api import sync_playwright

db_path = os.path.expandvars(r'%LOCALAPPDATA%\ZXD44-IG-Cleaner\unfollowx.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute("SELECT user_id, username FROM scan_snapshots WHERE snapshot_type = 'following'")
targets = c.fetchall()
conn.close()

id_to_user = {t[0]: t[1] for t in targets}
user_ids = list(id_to_user.keys())
print(f"Total following to check with show_many: {len(user_ids)}")

profile_dir = os.path.expandvars(r'%LOCALAPPDATA%\ZXD44-IG-Cleaner\browser_profile')
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(user_data_dir=profile_dir, headless=True)
    page = ctx.new_page()
    page.goto('https://www.instagram.com/', wait_until='domcontentloaded')
    
    cookies = {c['name']: c['value'] for c in ctx.cookies()}
    csrf = cookies.get('csrftoken')
    
    # Process in chunks of 50
    chunk_size = 50
    not_following_back = []
    
    for i in range(0, min(len(user_ids), 50), chunk_size):
        chunk = user_ids[i:i + chunk_size]
        res = page.evaluate('''async (args) => {
            try {
                const body = new URLSearchParams();
                body.append('user_ids', args.ids.join(','));
                const resp = await fetch('/api/v1/friendships/show_many/', {
                    method: 'POST',
                    headers: {
                        'x-ig-app-id': '936619743392459',
                        'x-csrftoken': args.csrf,
                        'content-type': 'application/x-www-form-urlencoded'
                    },
                    body: body.toString()
                });
                const text = await resp.text();
                return { status: resp.status, redirected: resp.redirected, body: text };
            } catch(e) {
                return { error: e.toString() };
            }
        }''', {'ids': chunk, 'csrf': csrf})
        print("Response:", res.get('status'), res.get('redirected'), res.get('body', '')[:300])
        
        statuses = res.get('data', {}).get('friendship_statuses', {})
        for uid, st in statuses.items():
            following = st.get('following')
            followed_by = st.get('followed_by')
            uname = id_to_user.get(uid, uid)
            if following and not followed_by:
                not_following_back.append((uid, uname, st))
                print(f"[FOUND NON-FOLLOWER] @{uname} ({uid}): following={following}, followed_by={followed_by}")
                
    ctx.close()

print("\n" + "=" * 50)
print(f"Total Accounts NOT Following Back: {len(not_following_back)}")
print("=" * 50)
for uid, uname, st in not_following_back:
    print(f"@{uname} -> https://www.instagram.com/{uname}/")

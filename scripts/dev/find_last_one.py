import os
import sys
import json
import time
from playwright.sync_api import sync_playwright

profile_dir = os.path.expandvars(r'%LOCALAPPDATA%\ZXD44-IG-Cleaner\browser_profile')

print("Starting scan for the remaining 1 non-follower...", flush=True)

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=profile_dir,
        headless=True,
        args=['--disable-blink-features=AutomationControlled']
    )
    page = ctx.new_page()
    page.goto('https://www.instagram.com/', wait_until='domcontentloaded', timeout=20000)
    time.sleep(1)
    
    cookies = ctx.cookies()
    ds = next((c.get("value") for c in cookies if c.get("name") == "ds_user_id"), None)
    print(f"Logged in ds_user_id: {ds}", flush=True)
    
    script = f"""
    async () => {{
        const ds = '{ds}';
        const grabAll = async (ep) => {{
            let all = [];
            let maxId = null;
            let pageNum = 0;
            
            while (pageNum < 50) {{
                pageNum++;
                let url = `/api/v1/friendships/${{ds}}/${{ep}}/?count=50`;
                if (ep === 'followers') {{
                    url += '&search_surface=follow_list_page';
                }}
                if (maxId) {{
                    url += `&max_id=${{encodeURIComponent(maxId)}}`;
                }}
                
                const resp = await fetch(url, {{
                    credentials: 'include',
                    headers: {{
                        'x-ig-app-id': '936619743392459',
                        'x-requested-with': 'XMLHttpRequest',
                        'accept': '*/*'
                    }}
                }});
                
                if (resp.status !== 200 || resp.redirected) {{
                    break;
                }}
                
                const data = await resp.json();
                if (data.users && data.users.length > 0) {{
                    all.push(...data.users);
                }}
                
                if (!data.next_max_id) {{
                    break;
                }}
                maxId = data.next_max_id;
                await new Promise(r => setTimeout(r, 200));
            }}
            return all;
        }};
        
        const following = await grabAll('following');
        await new Promise(r => setTimeout(r, 400));
        const followers = await grabAll('followers');
        
        const followerUsernames = new Set(followers.map(u => (u.username || '').toLowerCase()));
        const followerPks = new Set(followers.map(u => String(u.pk || u.id)));
        
        const nonFollowers = following.filter(u => {{
            const uname = (u.username || '').toLowerCase();
            const pk = String(u.pk || u.id);
            return !followerUsernames.has(uname) && !followerPks.has(pk);
        }});
        
        return {{
            following_total: following.length,
            followers_total: followers.length,
            non_followers: nonFollowers.map(u => ({{
                id: String(u.pk || u.id),
                username: u.username,
                full_name: u.full_name || '',
                is_private: !!u.is_private,
                is_verified: !!u.is_verified
            }})),
            all_following: following.map(u => u.username),
            all_followers: followers.map(u => u.username)
        }};
    }}
    """
    
    result = page.evaluate(script)
    ctx.close()

print("\n" + "=" * 50, flush=True)
print(f"Total Following Fetched: {result.get('following_total')}", flush=True)
print(f"Total Followers Fetched: {result.get('followers_total')}", flush=True)
non_f = result.get('non_followers', [])
print(f"Non-Followers Found: {len(non_f)}", flush=True)
print("=" * 50, flush=True)

for i, nf in enumerate(non_f, 1):
    print(f"\n{i}. @{nf['username']} (Name: {nf['full_name']})", flush=True)
    print(f"   Link: https://www.instagram.com/{nf['username']}/", flush=True)

with open('LAST_ONE_FOUND.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

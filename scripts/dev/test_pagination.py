import os, json
from playwright.sync_api import sync_playwright

profile_dir = os.path.expandvars(r'%LOCALAPPDATA%\ZXD44-IG-Cleaner\browser_profile')
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(user_data_dir=profile_dir, headless=True)
    page = ctx.new_page()
    page.goto('https://www.instagram.com/', wait_until='domcontentloaded')
    
    cookies = {c['name']: c['value'] for c in ctx.cookies()}
    ds = cookies.get('ds_user_id')
    
    res = page.evaluate('''async (ds) => {
        let pages = [];
        let maxId = null;
        for (let i = 0; i < 25; i++) {
            let u = `/api/v1/friendships/${ds}/following/?count=50` + (maxId ? `&max_id=${encodeURIComponent(maxId)}` : '');
            let r = await fetch(u, {
                headers: {'x-ig-app-id': '936619743392459'}
            });
            let text = await r.text();
            let isJson = text.trim().startsWith('{');
            if (!isJson) {
                pages.push({
                    page: i + 1,
                    status: r.status,
                    redirected: r.redirected,
                    error_preview: text.slice(0, 150)
                });
                break;
            }
            let j = JSON.parse(text);
            pages.push({
                page: i + 1,
                count: j.users ? j.users.length : 0,
                next_max_id: j.next_max_id || null,
                sample: j.users ? j.users.slice(0, 2).map(x => x.username) : []
            });
            if (!j.next_max_id) break;
            maxId = j.next_max_id;
            await new Promise(res => setTimeout(res, 500));
        }
        return pages;
    }''', ds)
    
    print('Pagination trace:')
    for p_info in res:
        print(p_info)
    
    ctx.close()

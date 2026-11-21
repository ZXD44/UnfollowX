import os, json
from playwright.sync_api import sync_playwright

profile_dir = os.path.expandvars(r'%LOCALAPPDATA%\ZXD44-IG-Cleaner\browser_profile')
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=profile_dir,
        headless=True,
        channel='chrome',
        args=['--disable-blink-features=AutomationControlled']
    )
    page = ctx.new_page()
    page.goto('https://www.instagram.com/hdxw7/', wait_until='networkidle')
    
    # Test GraphQL query hashes
    hashes = [
        ('following_1', 'd04b0a70323f622296c0d8586d2e5f5e', {'id': '44684676608', 'include_reel': True, 'fetch_mutual': False, 'first': 50}),
        ('followers_1', 'c76146de99bb02f6415203be841dd25a', {'id': '44684676608', 'include_reel': True, 'fetch_mutual': False, 'first': 50}),
        ('followers_2', '5a533751e868aa2f739816041b488743', {'id': '44684676608', 'include_reel': True, 'fetch_mutual': False, 'first': 50}),
        ('followers_3', '37479f2b8209594dde7ffab26d3159a2', {'id': '44684676608', 'include_reel': True, 'fetch_mutual': False, 'first': 50}),
    ]
    
    for label, qhash, vars_obj in hashes:
        res = page.evaluate('''async (args) => {
            try {
                const url = `/graphql/query/?query_hash=${args.qhash}&variables=${encodeURIComponent(JSON.stringify(args.vars))}`;
                const resp = await fetch(url);
                return { status: resp.status, text: (await resp.text()).slice(0, 300) };
            } catch(e) {
                return { error: e.toString() };
            }
        }''', {'qhash': qhash, 'vars': vars_obj})
        print(f"[{label}] status={res.get('status')} -> {res.get('text', res.get('error'))}")
        
    ctx.close()

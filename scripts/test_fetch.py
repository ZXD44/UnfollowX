import os
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
    
    reqs = []
    page.on('response', lambda r: reqs.append((r.url, r.status)) if any(k in r.url for k in ['graphql', 'friendships', 'following', 'followers']) else None)
    
    links = page.query_selector_all('header a')
    for a in links:
        text = a.inner_text()
        if 'followers' in text:
            print('Clicking followers link...')
            a.click()
            page.wait_for_timeout(4000)
            break
            
    dialog = page.query_selector('div[role="dialog"]')
    if dialog:
        print('Dialog Text:\n', dialog.inner_text()[:600])
    else:
        print('No dialog found.')
        
    print('Responses captured:')
    for url, status in reqs:
        print(f'[{status}] {url}')
        
    ctx.close()

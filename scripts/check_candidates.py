import os
from playwright.sync_api import sync_playwright

candidates = [
    '_vintaaaaaa.07',
    'lamberthdutiful'
]

profile_dir = os.path.expandvars(r'%LOCALAPPDATA%\ZXD44-IG-Cleaner\browser_profile')
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=profile_dir,
        headless=True,
        channel='chrome',
        args=['--disable-blink-features=AutomationControlled']
    )
    page = ctx.new_page()
    
    for username in candidates:
        url = f'https://www.instagram.com/{username}/'
        page.goto(url, wait_until='domcontentloaded')
        page.wait_for_timeout(2000)
        
        # Check buttons in header
        buttons = [b.inner_text().strip() for b in page.query_selector_all('header button')]
        # Check text on page
        body = page.inner_text('header') if page.query_selector('header') else ''
        
        # Check if button says 'Following' or 'กำลังติดตาม'
        is_following = any(txt in ['Following', 'กำลังติดตาม', 'Requested', 'คำขอแล้ว'] for txt in buttons)
        follows_you = 'Follows you' in body or 'ติดตามคุณ' in body
        
        print(f'User: @{username:15} | Buttons: {buttons} | is_following={is_following} | follows_you={follows_you}')
        
    ctx.close()

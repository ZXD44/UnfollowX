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
    page.goto('https://www.instagram.com/hdxw7/', wait_until='domcontentloaded')
    page.wait_for_timeout(3000)
    
    # Click following link
    links = page.query_selector_all('header a')
    for a in links:
        text = a.inner_text()
        if 'following' in text or 'กำลังติดตาม' in text:
            print('Clicking following header link...')
            a.click()
            page.wait_for_timeout(4000)
            break
            
    dialog = page.query_selector('div[role="dialog"]')
    if dialog:
        print('Dialog Text:\n', dialog.inner_text()[:600])
    else:
        print('No dialog found.')
        
    ctx.close()

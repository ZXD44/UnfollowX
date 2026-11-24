import os, re
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
    
    js_urls = []
    page.on('response', lambda r: js_urls.append(r.url) if r.url.endswith('.js') and 'cdninstagram' in r.url else None)
    page.goto('https://www.instagram.com/hdxw7/', wait_until='networkidle')
    
    print('Found JS bundles:', len(js_urls))
    
    # Let's inspect window.__additionalData or Relay store in page context
    relay_data = page.evaluate('''() => {
        const win = window;
        const res = {};
        for (let k in win) {
            if (k.startsWith('__') || k.includes('relay') || k.includes('Store')) {
                res[k] = typeof win[k];
            }
        }
        return res;
    }''')
    print('Global objects:', relay_data)
    
    ctx.close()

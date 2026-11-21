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
    
    graphql_calls = []
    def handle_response(resp):
        if 'graphql' in resp.url or 'api/v1' in resp.url:
            try:
                text = resp.text()
                graphql_calls.append({
                    'url': resp.url,
                    'status': resp.status,
                    'body': text[:500]
                })
            except Exception as e:
                graphql_calls.append({'url': resp.url, 'status': resp.status, 'error': str(e)})

    page.on('response', handle_response)
    page.goto('https://www.instagram.com/hdxw7/', wait_until='networkidle')
    
    print('Total API/GraphQL calls captured on page load:', len(graphql_calls))
    for call in graphql_calls:
        print(f"[{call['status']}] {call['url'][:80]} -> {call.get('body', '')[:100]}")
        
    ctx.close()

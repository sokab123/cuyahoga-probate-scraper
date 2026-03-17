#!/usr/bin/env python3
"""Quick test to inspect the Cuyahoga search interface"""

from playwright.sync_api import sync_playwright
import time

def inspect_site():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)  # Headless mode
        page = browser.new_page()
        
        print("🌐 Loading site...")
        page.goto("https://cuyahoga.oh.publicsearch.us", wait_until="networkidle", timeout=60000)
        
        print("📸 Taking screenshot...")
        page.screenshot(path="homepage.png")
        
        print("\n🔍 Page title:", page.title())
        print("\n📄 HTML structure:")
        
        # Look for search inputs
        inputs = page.locator('input').all()
        print(f"\nFound {len(inputs)} input fields:")
        for i, inp in enumerate(inputs[:10]):  # Show first 10
            try:
                inp_type = inp.get_attribute('type')
                inp_name = inp.get_attribute('name')
                inp_id = inp.get_attribute('id')
                inp_placeholder = inp.get_attribute('placeholder')
                print(f"  {i+1}. type={inp_type}, name={inp_name}, id={inp_id}, placeholder={inp_placeholder}")
            except:
                pass
        
        # Look for buttons
        buttons = page.locator('button, input[type="submit"]').all()
        print(f"\nFound {len(buttons)} buttons/submit elements:")
        for i, btn in enumerate(buttons[:5]):
            try:
                text = btn.text_content()
                print(f"  {i+1}. {text}")
            except:
                pass
        
        # Look for links
        links = page.locator('a').all()
        print(f"\nFound {len(links)} links (showing first 10):")
        for i, link in enumerate(links[:10]):
            try:
                text = link.text_content().strip()
                href = link.get_attribute('href')
                if text:
                    print(f"  {i+1}. {text} -> {href}")
            except:
                pass
        
        print("\n⏸️  Pausing for 10 seconds so you can inspect the browser...")
        time.sleep(10)
        
        browser.close()
        print("✅ Done")

if __name__ == "__main__":
    inspect_site()

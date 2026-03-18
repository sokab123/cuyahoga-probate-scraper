#!/usr/bin/env python3
"""
Cuyahoga County Probate Lead Scraper v4
✅ FIXED: Now handles pagination to get ALL results (not just first 50)
"""

from playwright.sync_api import sync_playwright
import csv
import json
import os
from datetime import datetime, timedelta
from collections import defaultdict
import time
import re

# Target document types
DOCUMENT_TYPES = [
    "Power of Attorney",
    "Affidavit of Transfer on Death",
    "Deed- Certificate of Transfer",
    "Deed Transfer on Death",
    "Deed Survivorship"
]

BASE_URL = "https://cuyahoga.oh.publicsearch.us"

def dismiss_modal(page):
    """Dismiss any popups/modals"""
    try:
        close_btn = page.locator('button:has-text("×"), button[aria-label="Close"]').first
        if close_btn.is_visible(timeout=2000):
            close_btn.click()
            time.sleep(0.5)
    except:
        pass

def set_date_range(page, days_back=1):
    """Set the date range for search"""
    try:
        start_date = (datetime.now() - timedelta(days=days_back)).strftime('%-m/%-d/%Y')
        end_date = datetime.now().strftime('%-m/%-d/%Y')
        
        print(f"  📅 Setting date range: {start_date} → {end_date}")
        
        date_inputs = page.locator('input[type="text"]').all()
        
        if len(date_inputs) >= 2:
            date_inputs[0].click()
            date_inputs[0].fill('')
            date_inputs[0].fill(start_date)
            time.sleep(0.5)
            
            date_inputs[1].click()
            date_inputs[1].fill('')
            date_inputs[1].fill(end_date)
            time.sleep(0.5)
            
            print(f"  ✅ Date range set")
        
    except Exception as e:
        print(f"  ⚠️  Could not set date range: {e}")

def extract_parcel_from_text(text):
    """Extract parcel number from text using regex patterns"""
    if not text:
        return ''
    
    # Common Cuyahoga County parcel formats:
    # XXX-XX-XXX (e.g., 687-09-009)
    # XXXXXXXXXXXX (12 digits)
    # XXX XX XXX
    
    patterns = [
        r'\b(\d{3}-\d{2}-\d{3})\b',  # XXX-XX-XXX
        r'\b(\d{12})\b',  # 12 digits
        r'\b(\d{3}\s*\d{2}\s*\d{3})\b',  # XXX XX XXX
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            # Normalize format to XXX-XX-XXX
            parcel = match.group(1).replace(' ', '').replace('-', '')
            if len(parcel) >= 8:
                return f"{parcel[0:3]}-{parcel[3:5]}-{parcel[5:8]}"
    
    return ''

def scrape_document_type(page, doc_type, days_back=1):
    """Scrape records for a specific document type with PAGINATION"""
    print(f"\n🔍 Searching for: {doc_type}")
    
    all_records = []
    page_num = 1
    max_pages = 20  # Safety limit
    
    try:
        page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(2)
        
        dismiss_modal(page)
        set_date_range(page, days_back)
        
        search_input = page.locator('input[placeholder*="Search for grantor/grantee"]').first
        search_input.click()
        search_input.fill(doc_type)
        time.sleep(1)
        
        search_btn = page.locator('button[type="submit"], button:has-text("🔍")').first
        search_btn.click()
        
        print(f"  ⏳ Waiting for results...")
        time.sleep(4)
        
        page.wait_for_load_state("networkidle", timeout=30000)
        
        # Check for result count
        total_results = 0
        result_count = page.locator('text=/\d+-\d+ of \d+ results?/i').first
        if result_count.is_visible(timeout=3000):
            count_text = result_count.text_content()
            print(f"  📊 {count_text}")
            
            # Extract total count (e.g., "1-50 of 317 results")
            match = re.search(r'of (\d+)', count_text, re.IGNORECASE)
            if match:
                total_results = int(match.group(1))
        
        # PAGINATION LOOP
        while page_num <= max_pages:
            print(f"  📄 Page {page_num}...")
            
            # Extract table data from current page
            rows = page.locator('table tbody tr').all()
            page_records = []
            
            print(f"  📋 Found {len(rows)} result rows")
            
            for i, row in enumerate(rows):
                try:
                    # Get all cells in the row
                    cells = row.locator('td').all()
                    
                    # Column mapping:
                    # 0-2: Empty/icons
                    # 3: GRANTOR
                    # 4: GRANTEE
                    # 5: DOC TYPE
                    # 6: RECORDED DATE
                    # 7: DOC NUMBER
                    # 8: BOOK/VOLUME/PAGE
                    # 9: LEGAL DESCRIPTION
                    # 10: PARCEL ID
                    # 11: PROPERTY ADDRESS
                    # 12: REFERENCES
                    
                    if len(cells) >= 11:
                        grantor = cells[3].text_content().strip()
                        grantee = cells[4].text_content().strip()
                        recorded_date = cells[6].text_content().strip()
                        doc_number = cells[7].text_content().strip()
                        legal_desc = cells[9].text_content().strip()
                        parcel_id = cells[10].text_content().strip()
                        property_address = cells[11].text_content().strip() if len(cells) > 11 else ''
                        
                        # Extract parcel from legal description if parcel_id is N/A
                        if parcel_id == 'N/A' or not parcel_id:
                            parcel_id = extract_parcel_from_text(legal_desc)
                        
                        # Also check property address for parcel
                        if (not parcel_id or parcel_id == 'N/A') and property_address:
                            parcel_id = extract_parcel_from_text(property_address)
                        
                        record = {
                            'document_type': doc_type,
                            'grantor': grantor,
                            'grantee': grantee,
                            'recorded_date': recorded_date,
                            'document_number': doc_number,
                            'legal_description': legal_desc,
                            'parcel_number': parcel_id if parcel_id != 'N/A' else '',
                            'property_address': property_address if property_address != 'N/A' else '',
                        }
                        
                        page_records.append(record)
                        
                except Exception as e:
                    print(f"  ⚠️  Error parsing row {i}: {e}")
                    continue
            
            print(f"  ✅ Extracted {len(page_records)} records from page {page_num}")
            all_records.extend(page_records)
            
            # Check if we have all results
            if total_results > 0 and len(all_records) >= total_results:
                print(f"  ✅ Got all {total_results} results!")
                break
            
            # Try to find and click "Next Page" button
            try:
                # Look for pagination controls
                # Common selectors: button with "Next", arrow icon, page number + 1
                next_button = page.locator('button:has-text("Next"), button[aria-label*="Next"], a:has-text("›"), a:has-text("Next")').first
                
                if next_button.is_visible(timeout=2000):
                    # Save current page content to detect if navigation worked
                    old_row_count = len(rows)
                    
                    next_button.click()
                    time.sleep(3)  # Wait for page to load
                    page.wait_for_load_state("networkidle", timeout=15000)
                    
                    # Check if content changed
                    new_rows = page.locator('table tbody tr').all()
                    
                    if len(new_rows) == 0 or len(new_rows) == old_row_count:
                        # Check if the first row is the same (no new data)
                        if len(new_rows) > 0 and new_rows[0].text_content() == rows[0].text_content():
                            print("  ⏹  No more pages (content didn't change)")
                            break
                    
                    page_num += 1
                else:
                    print("  ⏹  No next button found")
                    break
                    
            except Exception as e:
                print(f"  ⏹  Pagination ended: {e}")
                break
        
        print(f"  🎯 Total extracted for '{doc_type}': {len(all_records)} records")
        
    except Exception as e:
        print(f"  ❌ Error scraping {doc_type}: {e}")
        try:
            page.screenshot(path=f"error_{doc_type.replace(' ', '_')}.png")
        except:
            pass
    
    return all_records

def group_by_parcel(records):
    """Group records by parcel number and score leads"""
    # Separate records with parcels vs without
    with_parcels = [r for r in records if r.get('parcel_number')]
    without_parcels = [r for r in records if not r.get('parcel_number')]
    
    print(f"  📦 {len(with_parcels)} records have parcel numbers")
    print(f"  ⚠️  {len(without_parcels)} records missing parcel numbers")
    
    parcel_groups = defaultdict(list)
    
    for record in with_parcels:
        parcel = record['parcel_number'].strip()
        parcel_groups[parcel].append(record)
    
    # Score leads
    scored_leads = []
    for parcel, docs in parcel_groups.items():
        doc_count = len(docs)
        lead_score = "HOT" if doc_count >= 2 else "WARM"
        
        # Get unique document types
        doc_types = list(set([d['document_type'] for d in docs]))
        
        # Get all names
        grantors = list(set([d.get('grantor', '') for d in docs if d.get('grantor')]))
        grantees = list(set([d.get('grantee', '') for d in docs if d.get('grantee')]))
        dates = list(set([d.get('recorded_date', '') for d in docs if d.get('recorded_date')]))
        doc_numbers = list(set([d.get('document_number', '') for d in docs if d.get('document_number')]))
        
        # Get property address (take first non-empty one)
        property_address = next((d.get('property_address', '') for d in docs if d.get('property_address')), '')
        
        lead = {
            'lead_score': lead_score,
            'document_count': doc_count,
            'parcel_number': parcel,
            'property_address': property_address,
            'grantors': '; '.join(grantors),
            'grantees': '; '.join(grantees),
            'document_types': '; '.join(doc_types),
            'recorded_dates': '; '.join(sorted(dates)),
            'document_numbers': '; '.join(doc_numbers)
        }
        
        scored_leads.append(lead)
    
    # Sort by score (HOT first), then by document count
    scored_leads.sort(key=lambda x: (x['lead_score'] != 'HOT', -x['document_count']))
    
    return scored_leads, without_parcels

def main():
    print("🏛️  Cuyahoga County Probate Lead Scraper v4")
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Check if this is the first run
    flag_file = '/tmp/cuyahoga_first_run_complete.flag'
    is_first_run = not os.path.exists(flag_file)
    
    if is_first_run:
        print("🎯 FIRST RUN: Pulling 14 days of historical data")
        days_back = 14
    else:
        print("♻️  Incremental run: Pulling 1 day of data")
        days_back = 1
    
    all_records = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        for doc_type in DOCUMENT_TYPES:
            records = scrape_document_type(page, doc_type, days_back)
            all_records.extend(records)
        
        browser.close()
    
    print(f"\n📊 Total records found: {len(all_records)}")
    
    # Analyze and score leads
    print(f"\n🧠 Analyzing leads by parcel...")
    scored_leads, no_parcel_records = group_by_parcel(all_records)
    
    # Summary
    hot_leads = [l for l in scored_leads if l['lead_score'] == 'HOT']
    warm_leads = [l for l in scored_leads if l['lead_score'] == 'WARM']
    
    print(f"\n📝 Lead Summary:")
    print(f"  🔥 HOT leads (2+ docs): {len(hot_leads)}")
    print(f"  💛 WARM leads (1 doc): {len(warm_leads)}")
    print(f"  📦 Total unique parcels: {len(scored_leads)}")
    
    # Save to CSV
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'cuyahoga_leads_{timestamp}.csv'
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        fieldnames = [
            'lead_score', 'document_count', 'parcel_number', 'property_address',
            'grantors', 'grantees', 'document_types', 'recorded_dates', 'document_numbers'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(scored_leads)
    
    print(f"\n✅ Saved {len(scored_leads)} leads to {filename}")
    
    # Save all records (including no-parcel) to JSON for backup
    all_data = {
        'timestamp': timestamp,
        'scored_leads': scored_leads,
        'no_parcel_records': no_parcel_records
    }
    
    json_filename = f'cuyahoga_all_records_{timestamp}.json'
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, indent=2)
    
    print(f"📄 All records saved to {json_filename}")
    
    if len(no_parcel_records) > 0:
        no_parcel_file = f'cuyahoga_no_parcels_{timestamp}.json'
        with open(no_parcel_file, 'w', encoding='utf-8') as f:
            json.dump(no_parcel_records, f, indent=2)
        print(f"⚠️  {len(no_parcel_records)} records without parcels saved to {no_parcel_file}")
    
    # Mark first run as complete
    if is_first_run:
        with open(flag_file, 'w') as f:
            f.write(datetime.now().isoformat())
        print(f"\n✅ First run complete. Future runs will only pull 1 day of data.")
    
    # Upload to Google Sheets
    try:
        from smart_deduplication import process_daily_leads, get_sheets_client
        
        print(f"\n🌊 Processing leads and updating Google Sheets...")
        
        client = get_sheets_client()
        new_leads, updated_leads, hot_alerts = process_daily_leads(filename, client)
        
        print(f"\n📊 Processing Results:")
        print(f"  🆕 New leads: {len(new_leads)}")
        print(f"  🔄 Updated leads: {len(updated_leads)}")
        print(f"  🔥 Hot alerts: {len(hot_alerts)}")
        
        # Send email alert if configured
        if hot_alerts or updated_leads:
            from smart_deduplication import send_email_alert
            send_email_alert(new_leads, updated_leads, hot_alerts)
    
    except Exception as e:
        print(f"\n⚠️  Google Sheets update failed: {e}")
    
    print(f"\n✅ Scrape complete!")

if __name__ == "__main__":
    main()

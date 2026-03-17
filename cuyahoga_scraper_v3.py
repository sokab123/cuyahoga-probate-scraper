#!/usr/bin/env python3
"""
Cuyahoga County Probate Lead Scraper v3
Correctly maps table columns and extracts parcel numbers
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
        r'\\b(\\d{3}-\\d{2}-\\d{3})\\b',  # XXX-XX-XXX
        r'\\b(\\d{12})\\b',  # 12 digits
        r'\\b(\\d{3}\\s*\\d{2}\\s*\\d{3})\\b',  # XXX XX XXX
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
    """Scrape records for a specific document type"""
    print(f"\n🔍 Searching for: {doc_type}")
    
    records = []
    
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
        result_count = page.locator('text=/\\d+ Results?/i').first
        if result_count.is_visible(timeout=3000):
            count_text = result_count.text_content()
            print(f"  📊 {count_text}")
        
        # Extract table data - specifically targeting tbody tr
        rows = page.locator('table tbody tr').all()
        
        print(f"  📋 Found {len(rows)} result rows")
        
        for i, row in enumerate(rows[:100]):  # Get up to 100 results
            try:
                # Get all cells in the row
                cells = row.locator('td').all()
                
                # Based on the screenshot, the columns are:
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
                    
                    records.append(record)
                    
            except Exception as e:
                print(f"  ⚠️  Error parsing row {i}: {e}")
                continue
        
        print(f"  ✅ Extracted {len(records)} records")
        
    except Exception as e:
        print(f"  ❌ Error scraping {doc_type}: {e}")
        try:
            page.screenshot(path=f"error_{doc_type.replace(' ', '_')}.png")
        except:
            pass
    
    return records

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
        
        # Get property address (use first non-empty)
        address = next((d.get('property_address', '') for d in docs if d.get('property_address')), '')
        
        # Get all document numbers and dates
        doc_numbers = [d.get('document_number', '') for d in docs if d.get('document_number')]
        dates = [d.get('recorded_date', '') for d in docs if d.get('recorded_date')]
        
        scored_leads.append({
            'parcel_number': parcel,
            'property_address': address,
            'document_count': doc_count,
            'lead_score': lead_score,
            'document_types': '; '.join(doc_types),
            'grantors': '; '.join(grantors) if grantors else '',
            'grantees': '; '.join(grantees) if grantees else '',
            'document_numbers': '; '.join(doc_numbers) if doc_numbers else '',
            'recorded_dates': '; '.join(dates) if dates else '',
        })
    
    # Sort by document count (hot leads first)
    scored_leads.sort(key=lambda x: x['document_count'], reverse=True)
    
    return scored_leads, without_parcels

def save_to_csv(leads, filename):
    """Save leads to CSV file"""
    if not leads:
        print("⚠️  No leads to save")
        return
    
    fieldnames = [
        'lead_score',
        'document_count',
        'parcel_number',
        'property_address',
        'grantors',
        'grantees',
        'document_types',
        'recorded_dates',
        'document_numbers'
    ]
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(leads)
    
    print(f"\n✅ Saved {len(leads)} leads to {filename}")

def main():
    """Main scraper function"""
    print("🏛️  Cuyahoga County Probate Lead Scraper v3")
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Check if this is first run or daily run
    # Use environment variable or check for existence of a flag file
    first_run = os.getenv('FIRST_RUN', 'false').lower() == 'true'
    flag_file = 'first_run_complete.flag'
    
    if first_run or not os.path.exists(flag_file):
        days_back = 14
        print("📅 FIRST RUN: Pulling 14 days of historical data\n")
    else:
        days_back = 1
        print("📅 DAILY RUN: Pulling yesterday's records only\n")
    
    all_records = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )
        page = context.new_page()
        
        # Scrape each document type
        for doc_type in DOCUMENT_TYPES:
            records = scrape_document_type(page, doc_type, days_back=days_back)
            all_records.extend(records)
            time.sleep(3)  # Be polite between searches
        
        browser.close()
    
    # Mark first run as complete
    if not os.path.exists(flag_file):
        with open(flag_file, 'w') as f:
            f.write(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        print(f"\n✅ First run complete. Future runs will only pull 1 day of data.")
    
    print(f"\n📊 Total records found: {len(all_records)}")
    
    # Group by parcel and score
    print("\n🎯 Analyzing leads by parcel...")
    scored_leads, orphans = group_by_parcel(all_records)
    
    # Stats
    hot_leads = [l for l in scored_leads if l['lead_score'] == 'HOT']
    warm_leads = [l for l in scored_leads if l['lead_score'] == 'WARM']
    
    print(f"\n📈 Lead Summary:")
    print(f"  🔥 HOT leads (2+ docs): {len(hot_leads)}")
    print(f"  ⚡ WARM leads (1 doc): {len(warm_leads)}")
    print(f"  📦 Total unique parcels: {len(scored_leads)}")
    
    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"cuyahoga_leads_{timestamp}.csv"
    save_to_csv(scored_leads, filename)
    
    # Save all records (with parcels) for reference
    all_filename = f"cuyahoga_all_records_{timestamp}.json"
    with open(all_filename, 'w') as f:
        json.dump(all_records, f, indent=2)
    print(f"💾 All records saved to {all_filename}")
    
    # Save orphans (no parcels) separately
    if orphans:
        orphan_filename = f"cuyahoga_no_parcels_{timestamp}.json"
        with open(orphan_filename, 'w') as f:
            json.dump(orphans, f, indent=2)
        print(f"⚠️  {len(orphans)} records without parcels saved to {orphan_filename}")
    
    print(f"\n✅ Scrape complete!")
    
    # Process with smart deduplication and upload to Google Sheets
    print("\n📤 Processing leads and updating Google Sheets...")
    try:
        from smart_deduplication import process_daily_leads, send_email_alert, get_sheets_client
        
        client = get_sheets_client()
        new_leads, updated_leads, hot_alerts = process_daily_leads(filename, client)
        
        print(f"\n📊 Processing Results:")
        print(f"  🆕 New leads: {len(new_leads)}")
        print(f"  🔄 Updated leads: {len(updated_leads)}")
        print(f"  🔥 Hot alerts: {len(hot_alerts)}")
        
        # Send email alert if there's activity
        if hot_alerts or updated_leads:
            send_email_alert(new_leads, updated_leads, hot_alerts)
            
    except Exception as e:
        print(f"⚠️  Smart processing failed: {e}")
        print("Falling back to simple upload...")
        try:
            from google_sheets_uploader import upload_to_sheets
            upload_to_sheets(filename)
        except Exception as e2:
            print(f"⚠️  Google Sheets upload also failed: {e2}")
    
    # Show top 10 hot leads
    if hot_leads:
        print("\n🔥 Top HOT Leads (2+ documents):")
        for i, lead in enumerate(hot_leads[:10], 1):
            addr = lead['property_address'][:40] if lead['property_address'] else 'No address'
            print(f"  {i}. {lead['parcel_number']} | {lead['document_count']} docs | {addr}")
            print(f"     Types: {lead['document_types']}")
    
    # Show sample warm leads
    if warm_leads and len(warm_leads) <= 20:
        print(f"\n⚡ WARM Leads (1 document each): {len(warm_leads)} total")
        for lead in warm_leads[:5]:
            addr = lead['property_address'][:40] if lead['property_address'] else 'No address'
            print(f"  • {lead['parcel_number']} | {lead['document_types']} | {addr}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Cuyahoga County Probate Lead Scraper v2
Searches for trigger documents and identifies high-value leads based on parcel activity
"""

from playwright.sync_api import sync_playwright
import csv
import json
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
        # Look for close button (X) or dismiss button
        close_btn = page.locator('button:has-text("×"), button[aria-label="Close"]').first
        if close_btn.is_visible(timeout=2000):
            close_btn.click()
            time.sleep(0.5)
    except:
        pass  # No modal to close

def set_date_range(page, days_back=1):
    """Set the date range for search"""
    try:
        # Calculate start date (days_back from today)
        start_date = (datetime.now() - timedelta(days=days_back)).strftime('%-m/%-d/%Y')
        end_date = datetime.now().strftime('%-m/%-d/%Y')
        
        print(f"  📅 Setting date range: {start_date} → {end_date}")
        
        # Find the date inputs (there should be 2 text inputs for dates)
        date_inputs = page.locator('input[type="text"]').all()
        
        if len(date_inputs) >= 2:
            # Clear and set start date
            date_inputs[0].click()
            date_inputs[0].fill('')
            date_inputs[0].fill(start_date)
            time.sleep(0.5)
            
            # Clear and set end date
            date_inputs[1].click()
            date_inputs[1].fill('')
            date_inputs[1].fill(end_date)
            time.sleep(0.5)
            
            print(f"  ✅ Date range set")
        
    except Exception as e:
        print(f"  ⚠️  Could not set date range: {e}")

def scrape_document_type(page, doc_type, days_back=1):
    """Scrape records for a specific document type"""
    print(f"\n🔍 Searching for: {doc_type}")
    
    records = []
    
    try:
        # Navigate to search page
        page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(2)
        
        # Dismiss modal if present
        dismiss_modal(page)
        
        # Set date range
        set_date_range(page, days_back)
        
        # Find the main search input
        search_input = page.locator('input[placeholder*="Search for grantor/grantee"]').first
        search_input.click()
        search_input.fill(doc_type)
        time.sleep(1)
        
        # Click search button (magnifying glass)
        search_btn = page.locator('button[type="submit"], button:has-text("🔍")').first
        search_btn.click()
        
        print(f"  ⏳ Waiting for results...")
        time.sleep(4)
        
        # Wait for results to load
        page.wait_for_load_state("networkidle", timeout=30000)
        
        # Take a screenshot for debugging
        page.screenshot(path=f"search_{doc_type.replace(' ', '_')}.png")
        
        # Look for results - try multiple selectors
        # First, try to find the results table/list
        result_count = page.locator('text=/\\d+ Results?/i').first
        if result_count.is_visible(timeout=3000):
            count_text = result_count.text_content()
            print(f"  📊 {count_text}")
        
        # Extract results from table rows
        # Common patterns: tr, .result-row, .document-row, etc.
        rows = page.locator('table tbody tr, .result-row, .search-result').all()
        
        if len(rows) == 0:
            # Try alternative selectors
            rows = page.locator('[class*="result"], [class*="row"]').all()
        
        print(f"  📋 Found {len(rows)} potential result rows")
        
        for i, row in enumerate(rows[:50]):  # Limit to first 50 results
            try:
                # Get all text content from the row
                row_text = row.text_content()
                
                # Try to extract structured data
                cells = row.locator('td, .cell, [class*="col"]').all()
                
                if len(cells) >= 3:
                    # Attempt to parse common patterns
                    record = {
                        'document_type': doc_type,
                        'raw_text': row_text.strip(),
                        'cells': [c.text_content().strip() for c in cells]
                    }
                    records.append(record)
                elif row_text.strip():
                    # Fall back to raw text parsing
                    record = {
                        'document_type': doc_type,
                        'raw_text': row_text.strip()
                    }
                    records.append(record)
                    
            except Exception as e:
                print(f"  ⚠️  Error parsing row {i}: {e}")
                continue
        
        print(f"  ✅ Extracted {len(records)} records")
        
    except Exception as e:
        print(f"  ❌ Error scraping {doc_type}: {e}")
        # Take error screenshot
        try:
            page.screenshot(path=f"error_{doc_type.replace(' ', '_')}.png")
        except:
            pass
    
    return records

def parse_records(raw_records):
    """Parse raw records into structured data"""
    parsed = []
    
    for record in raw_records:
        try:
            # If we have cells, try to map them
            if 'cells' in record and len(record['cells']) >= 3:
                cells = record['cells']
                parsed_record = {
                    'document_type': record['document_type'],
                    'document_number': cells[0] if len(cells) > 0 else '',
                    'recorded_date': cells[1] if len(cells) > 1 else '',
                    'grantor': cells[2] if len(cells) > 2 else '',
                    'grantee': cells[3] if len(cells) > 3 else '',
                    'property_address': cells[4] if len(cells) > 4 else '',
                    'parcel_number': cells[5] if len(cells) > 5 else '',
                }
                parsed.append(parsed_record)
            else:
                # Try to parse from raw text
                raw_text = record.get('raw_text', '')
                # Extract parcel number (typically format: XXX-XX-XXX)
                parcel_match = re.search(r'\\b\\d{3}-\\d{2}-\\d{3}\\b', raw_text)
                
                parsed_record = {
                    'document_type': record['document_type'],
                    'raw_text': raw_text,
                    'parcel_number': parcel_match.group(0) if parcel_match else '',
                    'document_number': '',
                    'recorded_date': '',
                    'grantor': '',
                    'grantee': '',
                    'property_address': '',
                }
                parsed.append(parsed_record)
                
        except Exception as e:
            print(f"  ⚠️  Error parsing record: {e}")
            continue
    
    return parsed

def group_by_parcel(records):
    """Group records by parcel number and score leads"""
    parcel_groups = defaultdict(list)
    
    for record in records:
        parcel = record.get('parcel_number', '').strip()
        if parcel:  # Only group if parcel number exists
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
        
        # Get raw text for reference
        raw_texts = [d.get('raw_text', '') for d in docs if d.get('raw_text')]
        
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
            'raw_data': ' || '.join(raw_texts[:3]) if raw_texts else '',  # First 3 entries
        })
    
    # Sort by document count (hot leads first)
    scored_leads.sort(key=lambda x: x['document_count'], reverse=True)
    
    return scored_leads

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
        'document_numbers',
        'raw_data'
    ]
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(leads)
    
    print(f"\n✅ Saved {len(leads)} leads to {filename}")

def main():
    """Main scraper function"""
    print("🏛️  Cuyahoga County Probate Lead Scraper v2")
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
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
            records = scrape_document_type(page, doc_type, days_back=7)  # Last 7 days
            all_records.extend(records)
            time.sleep(3)  # Be polite between searches
        
        browser.close()
    
    print(f"\n📊 Total raw records found: {len(all_records)}")
    
    # Parse records
    print("\n🔧 Parsing records...")
    parsed_records = parse_records(all_records)
    print(f"  ✅ Parsed {len(parsed_records)} records")
    
    # Group by parcel and score
    print("\n🎯 Analyzing leads by parcel...")
    scored_leads = group_by_parcel(parsed_records)
    
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
    
    # Also save raw data for debugging
    raw_filename = f"cuyahoga_raw_{timestamp}.json"
    with open(raw_filename, 'w') as f:
        json.dump(all_records, f, indent=2)
    print(f"💾 Raw data saved to {raw_filename}")
    
    print(f"\n✅ Scrape complete!")
    
    # Show top 5 hot leads
    if hot_leads:
        print("\n🔥 Top HOT Leads:")
        for lead in hot_leads[:5]:
            print(f"  • {lead['parcel_number']} ({lead['document_count']} docs) - {lead['document_types']}")
    
    # Show sample of all leads
    if scored_leads:
        print(f"\n📋 Sample of all leads (first 10):")
        for lead in scored_leads[:10]:
            print(f"  • [{lead['lead_score']}] {lead['parcel_number']} ({lead['document_count']} docs)")

if __name__ == "__main__":
    main()

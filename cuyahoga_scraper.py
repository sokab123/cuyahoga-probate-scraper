#!/usr/bin/env python3
"""
Cuyahoga County Probate Lead Scraper
Searches for trigger documents and identifies high-value leads based on parcel activity
"""

from playwright.sync_api import sync_playwright
import csv
import json
from datetime import datetime, timedelta
from collections import defaultdict
import time

# Target document types
DOCUMENT_TYPES = [
    "Power of Attorney",
    "Affidavit of Transfer on Death",
    "Deed- Certificate of Transfer",
    "Deed Transfer on Death",
    "Deed Survivorship"
]

BASE_URL = "https://cuyahoga.oh.publicsearch.us"

def scrape_document_type(page, doc_type, days_back=1):
    """Scrape records for a specific document type"""
    print(f"\n🔍 Searching for: {doc_type}")
    
    records = []
    
    try:
        # Navigate to search page
        page.goto(BASE_URL, wait_until="networkidle", timeout=60000)
        time.sleep(2)
        
        # Look for search input field
        search_input = page.locator('input[type="text"]').first
        search_input.fill(doc_type)
        time.sleep(1)
        
        # Submit search
        search_button = page.locator('button:has-text("Search"), input[type="submit"]').first
        search_button.click()
        time.sleep(3)
        
        # Wait for results
        page.wait_for_load_state("networkidle", timeout=30000)
        
        # Extract results from table
        rows = page.locator('table tr').all()
        print(f"Found {len(rows)} rows")
        
        for row in rows[1:]:  # Skip header
            cells = row.locator('td').all()
            if len(cells) >= 5:
                try:
                    record = {
                        'document_type': doc_type,
                        'document_number': cells[0].text_content().strip(),
                        'recorded_date': cells[1].text_content().strip(),
                        'grantor': cells[2].text_content().strip(),
                        'grantee': cells[3].text_content().strip(),
                        'property_address': cells[4].text_content().strip() if len(cells) > 4 else '',
                        'parcel_number': cells[5].text_content().strip() if len(cells) > 5 else '',
                    }
                    records.append(record)
                except Exception as e:
                    print(f"  ⚠️  Error parsing row: {e}")
                    continue
        
        print(f"  ✅ Extracted {len(records)} records")
        
    except Exception as e:
        print(f"  ❌ Error scraping {doc_type}: {e}")
    
    return records

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
        grantors = list(set([d['grantor'] for d in docs if d['grantor']]))
        grantees = list(set([d['grantee'] for d in docs if d['grantee']]))
        
        # Get property address (use first non-empty)
        address = next((d['property_address'] for d in docs if d.get('property_address')), '')
        
        # Get all document numbers and dates
        doc_numbers = [d['document_number'] for d in docs]
        dates = [d['recorded_date'] for d in docs]
        
        scored_leads.append({
            'parcel_number': parcel,
            'property_address': address,
            'document_count': doc_count,
            'lead_score': lead_score,
            'document_types': '; '.join(doc_types),
            'grantors': '; '.join(grantors),
            'grantees': '; '.join(grantees),
            'document_numbers': '; '.join(doc_numbers),
            'recorded_dates': '; '.join(dates),
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
        'document_numbers'
    ]
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(leads)
    
    print(f"\n✅ Saved {len(leads)} leads to {filename}")

def main():
    """Main scraper function"""
    print("🏛️  Cuyahoga County Probate Lead Scraper")
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    all_records = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Scrape each document type
        for doc_type in DOCUMENT_TYPES:
            records = scrape_document_type(page, doc_type)
            all_records.extend(records)
            time.sleep(2)  # Be polite between searches
        
        browser.close()
    
    print(f"\n📊 Total records found: {len(all_records)}")
    
    # Group by parcel and score
    print("\n🎯 Analyzing leads by parcel...")
    scored_leads = group_by_parcel(all_records)
    
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
            print(f"  • {lead['parcel_number']} - {lead['property_address']} ({lead['document_count']} docs)")

if __name__ == "__main__":
    main()

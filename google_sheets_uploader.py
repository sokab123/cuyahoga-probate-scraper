#!/usr/bin/env python3
"""
Google Sheets uploader for Cuyahoga leads
Appends daily results to a master Google Sheet
"""

import gspread
from oauth2client.service_account import ServiceAccountCredentials
import csv
import json
from datetime import datetime
import os

def upload_to_sheets(csv_file, sheet_name="Cuyahoga Probate Leads"):
    """
    Upload CSV data to Google Sheets
    
    Requirements:
    1. Create a Google Cloud project
    2. Enable Google Sheets API
    3. Create a service account and download JSON credentials
    4. Share your Google Sheet with the service account email
    5. Set GOOGLE_CREDENTIALS environment variable (JSON string)
    """
    
    # Get credentials from environment variable
    creds_json = os.getenv('GOOGLE_CREDENTIALS')
    if not creds_json:
        print("❌ GOOGLE_CREDENTIALS environment variable not set")
        print("⚠️  Skipping Google Sheets upload")
        return False
    
    try:
        # Parse credentials
        creds_dict = json.loads(creds_json)
        
        # Define scope
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        
        # Authorize
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # Open or create sheet
        try:
            sheet = client.open(sheet_name).sheet1
            print(f"📊 Found existing sheet: {sheet_name}")
        except gspread.SpreadsheetNotFound:
            print(f"📊 Creating new sheet: {sheet_name}")
            spreadsheet = client.create(sheet_name)
            sheet = spreadsheet.sheet1
            
            # Share with your email (get from env var)
            owner_email = os.getenv('OWNER_EMAIL')
            if owner_email:
                spreadsheet.share(owner_email, perm_type='user', role='writer')
                print(f"✉️  Shared sheet with: {owner_email}")
        
        # Read CSV data
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
        
        if len(rows) == 0:
            print("⚠️  CSV is empty")
            return False
        
        # Check if this is first upload (no headers in sheet)
        existing_data = sheet.get_all_values()
        
        if len(existing_data) == 0:
            # First upload - include headers
            print("📝 First upload - adding headers")
            data_to_append = rows
        else:
            # Subsequent upload - skip headers, add timestamp column
            print("📝 Appending to existing data")
            data_to_append = rows[1:]  # Skip header row
        
        # Add timestamp to each row
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for row in data_to_append:
            row.append(timestamp)
        
        # If first upload, add "Last Updated" header
        if len(existing_data) == 0:
            data_to_append[0].append('Last Updated')
        
        # Append data
        if len(data_to_append) > 1:  # More than just headers
            sheet.append_rows(data_to_append)
            print(f"✅ Uploaded {len(data_to_append)-1 if len(existing_data)==0 else len(data_to_append)} rows to Google Sheets")
            print(f"🔗 Sheet URL: {sheet.spreadsheet.url}")
            return True
        else:
            print("⚠️  No new data to upload")
            return False
            
    except Exception as e:
        print(f"❌ Error uploading to Google Sheets: {e}")
        return False

def main():
    """Test the uploader"""
    # Find most recent CSV file
    import glob
    csv_files = glob.glob("cuyahoga_leads_*.csv")
    
    if not csv_files:
        print("❌ No CSV files found")
        return
    
    # Get most recent
    latest_csv = max(csv_files, key=os.path.getctime)
    print(f"📁 Uploading: {latest_csv}")
    
    upload_to_sheets(latest_csv)

if __name__ == "__main__":
    main()

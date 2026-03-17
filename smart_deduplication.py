#!/usr/bin/env python3
"""
Smart deduplication and parcel tracking system
Compares daily scrapes against master sheet, tracks repeat activity, sends alerts
"""

import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os
from datetime import datetime
from collections import defaultdict
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def get_sheets_client():
    """Get authenticated Google Sheets client"""
    creds_json = os.getenv('GOOGLE_CREDENTIALS')
    if not creds_json:
        raise Exception("GOOGLE_CREDENTIALS not set")
    
    creds_dict = json.loads(creds_json)
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

def load_master_sheet(client, sheet_name="Cuyahoga Probate Leads"):
    """Load existing data from master sheet"""
    try:
        spreadsheet = client.open(sheet_name)
        master_sheet = spreadsheet.worksheet("Master")
        
        # Get all records
        records = master_sheet.get_all_records()
        
        # Index by parcel number for fast lookup
        parcel_index = {}
        for idx, record in enumerate(records, start=2):  # Start at row 2 (after header)
            parcel = record.get('parcel_number', '').strip()
            if parcel:
                parcel_index[parcel] = {
                    'row': idx,
                    'record': record
                }
        
        return spreadsheet, master_sheet, parcel_index
        
    except gspread.exceptions.WorksheetNotFound:
        # Create Master sheet if it doesn't exist
        spreadsheet = client.open(sheet_name)
        master_sheet = spreadsheet.add_worksheet(title="Master", rows=1000, cols=15)
        
        # Add headers
        headers = [
            'lead_score', 'document_count', 'parcel_number', 'property_address',
            'grantors', 'grantees', 'document_types', 'recorded_dates',
            'document_numbers', 'first_seen', 'last_updated', 'activity_count'
        ]
        master_sheet.append_row(headers)
        
        return spreadsheet, master_sheet, {}

def process_daily_leads(daily_leads_file, client):
    """
    Process daily leads against master sheet
    Returns: new_leads, updated_leads, hot_alerts
    """
    import csv
    
    # Load master data
    spreadsheet, master_sheet, parcel_index = load_master_sheet(client)
    
    # Read daily leads
    with open(daily_leads_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        daily_leads = list(reader)
    
    new_leads = []
    updated_leads = []
    hot_alerts = []
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    for lead in daily_leads:
        parcel = lead['parcel_number'].strip()
        if not parcel:
            continue
        
        if parcel in parcel_index:
            # EXISTING PARCEL - Check if new documents added
            existing = parcel_index[parcel]['record']
            existing_count = int(existing.get('document_count', 0))
            new_count = int(lead['document_count'])
            
            # Get existing document types
            existing_types = set(existing.get('document_types', '').split('; '))
            new_types = set(lead['document_types'].split('; '))
            
            # Check if there are truly new document types
            added_types = new_types - existing_types
            
            if added_types or new_count > existing_count:
                # UPDATE EXISTING ROW
                row_num = parcel_index[parcel]['row']
                
                # Merge document data
                all_types = existing_types | new_types
                all_grantors = set(existing.get('grantors', '').split('; ')) | set(lead['grantors'].split('; '))
                all_grantees = set(existing.get('grantees', '').split('; ')) | set(lead['grantees'].split('; '))
                all_doc_numbers = set(existing.get('document_numbers', '').split('; ')) | set(lead['document_numbers'].split('; '))
                all_dates = set(existing.get('recorded_dates', '').split('; ')) | set(lead['recorded_dates'].split('; '))
                
                # Remove empty strings
                all_types.discard('')
                all_grantors.discard('')
                all_grantees.discard('')
                all_doc_numbers.discard('')
                all_dates.discard('')
                
                total_count = len(all_doc_numbers)
                activity_count = int(existing.get('activity_count', 1)) + 1
                
                # Determine new lead score
                new_score = "HOT" if total_count >= 2 else "WARM"
                
                # Update row
                updated_row = [
                    new_score,
                    total_count,
                    parcel,
                    lead['property_address'] or existing.get('property_address', ''),
                    '; '.join(sorted(all_grantors)),
                    '; '.join(sorted(all_grantees)),
                    '; '.join(sorted(all_types)),
                    '; '.join(sorted(all_dates)),
                    '; '.join(sorted(all_doc_numbers)),
                    existing.get('first_seen', timestamp),
                    timestamp,
                    activity_count
                ]
                
                master_sheet.update(f'A{row_num}:L{row_num}', [updated_row])
                
                updated_leads.append({
                    'parcel': parcel,
                    'address': lead['property_address'],
                    'old_count': existing_count,
                    'new_count': total_count,
                    'new_types': list(added_types),
                    'score': new_score,
                    'activity_count': activity_count
                })
                
                # HOT ALERT if upgraded to HOT or got new activity
                if new_score == "HOT":
                    hot_alerts.append({
                        'parcel': parcel,
                        'address': lead['property_address'],
                        'document_count': total_count,
                        'document_types': '; '.join(sorted(all_types)),
                        'activity_count': activity_count
                    })
        
        else:
            # NEW PARCEL
            new_row = [
                lead['lead_score'],
                lead['document_count'],
                parcel,
                lead['property_address'],
                lead['grantors'],
                lead['grantees'],
                lead['document_types'],
                lead['recorded_dates'],
                lead['document_numbers'],
                timestamp,  # first_seen
                timestamp,  # last_updated
                1  # activity_count
            ]
            
            master_sheet.append_row(new_row)
            new_leads.append(lead)
    
    # Update Hot Alerts sheet
    update_hot_alerts_sheet(spreadsheet, hot_alerts, updated_leads)
    
    return new_leads, updated_leads, hot_alerts

def update_hot_alerts_sheet(spreadsheet, hot_alerts, updated_leads):
    """Update the Hot Alerts tab with latest activity"""
    try:
        hot_sheet = spreadsheet.worksheet("Hot Alerts")
        # Clear existing data (keep headers)
        hot_sheet.clear()
    except gspread.exceptions.WorksheetNotFound:
        hot_sheet = spreadsheet.add_worksheet(title="Hot Alerts", rows=500, cols=10)
    
    # Add headers
    headers = [
        'Alert Date', 'Parcel Number', 'Property Address', 'Document Count',
        'Activity Count', 'Document Types', 'Status'
    ]
    hot_sheet.update('A1:G1', [headers])
    
    # Add hot alerts
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    rows = []
    
    for alert in hot_alerts:
        rows.append([
            timestamp,
            alert['parcel'],
            alert['address'],
            alert['document_count'],
            alert['activity_count'],
            alert['document_types'],
            'NEW ACTIVITY' if alert['activity_count'] > 1 else 'NEW HOT LEAD'
        ])
    
    if rows:
        hot_sheet.append_rows(rows)
        print(f"🔥 Added {len(rows)} hot alerts to Hot Alerts tab")

def send_email_alert(new_leads, updated_leads, hot_alerts):
    """Send email summary of daily activity"""
    
    recipient = os.getenv('OWNER_EMAIL')
    if not recipient:
        print("⚠️  OWNER_EMAIL not set, skipping email")
        return
    
    # Build email content
    subject = f"Cuyahoga Probate Leads - {len(hot_alerts)} Hot Alerts, {len(updated_leads)} Updates"
    
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif;">
        <h2>🏛️ Cuyahoga Probate Daily Report</h2>
        <p><strong>Date:</strong> {datetime.now().strftime('%Y-%m-%d %I:%M %p')}</p>
        
        <hr>
        
        <h3>🔥 Hot Alerts ({len(hot_alerts)})</h3>
        <p>Parcels with 2+ documents or new activity on existing hot leads:</p>
        <table border="1" cellpadding="5" style="border-collapse: collapse;">
            <tr style="background-color: #f0f0f0;">
                <th>Parcel</th>
                <th>Address</th>
                <th>Docs</th>
                <th>Activity Count</th>
                <th>Types</th>
            </tr>
    """
    
    for alert in hot_alerts[:20]:  # Top 20
        html_content += f"""
            <tr>
                <td>{alert['parcel']}</td>
                <td>{alert['address'][:50]}</td>
                <td>{alert['document_count']}</td>
                <td>{alert['activity_count']}</td>
                <td>{alert['document_types'][:60]}</td>
            </tr>
        """
    
    html_content += f"""
        </table>
        
        <hr>
        
        <h3>📊 Summary</h3>
        <ul>
            <li><strong>New Leads:</strong> {len(new_leads)}</li>
            <li><strong>Updated Leads:</strong> {len(updated_leads)}</li>
            <li><strong>Hot Alerts:</strong> {len(hot_alerts)}</li>
        </ul>
        
        <p><a href="https://sheets.google.com">View Full Sheet</a></p>
        
        <hr>
        <p style="color: #888; font-size: 12px;">
            Automated by Cuyahoga Probate Scraper<br>
            To stop receiving these emails, remove OWNER_EMAIL from Railway variables
        </p>
    </body>
    </html>
    """
    
    # Send email using SMTP
    smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
    smtp_port = int(os.getenv('SMTP_PORT', '587'))
    smtp_user = os.getenv('SMTP_USER')
    smtp_pass = os.getenv('SMTP_PASS')
    
    if not smtp_user or not smtp_pass:
        print("⚠️  SMTP credentials not set, skipping email")
        print("   Set SMTP_USER and SMTP_PASS in Railway variables")
        return
    
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = smtp_user
        msg['To'] = recipient
        
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        
        print(f"✉️  Email sent to {recipient}")
        
    except Exception as e:
        print(f"❌ Error sending email: {e}")

def main():
    """Test the deduplication system"""
    import glob
    
    client = get_sheets_client()
    
    # Find latest CSV
    csv_files = glob.glob("cuyahoga_leads_*.csv")
    if not csv_files:
        print("❌ No CSV files found")
        return
    
    latest_csv = max(csv_files, key=os.path.getctime)
    print(f"📁 Processing: {latest_csv}")
    
    new_leads, updated_leads, hot_alerts = process_daily_leads(latest_csv, client)
    
    print(f"\n📊 Results:")
    print(f"  🆕 New leads: {len(new_leads)}")
    print(f"  🔄 Updated leads: {len(updated_leads)}")
    print(f"  🔥 Hot alerts: {len(hot_alerts)}")
    
    if hot_alerts or updated_leads:
        send_email_alert(new_leads, updated_leads, hot_alerts)

if __name__ == "__main__":
    main()

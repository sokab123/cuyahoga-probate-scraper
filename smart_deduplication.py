#!/usr/bin/env python3
"""
Smart deduplication and parcel tracking system (BATCHED VERSION)
Compares daily scrapes against master sheet, tracks repeat activity, sends alerts

OPTIMIZED: Uses batch_update to avoid Google Sheets API quota errors
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
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]

    # Try env var first (for Railway/cloud), fall back to local file
    creds_json = os.getenv('GOOGLE_CREDENTIALS')
    if creds_json:
        creds_dict = json.loads(creds_json)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        # Look for credentials file next to this script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        creds_file = os.path.join(script_dir, 'google_credentials.json')
        if not os.path.exists(creds_file):
            raise Exception("No credentials found. Set GOOGLE_CREDENTIALS env var or add google_credentials.json")
        creds = ServiceAccountCredentials.from_json_keyfile_name(creds_file, scope)

    return gspread.authorize(creds)

def load_master_sheet(client, sheet_name="Cuyahoga Probate Leads"):
    """Load existing data from master sheet"""
    try:
        spreadsheet = client.open(sheet_name)
        master_sheet = spreadsheet.worksheet("Master")
        
        # Get all records
        records = master_sheet.get_all_records()
        
        # Index by parcel number AND grantor for fast lookup
        parcel_index = {}
        grantor_index = {}
        
        for idx, record in enumerate(records, start=2):  # Start at row 2 (after header)
            parcel = record.get('parcel_number', '').strip()
            grantors = record.get('grantors', '').strip()
            
            # Index by parcel
            if parcel:
                parcel_index[parcel] = {
                    'row': idx,
                    'record': record
                }
            
            # Index by grantor(s)
            if grantors:
                for grantor in grantors.split('; '):
                    grantor = grantor.strip()
                    if grantor:
                        if grantor not in grantor_index:
                            grantor_index[grantor] = []
                        grantor_index[grantor].append({
                            'row': idx,
                            'record': record
                        })
        
        return spreadsheet, master_sheet, parcel_index, grantor_index
        
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
        
        return spreadsheet, master_sheet, {}, {}

def process_daily_leads(daily_leads_file, client):
    """
    Process daily leads against master sheet (BATCHED VERSION)
    Returns: new_leads, updated_leads, hot_alerts
    """
    import csv
    
    # Load master data
    spreadsheet, master_sheet, parcel_index, grantor_index = load_master_sheet(client)
    
    # Read daily leads
    with open(daily_leads_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        daily_leads = list(reader)
    
    new_leads = []
    updated_leads = []
    hot_alerts = []
    
    # Batch update storage
    updates_to_apply = []  # {range, values}
    rows_to_append = []     # New rows to add
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    def safe_int(val, default=0):
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    def safe_str(val):
        if val is None:
            return ''
        return str(val)

    no_parcel_rows = []  # Track no-parcel records for Master sheet

    for lead in daily_leads:
        parcel = lead['parcel_number'].strip()
        
        # Handle no-parcel records separately — add to Master but skip dedup logic
        if not parcel:
            no_parcel_row = [
                'NO PARCEL',
                lead['document_count'],
                '',
                lead['property_address'],
                lead['grantors'],
                lead['grantees'],
                lead['document_types'],
                lead['recorded_dates'],
                lead['document_numbers'],
                timestamp,
                timestamp,
                1
            ]
            no_parcel_rows.append(no_parcel_row)
            continue
        
        # Check if parcel exists
        if parcel in parcel_index:
            # EXISTING PARCEL - Check if new documents added
            existing = parcel_index[parcel]['record']
            existing_count = safe_int(existing.get('document_count', 0))
            new_count = safe_int(lead['document_count'])
            
            # Get existing document types
            existing_types = set(safe_str(existing.get('document_types', '')).split('; '))
            new_types = set(safe_str(lead.get('document_types', '')).split('; '))
            
            # Check if there are truly new document types
            added_types = new_types - existing_types
            
            if added_types or new_count > existing_count:
                # UPDATE EXISTING ROW (batched)
                row_num = parcel_index[parcel]['row']
                
                # Merge document data
                all_types = existing_types | new_types
                all_grantors = set(safe_str(existing.get('grantors', '')).split('; ')) | set(safe_str(lead.get('grantors', '')).split('; '))
                all_grantees = set(safe_str(existing.get('grantees', '')).split('; ')) | set(safe_str(lead.get('grantees', '')).split('; '))
                all_doc_numbers = set(safe_str(existing.get('document_numbers', '')).split('; ')) | set(safe_str(lead.get('document_numbers', '')).split('; '))
                all_dates = set(safe_str(existing.get('recorded_dates', '')).split('; ')) | set(safe_str(lead.get('recorded_dates', '')).split('; '))
                
                # Remove empty strings
                all_types.discard('')
                all_grantors.discard('')
                all_grantees.discard('')
                all_doc_numbers.discard('')
                all_dates.discard('')
                
                total_count = len(all_doc_numbers)
                activity_count = safe_int(existing.get('activity_count', 1)) + 1
                
                # Determine new lead score
                new_score = "HOT" if total_count >= 2 else "WARM"
                
                # Prepare update
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
                
                updates_to_apply.append({
                    'range': f'A{row_num}:L{row_num}',
                    'values': [updated_row]
                })
                
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
            # Check if grantor exists (related activity)
            grantors_in_lead = [g.strip() for g in lead['grantors'].split('; ') if g.strip()]
            matched_by_grantor = any(g in grantor_index for g in grantors_in_lead)
            
            if matched_by_grantor:
                # SAME GRANTOR, DIFFERENT PARCEL - Flag as related activity
                matching_grantors = [g for g in grantors_in_lead if g in grantor_index]
                related_parcels = []
                
                for grantor in matching_grantors:
                    for match in grantor_index[grantor]:
                        related_parcels.append(match['record'].get('parcel_number'))
                
                # Add as new row but flag the relationship
                new_row = [
                    "HOT",  # Auto-HOT because related to existing grantor
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
                
                rows_to_append.append(new_row)
                new_leads.append(lead)
                
                # HOT ALERT for related grantor activity
                hot_alerts.append({
                    'parcel': parcel,
                    'address': lead['property_address'],
                    'document_count': safe_int(lead['document_count']),
                    'document_types': lead['document_types'],
                    'activity_count': 1,
                    'related_grantors': matching_grantors,
                    'related_parcels': related_parcels
                })
            
            else:
                # COMPLETELY NEW PARCEL AND GRANTOR
                new_row = [
                    lead['lead_score'],
                    lead['document_count'],
                    parcel if parcel else 'NO PARCEL',
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
                
                rows_to_append.append(new_row)
                new_leads.append(lead)
    
    # ✅ APPLY ALL UPDATES IN ONE BATCH
    if updates_to_apply:
        print(f"  📝 Batching {len(updates_to_apply)} updates...")
        master_sheet.batch_update(updates_to_apply)
    
    # ✅ APPEND ALL NEW ROWS IN ONE BATCH
    all_rows_to_append = rows_to_append + no_parcel_rows
    if all_rows_to_append:
        print(f"  ➕ Batching {len(rows_to_append)} new parcel rows + {len(no_parcel_rows)} no-parcel rows...")
        master_sheet.append_rows(all_rows_to_append)
    
    # Update Hot Alerts sheet
    update_hot_alerts_sheet(spreadsheet, hot_alerts, updated_leads, daily_leads)
    
    return new_leads, updated_leads, hot_alerts

def update_unknown_poa_sheet(spreadsheet, unknown_poa_records):
    """Update the Unknown POA tab with Power of Attorney records that have N/A grantor and grantee"""
    try:
        poa_sheet = spreadsheet.worksheet("Unknown POA")
        poa_sheet.clear()
    except gspread.exceptions.WorksheetNotFound:
        poa_sheet = spreadsheet.add_worksheet(title="Unknown POA", rows=500, cols=10)

    headers = [
        'Recorded Date', 'Document Number', 'Parcel Number',
        'Property Address', 'Legal Description', 'Document Type'
    ]
    poa_sheet.update('A1:F1', [headers])

    rows = []
    for r in unknown_poa_records:
        rows.append([
            r.get('recorded_date', ''),
            r.get('document_number', ''),
            r.get('parcel_number', ''),
            r.get('property_address', ''),
            r.get('legal_description', '')[:200],  # Trim long legal descriptions
            r.get('document_type', ''),
        ])

    if rows:
        poa_sheet.append_rows(rows)

    print(f"  📋 Unknown POA tab: {len(rows)} records")

def update_hot_alerts_sheet(spreadsheet, hot_alerts, updated_leads, daily_leads=None):
    """Update the Hot Alerts tab with latest activity (BATCHED) - APPEND MODE"""
    try:
        hot_sheet = spreadsheet.worksheet("Hot Alerts")
        # Check if headers exist, add if sheet is empty
        existing = hot_sheet.get_all_values()
        if not existing:
            headers = [
                'Alert Date', 'Parcel Number', 'Property Address', 'Document Count',
                'Activity Count', 'Document Types', 'Status'
            ]
            hot_sheet.update('A1:G1', [headers])
    except gspread.exceptions.WorksheetNotFound:
        hot_sheet = spreadsheet.add_worksheet(title="Hot Alerts", rows=1000, cols=10)
        headers = [
            'Alert Date', 'Parcel Number', 'Property Address', 'Document Count',
            'Activity Count', 'Document Types', 'Status'
        ]
        hot_sheet.update('A1:G1', [headers])
    
    # Prepare all rows to add
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    rows = []
    
    # Add dedup-triggered hot alerts (existing parcel with new activity or related grantor)
    for alert in hot_alerts:
        if alert['activity_count'] > 1:
            status = 'NEW ACTIVITY'
        elif alert.get('related_grantors'):
            status = 'RELATED GRANTOR'
        else:
            status = 'NEW HOT LEAD'

        rows.append([
            timestamp,
            alert['parcel'],
            alert['address'],
            alert['document_count'],
            alert['activity_count'],
            alert['document_types'],
            status
        ])
    
    # Also add HOT leads from today's scrape (2+ docs on same parcel in same day)
    if daily_leads:
        alerted_parcels = set(a['parcel'] for a in hot_alerts)
        for lead in daily_leads:
            parcel = lead.get('parcel_number', '').strip()
            if not parcel:
                continue
            if lead.get('lead_score') == 'HOT' and parcel not in alerted_parcels:
                rows.append([
                    timestamp,
                    parcel,
                    lead.get('property_address', ''),
                    lead.get('document_count', ''),
                    1,
                    lead.get('document_types', ''),
                    'NEW HOT LEAD'
                ])
                alerted_parcels.add(parcel)
    
    # ✅ BATCH APPEND ALL ROWS AT ONCE
    if rows:
        hot_sheet.append_rows(rows[:100])  # Limit to top 100 alerts
    
    print(f"  🔥 Hot Alerts: {len(rows)} total")

def send_email_alert(new_leads, updated_leads, hot_alerts):
    """Send email summary of hot activity"""
    
    if not hot_alerts and not updated_leads:
        print("  ✉️  No hot alerts to send")
        return
    
    # Email config from environment
    smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.getenv('SMTP_PORT', 587))
    smtp_user = os.getenv('SMTP_USER')
    smtp_pass = os.getenv('SMTP_PASS')
    owner_email = os.getenv('OWNER_EMAIL')
    
    if not all([smtp_user, smtp_pass, owner_email]):
        print("  ⚠️  Email credentials not configured (optional)")
        return
    
    # Build email
    subject = f"🔥 Cuyahoga Probate Alert: {len(hot_alerts)} Hot Leads"
    
    html_body = f"""
    <html>
    <body>
        <h2>Probate Lead Alert - {datetime.now().strftime('%Y-%m-%d')}</h2>
        
        <h3>🔥 Hot Alerts ({len(hot_alerts)})</h3>
        <table border="1" cellpadding="5" style="border-collapse: collapse;">
            <tr>
                <th>Parcel</th>
                <th>Address</th>
                <th>Doc Count</th>
                <th>Activity</th>
                <th>Types</th>
            </tr>
    """
    
    for alert in hot_alerts[:20]:  # Top 20
        html_body += f"""
            <tr>
                <td>{alert['parcel']}</td>
                <td>{alert['address']}</td>
                <td>{alert['document_count']}</td>
                <td>{alert['activity_count']}</td>
                <td>{alert['document_types']}</td>
            </tr>
        """
    
    html_body += """
        </table>
        
        <p><strong>New leads:</strong> {}</p>
        <p><strong>Updated leads:</strong> {}</p>
        
        <p>View full details in your <a href="https://docs.google.com/spreadsheets">Google Sheet</a></p>
    </body>
    </html>
    """.format(len([l for l in new_leads if l.get('lead_score') == 'HOT']), len(updated_leads))
    
    # Send email
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = smtp_user
        msg['To'] = owner_email
        
        msg.attach(MIMEText(html_body, 'html'))
        
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        
        print(f"  ✉️  Email sent to {owner_email}")
    
    except Exception as e:
        print(f"  ⚠️  Email failed: {e}")

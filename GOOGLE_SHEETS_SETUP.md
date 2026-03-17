# Google Sheets Integration Setup

## Overview
The scraper will automatically append daily results to a Google Sheet that you can access anytime.

---

## Setup Steps (10 minutes)

### 1. Create Google Cloud Project

1. Go to: https://console.cloud.google.com
2. Click "Select a project" → "New Project"
3. Name: `Cuyahoga Scraper`
4. Click "Create"

### 2. Enable Google Sheets API

1. In your new project, go to: https://console.cloud.google.com/apis/library
2. Search for: `Google Sheets API`
3. Click it, then click "Enable"
4. Also enable: `Google Drive API` (same process)

### 3. Create Service Account

1. Go to: https://console.cloud.google.com/iam-admin/serviceaccounts
2. Click "Create Service Account"
3. Name: `railway-scraper`
4. Click "Create and Continue"
5. Skip roles (click "Continue")
6. Click "Done"

### 4. Generate Credentials Key

1. Click on the service account you just created
2. Go to "Keys" tab
3. Click "Add Key" → "Create new key"
4. Choose "JSON"
5. Click "Create" (downloads a JSON file)
6. **Keep this file safe!**

### 5. Get Service Account Email

Open the JSON file you just downloaded. Find the line:
```json
"client_email": "railway-scraper@cuyahoga-scraper-xxxxx.iam.gserviceaccount.com"
```

Copy that email address.

### 6. Create Google Sheet

1. Go to: https://sheets.google.com
2. Create a new blank sheet
3. Name it: `Cuyahoga Probate Leads`
4. Click "Share" button (top right)
5. **Paste the service account email** from step 5
6. Give it "Editor" access
7. Click "Send" (ignore the warning about it being a service account)

### 7. Add Credentials to Railway

1. Open the JSON credentials file you downloaded
2. Copy the **entire contents** (all the JSON)
3. Go to your Railway project → Variables tab
4. Add a new variable:
   - Name: `GOOGLE_CREDENTIALS`
   - Value: *paste the entire JSON content*
5. Also add:
   - Name: `OWNER_EMAIL`
   - Value: *your email address* (so the sheet is shared with you too)
6. Click "Add" (Railway will redeploy)

---

## ✅ You're Done!

Tomorrow at 9 AM, the scraper will:
1. Pull Cuyahoga County records (last 14 days)
2. Score leads by parcel number
3. Automatically append to your Google Sheet
4. Add a timestamp to each batch

You can access the sheet anytime at: https://sheets.google.com

The sheet will have columns:
- Lead Score (HOT/WARM)
- Document Count
- Parcel Number
- Property Address
- Grantors
- Grantees
- Document Types
- Recorded Dates
- Document Numbers
- Last Updated (timestamp)

---

## Troubleshooting

**If upload fails:**
1. Check Railway logs for error messages
2. Verify the service account email has Editor access to the sheet
3. Confirm `GOOGLE_CREDENTIALS` is valid JSON (no extra spaces/line breaks)
4. Make sure both Google Sheets API and Google Drive API are enabled

**Sheet not showing data:**
- The sheet must be named exactly: `Cuyahoga Probate Leads`
- Or modify the script to use your custom sheet name

---

**Need help?** Paste any error messages from Railway logs and I'll debug.

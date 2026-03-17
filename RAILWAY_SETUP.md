# Railway Deployment - Final Steps

## ✅ Code Pushed to GitHub
Repository: https://github.com/sokab123/cuyahoga-probate-scraper

---

## Deploy to Railway (5 minutes)

### 1. Create New Project
Go to: https://railway.app/new

Click: **"Deploy from GitHub repo"**

### 2. Select Repository
Choose: `sokab123/cuyahoga-probate-scraper`

Railway will automatically:
- Detect Python
- Install dependencies from `requirements.txt`
- Install Playwright + Chromium browser
- Run the scraper

### 3. Add Environment Variable (Important!)

In Railway project settings → Variables, add:

```
PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright
```

This tells Playwright where to find Chromium in Railway's environment.

### 4. Set Up Daily Cron Schedule

**Option A: Railway Cron (Recommended)**
1. In your Railway project, go to Settings
2. Scroll to "Cron Schedule"
3. Enter: `0 9 * * *` (runs daily at 9 AM EST)
4. Save

**Option B: Use Railway's Scheduler Service**
1. Add a new service: "Cron Job"
2. Point it to the same GitHub repo
3. Schedule: Daily at 9 AM

### 5. Monitor First Run

After deployment:
1. Check the "Deployments" tab
2. View logs to confirm scraper runs successfully
3. Should see: "✅ Scrape complete!" with lead counts

---

## What Happens Daily

Every morning at 9 AM:
1. Scraper runs automatically
2. Searches last 14 days of Cuyahoga records
3. Finds probate trigger documents
4. Groups by parcel number
5. Scores leads (HOT = 2+ docs, WARM = 1 doc)
6. Saves CSV files

## Next: File Storage

Right now CSVs are generated but not persisted between runs. 

**Options:**
1. **Add Railway Volume** - Store CSVs permanently
2. **Email results** - Send CSV to you daily
3. **Google Sheets integration** - Append to master sheet
4. **Download via Railway dashboard** - Manual retrieval

Which would you prefer? Let me know and I'll set it up.

# Deployment Guide - Cuyahoga Probate Scraper

## Railway Deployment

### 1. Create New Railway Project

1. Go to https://railway.app
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Choose the repository with this scraper

### 2. Configure Build

Railway should auto-detect Python. If needed, add these environment variables:

```
PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
```

### 3. Set Up Cron Schedule

In Railway project settings:
- Go to "Cron" tab
- Add schedule: `0 9 * * *` (runs daily at 9 AM EST)
- Or use Railway's built-in scheduler

Alternative: Use Railway's cron syntax in `railway.json`

### 4. File Storage

**Option A: Railway Volumes**
- Mount a volume at `/data`
- Modify scraper to save CSVs to `/data/`
- CSVs persist between runs

**Option B: Email Results**
- Install `sendgrid` or similar
- Email CSV after each run
- No storage needed

**Option C: Upload to Google Sheets**
- Use `gspread` library
- Append to master sheet daily
- Best for Chris's workflow

### 5. Monitoring

Check logs in Railway dashboard to ensure:
- Scraper runs successfully
- Parcel count looks reasonable
- No errors

---

## Current Settings

- **Days back:** 14 days
- **Document types:** 5 (Power of Attorney, Transfer on Death variants, Survivorship)
- **Output:** CSV + JSON files
- **Runtime:** ~2-3 minutes per run

## Next Steps

1. Test deployment on Railway
2. Verify cron schedule
3. Set up notification system (email/Slack/Discord when HOT leads found)
4. Configure master CSV accumulation

# Push to GitHub - Quick Steps

## 1. Create the GitHub Repo

Go to: https://github.com/new

Fill in:
- **Repository name:** `cuyahoga-probate-scraper`
- **Description:** Automated scraper for Cuyahoga County probate trigger documents
- **Visibility:** Public
- **DO NOT** check "Initialize with README"

Click "Create repository"

## 2. Push Your Code

After creating the repo, GitHub will show you commands. Use these:

```bash
cd /Users/clawdbot/Documents/Stewart/cuyahoga-probate-scraper

git remote add origin https://github.com/sokab123/cuyahoga-probate-scraper.git
git branch -M main
git push -u origin main
```

## 3. Deploy to Railway

Once pushed to GitHub:

1. Go to https://railway.app
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Choose `sokab123/cuyahoga-probate-scraper`
5. Railway will auto-detect Python and deploy

## 4. Set Up Daily Cron

In Railway project:
1. Click on your service
2. Go to "Settings"
3. Under "Cron Schedule", add: `0 9 * * *` (runs daily at 9 AM EST)
4. Save

---

**That's it!** The scraper will run daily and save results to Railway's storage.

Let me know when you've pushed to GitHub, and I'll help with the Railway setup.

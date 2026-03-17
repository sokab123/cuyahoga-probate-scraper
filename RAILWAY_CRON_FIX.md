# Railway Cron Fix

Railway is treating this as a web service, but it's a cron job. Here's how to fix it:

## Option 1: Use Railway Cron (Recommended)

Railway has a built-in cron feature, but the service needs to be configured as a **cron job**, not a **web service**.

### Fix Steps:

1. In Railway, click on your service
2. Go to **Settings** tab
3. Scroll to **Service Settings**
4. Under **Service Type**, change from "Web Service" to **"Cron Job"**
5. Set **Cron Schedule**: `0 9 * * *`
6. Save

This tells Railway: "Don't restart this when it exits — run it on schedule."

---

## Option 2: Use a Sleep Loop (Workaround)

If Railway doesn't have the Cron Job option visible, I can modify the script to:
1. Run the scraper
2. Calculate time until next 9 AM
3. Sleep until then
4. Loop

This keeps the container alive.

---

## Option 3: External Cron Trigger

Use a free cron service to hit a Railway webhook:
- https://cron-job.org (free)
- Triggers Railway deployment daily
- Railway runs scraper on each deploy

---

**Which would you prefer?**

Try **Option 1** first (change service type to Cron Job). If you don't see that option, let me know and I'll implement Option 2.

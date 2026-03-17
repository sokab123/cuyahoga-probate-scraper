# Email Alert Setup

The scraper can send you daily email summaries of hot alerts and updated leads.

## Gmail Setup (Recommended)

### 1. Create App Password

1. Go to: https://myaccount.google.com/apppasswords
2. Select app: **Mail**
3. Select device: **Other (Custom name)**
4. Name it: `Cuyahoga Scraper`
5. Click **Generate**
6. **Copy the 16-character password** (you won't see it again)

### 2. Add to Railway Variables

In Railway project → Variables:

- **SMTP_HOST:** `smtp.gmail.com`
- **SMTP_PORT:** `587`
- **SMTP_USER:** Your full Gmail address (e.g., `chris@gmail.com`)
- **SMTP_PASS:** The 16-character app password you just generated

### 3. Done!

You'll receive emails with:
- 🔥 Hot Alerts (parcels with 2+ documents or new activity)
- 🔄 Updated Leads (existing parcels with new documents)
- 📊 Daily summary stats

---

## Alternative: SendGrid (if you don't use Gmail)

1. Sign up: https://sendgrid.com (free tier: 100 emails/day)
2. Create API key
3. Railway variables:
   - **SMTP_HOST:** `smtp.sendgrid.net`
   - **SMTP_PORT:** `587`
   - **SMTP_USER:** `apikey` (literally the word "apikey")
   - **SMTP_PASS:** Your SendGrid API key

---

## Email Format

You'll receive HTML emails with:

**Subject:** `Cuyahoga Probate Leads - X Hot Alerts, Y Updates`

**Content:**
- Table of hot alerts (parcel, address, document count, types)
- Summary stats (new/updated/hot leads)
- Link to Google Sheet

**When you receive emails:**
- Daily at 9 AM after scrape completes
- Only if there are hot alerts or updates
- No email if it's just new WARM leads (to avoid inbox spam)

---

## Troubleshooting

**Not receiving emails?**
- Check Railway logs for "✉️ Email sent" message
- Verify SMTP_USER and SMTP_PASS are correct
- Check spam folder
- Make sure OWNER_EMAIL is set to your actual email

**Gmail blocking sign-in?**
- Use App Password, not your regular Gmail password
- Enable "Less secure app access" (not recommended) OR use App Password (recommended)

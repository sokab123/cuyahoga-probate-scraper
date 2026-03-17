# Cuyahoga County Probate Lead Scraper

## Purpose
Scrapes Cuyahoga County Recorder's Office for probate trigger documents and identifies high-value leads based on multiple filings per parcel.

## Target Documents
1. Power of Attorney
2. Affidavit of Transfer on Death
3. Deed- Certificate of Transfer
4. Deed Transfer on Death
5. Deed Survivorship

## Strategy
- Pull index data (no login required)
- Group by parcel number
- Flag parcels with 2+ trigger documents (hot leads)
- Track over time to identify repeat activity

## Output
CSV with:
- Parcel Number
- Property Address
- Document Count
- Document Types
- Grantor/Grantee Names
- Date(s) Recorded
- Document Number(s)
- Lead Score (hot/warm)

## Automation
Daily scrapes via cron/Railway to build lead pipeline over time.

---

**Status:** In development
**Started:** 2026-03-17

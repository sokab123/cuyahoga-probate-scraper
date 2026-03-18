#!/usr/bin/env python3
"""
Cron wrapper that keeps the container alive
Runs the scraper on schedule and sleeps between runs
Updated: 2026-03-17 20:33 EST - Force redeploy
"""

import schedule
import time
from datetime import datetime
import subprocess
import sys

def run_scraper():
    """Run the scraper script"""
    print(f"\n{'='*60}")
    print(f"⏰ Cron triggered at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    try:
        # Run the scraper
        result = subprocess.run(
            ['python', 'cuyahoga_scraper_v3.py'],
            capture_output=False,
            text=True
        )
        
        if result.returncode == 0:
            print(f"\n✅ Scraper completed successfully")
        else:
            print(f"\n❌ Scraper exited with code {result.returncode}")
            
    except Exception as e:
        print(f"\n❌ Error running scraper: {e}")
    
    print(f"\n{'='*60}")
    print(f"⏸️  Sleeping until next run...")
    print(f"{'='*60}\n")

def main():
    """Main cron loop"""
    print("🏛️  Cuyahoga Probate Scraper - Cron Service")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📅 Schedule: Daily at 9:00 AM UTC (5:00 AM EST)")
    print(f"{'='*60}\n")
    
    # Schedule the job
    schedule.every().day.at("09:00").do(run_scraper)
    
    print("✅ Cron scheduler initialized")
    
    # Always run immediately on startup
    import os
    print("🚀 Running scraper immediately on startup...\n")
    run_scraper()
    
    print("\n⏳ Waiting for next scheduled run...\n")
    
    # Keep the service alive
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  Cron service stopped")
        sys.exit(0)

# Use Playwright's official Docker image with Python (match requirements.txt version)
FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy

# Set working directory
WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Verify Playwright installation
RUN playwright install chromium

# Run the scraper directly (Railway's cron will handle scheduling)
CMD ["python", "-u", "cuyahoga_scraper_v3.py"]

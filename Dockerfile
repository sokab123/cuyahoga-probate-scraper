# Start from Ubuntu base
FROM ubuntu:22.04

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install Python and system dependencies
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3-pip \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Install Playwright browsers with all dependencies
RUN playwright install --with-deps chromium

# Copy application code
COPY . .

# Run the scraper
CMD ["python3", "-u", "cuyahoga_scraper_v3.py"]

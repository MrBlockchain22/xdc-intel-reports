#!/bin/bash

# Navigate to repo
cd /root/xdc-intel-reports

# Pull latest changes from remote
git pull origin main

# Pull in .env values
export $(grep -v '^#' /root/xdc-intel/.env | xargs)

# --- Start of integrated update_readme_status_fields.py logic ---
python3 << 'END_PYTHON'
import re
from datetime import datetime
import pytz
import pandas as pd
import glob
import os

# Absolute Paths
readme_path = "/root/xdc-intel-reports/README.md"
large_transfers_pattern = "/root/xdc-intel-reports/data/large_transfers_*.csv"
usdc_transfers_pattern = "/root/xdc-intel-reports/data/usdc_bridge_transfers_*.csv"

# Load latest large transfers file safely
large_transfers_files = glob.glob(large_transfers_pattern)
if large_transfers_files:
    latest_transfers_file = max(large_transfers_files, key=os.path.getmtime)
    try:
        transfers_df = pd.read_csv(latest_transfers_file)
        if transfers_df.empty or 'timestamp' not in transfers_df.columns:
            transfers_df = pd.DataFrame()
    except (pd.errors.EmptyDataError, pd.errors.ParserError):
        transfers_df = pd.DataFrame()
else:
    transfers_df = pd.DataFrame()

# Load latest USDC.e transfers file safely
usdc_transfers_files = glob.glob(usdc_transfers_pattern)
if usdc_transfers_files:
    latest_usdc_file = max(usdc_transfers_files, key=os.path.getmtime)
    try:
        usdc_transfers_df = pd.read_csv(latest_usdc_file)
        if usdc_transfers_df.empty or 'timestamp' not in usdc_transfers_df.columns:
            usdc_transfers_df = pd.DataFrame()
    except (pd.errors.EmptyDataError, pd.errors.ParserError):
        usdc_transfers_df = pd.DataFrame()
else:
    usdc_transfers_df = pd.DataFrame()

# Determine the most recent scan time
latest_scan_time = None
if large_transfers_files or usdc_transfers_files:
    latest_file = max(
        ([latest_transfers_file] if large_transfers_files else []) +
        ([latest_usdc_file] if usdc_transfers_files else []),
        key=os.path.getmtime
    )
    transfers_mtime = os.path.getmtime(latest_file)
    latest_scan_time = datetime.utcfromtimestamp(transfers_mtime).replace(tzinfo=pytz.utc)

# Format the latest scan time
if latest_scan_time:
    est_time = latest_scan_time.astimezone(pytz.timezone('US/Eastern'))
    scan_time = latest_scan_time.strftime("%Y-%m-%d %H:%M:%S UTC") + f" ({est_time.strftime('%I:%M %p EST')})"
else:
    scan_time = "Not Available"

# Prepare status values
last_large_transfer = f"Detected ({len(transfers_df)} transfers ≥ $5,000)" if len(transfers_df) > 0 else "None Detected"
last_usdc_transfer = f"Detected ({len(usdc_transfers_df)} transfers ≥ $5,000)" if len(usdc_transfers_df) > 0 else "None Detected"

# Read README
with open(readme_path, "r") as file:
    readme_content = file.read()

# Replace status fields (handle bold markdown and variable spacing)
readme_content = re.sub(r"\|\s*\*\*Last Scan Time\*\*\s*\|\s*.*", f"| **Last Scan Time**    | {scan_time}                             |", readme_content)
readme_content = re.sub(r"\|\s*\*\*Last Large Transfer\*\*\s*\|\s*.*", f"| **Last Large Transfer** | {last_large_transfer:<30} |", readme_content)

# Add or update Last USDC.e Transfer
if "**Last USDC.e Transfer**" not in readme_content:
    readme_content = readme_content.replace(
        "| **Last Large Transfer** |",
        "| **Last Large Transfer** |\n| **Last USDC.e Transfer** | {last_usdc_transfer:<30} |"
    )
else:
    readme_content = re.sub(r"\|\s*\*\*Last USDC.e Transfer\*\*\s*\|\s*.*", f"| **Last USDC.e Transfer** | {last_usdc_transfer:<30} |", readme_content)

# Remove USDC.e Bridge Balance if it exists
readme_content = re.sub(r"\|\s*\*\*USDC.e Bridge Balance\*\*\s*\|\s*.*\n?", "", readme_content)

# Remove other outdated fields
readme_content = re.sub(r"\|\s*\*\*Last Critical Movement\*\*\s*\|\s*.*\n?", "", readme_content)
readme_content = re.sub(r"\|\s*\*\*Last Smart Contract\*\*\s*\|\s*.*\n?", "", readme_content)

# Write updated README
with open(readme_path, "w") as file:
    file.write(readme_content)

print("[+] README.md updated successfully.")
END_PYTHON

# Check for changes and push if needed
git add README.md data/*.csv scripts/*.py scripts/*.sh

if git diff --cached --quiet; then
    echo "[*] No changes to commit."
else
    git commit -m "Automated Update: System Status Scan Time and Files $(date -u +%Y%m%d_%H%M%S)"
    git push
    echo "[+] Changes pushed to GitHub."
fi

# Post to X for large transfers
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Running post_to_x.py..." >> /root/xdc-intel/scan.log
python3 /root/xdc-intel-reports/scripts/post_to_x.py >> /root/xdc-intel/scan.log 2>&1

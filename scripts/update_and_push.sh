#!/bin/bash

# Navigate to repo
cd /root/xdc-intel-reports

# Pull latest changes from remote
git pull origin main

# Pull in .env values
export $(grep -v '^#' /root/xdc-intel/.env | xargs)

# --- Start of integrated update_readme_status_fields.py logic ---
# Required imports in bash (we'll use Python inline)
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
contracts_weekly_pattern = "/root/xdc-intel-reports/data/contracts_weekly_*.csv"

# Load latest large transfers file safely
large_transfers_files = glob.glob(large_transfers_pattern)
if large_transfers_files:
    latest_transfers_file = max(large_transfers_files, key=os.path.getctime)
    try:
        transfers_df = pd.read_csv(latest_transfers_file)
    except pd.errors.EmptyDataError:
        transfers_df = pd.DataFrame()
else:
    transfers_df = pd.DataFrame()

# Load latest contracts weekly file safely
contracts_files = glob.glob(contracts_weekly_pattern)
if contracts_files:
    latest_contracts_file = max(contracts_files, key=os.path.getctime)
    try:
        contracts_df = pd.read_csv(latest_contracts_file)
    except pd.errors.EmptyDataError:
        contracts_df = pd.DataFrame()
else:
    contracts_df = pd.DataFrame()

# Determine the most recent scan time
latest_scan_time = None
if large_transfers_files:
    transfers_mtime = os.path.getmtime(latest_transfers_file)
    latest_scan_time = datetime.utcfromtimestamp(transfers_mtime).replace(tzinfo=pytz.utc)
if contracts_files:
    contracts_mtime = os.path.getmtime(latest_contracts_file)
    contracts_time = datetime.utcfromtimestamp(contracts_mtime).replace(tzinfo=pytz.utc)
    if latest_scan_time:
        latest_scan_time = max(latest_scan_time, contracts_time)
    else:
        latest_scan_time = contracts_time

# Format the latest scan time
if latest_scan_time:
    est_time = latest_scan_time.astimezone(pytz.timezone('US/Eastern'))
    scan_time = latest_scan_time.strftime("%Y-%m-%d %H:%M:%S UTC") + f" ({est_time.strftime('%I:%M %p EST')})"
else:
    scan_time = "Not Available"

# Prepare status values
last_large_transfer = f"Detected ({len(transfers_df)} transfers ≥ $5,000)" if len(transfers_df) > 0 else "None Detected"
last_smart_contract = f"Detected ({len(contracts_df)} contracts)" if len(contracts_df) > 0 else "None Detected"

# Read README
with open(readme_path, "r") as file:
    readme_content = file.read()

# Replace status fields (handle bold markdown and variable spacing)
readme_content = re.sub(r"\|\s*\*\*Last Scan Time\*\*\s*\|\s*.*", f"| **Last Scan Time**    | {scan_time}                             |", readme_content)
readme_content = re.sub(r"\|\s*\*\*Last Threat Detected\*\*\s*\|\s*.*", f"| **Last Large Transfer** | {last_large_transfer:<30} |", readme_content)
readme_content = re.sub(r"\|\s*\*\*Last Critical Movement\*\*\s*\|\s*.*", f"| **Last Smart Contract** | {last_smart_contract:<30} |", readme_content)

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


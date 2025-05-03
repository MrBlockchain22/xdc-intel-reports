#!/bin/bash

# Navigate to repo
cd /root/xdc-intel-reports

# Pull latest changes from remote
git pull origin main

# Pull in .env values
export $(grep -v '^#' /root/xdc-intel/.env | xargs)

# Check for changes and push if needed
git add data/*.csv scripts/*.py scripts/*.sh

if git diff --cached --quiet; then
    echo "[*] No changes to commit."
else
    git commit -m "Automated Update: Latest CSV and Script Files $(date -u +%Y%m%d_%H%M%S)"
    git push
    echo "[+] Changes pushed to GitHub."
fi

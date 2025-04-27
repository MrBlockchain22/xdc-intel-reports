#!/bin/bash

cd /root/xdc-intel-reports

python3 update_readme_status.py

git add README.md
git commit -m "Automated Update: System Status Scan Time"
git push
python3 post_to_x.py

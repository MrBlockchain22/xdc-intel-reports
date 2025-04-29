import pandas as pd
from datetime import datetime
import pytz

# Load the latest bridge scam file
try:
    bridge_file = max(Path("data").glob("bridge_scam_hits_*.csv"), key=lambda p: p.stat().st_ctime)
    bridge_df = pd.read_csv(bridge_file)
except Exception:
    bridge_df = pd.DataFrame()

# Load the latest critical movement file
try:
    critical_file = max(Path("data").glob("critical_movements_*.csv"), key=lambda p: p.stat().st_ctime)
    critical_df = pd.read_csv(critical_file)
except Exception:
    critical_df = pd.DataFrame()

# Get current time
utc_now = datetime.now(pytz.utc)
utc_time_str = utc_now.strftime("%Y-%m-%d %H:%M:%S UTC")
est_now = utc_now.astimezone(pytz.timezone('US/Eastern'))
est_time_str = est_now.strftime("%I:%M %p EST")

# Determine statuses
last_threat = "Detected" if not bridge_df.empty and len(bridge_df) > 1 else "None Detected"
last_critical = "Detected" if not critical_df.empty and len(critical_df) > 1 else "None Detected"

# Read README.md
with open("README.md", "r") as f:
    lines = f.readlines()

# Update System Status section
new_lines = []
inside_table = False
for line in lines:
    if line.strip().startswith("| Metric"):
        inside_table = True
        new_lines.append(line)
        continue
    if inside_table:
        if line.strip().startswith("| Last Scan Time"):
            new_lines.append(f"| Last Scan Time | {utc_time_str} ({est_time_str}) |\n")
        elif line.strip().startswith("| Last Threat Detected"):
            new_lines.append(f"| Last Threat Detected | {last_threat} |\n")
        elif line.strip().startswith("| Last Critical Movement"):
            new_lines.append(f"| Last Critical Movement | {last_critical} |\n")
        else:
            if line.strip() == "":
                inside_table = False
                new_lines.append(line)
            else:
                continue
    else:
        new_lines.append(line)

# Write updated README.md
with open("README.md", "w") as f:
    f.writelines(new_lines)

print("[+] README System Status updated successfully.")

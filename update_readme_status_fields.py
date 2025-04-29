import re
from datetime import datetime
import pytz
import pandas as pd
import glob

# Paths
readme_path = "README.md"
bridge_hits_pattern = "data/bridge_scam_hits_*.csv"
critical_movements_pattern = "data/critical_movements_*.csv"

# Load latest bridge scan file
latest_bridge_file = max(glob.glob(bridge_hits_pattern), key=lambda f: f)
bridge_df = pd.read_csv(latest_bridge_file)

# Load latest critical movement file
latest_critical_file = max(glob.glob(critical_movements_pattern), key=lambda f: f)
critical_df = pd.read_csv(latest_critical_file)

# Prepare timestamps
utc_now = datetime.now(pytz.utc)
est_now = utc_now.astimezone(pytz.timezone('US/Eastern'))
scan_time = utc_now.strftime("%Y-%m-%d %H:%M:%S UTC") + f" ({est_now.strftime('%I:%M %p EST')})"

# Prepare status values
last_threat_detected = "Detected" if len(bridge_df) > 1 else "None Detected"
last_critical_movement = "Detected" if len(critical_df) > 1 else "None Detected"

# Read README
with open(readme_path, "r") as file:
    readme_content = file.read()

# Replace Last Scan Time
readme_content = re.sub(r"(Last Scan Time\s*\|\s*).*", f"Last Scan Time | {scan_time}", readme_content)

# Replace Last Threat Detected
readme_content = re.sub(r"(Last Threat Detected\s*\|\s*).*", f"Last Threat Detected | {last_threat_detected}", readme_content)

# Replace Last Critical Movement
readme_content = re.sub(r"(Last Critical Movement\s*\|\s*).*", f"Last Critical Movement | {last_critical_movement}", readme_content)

# Save back README
with open(readme_path, "w") as file:
    file.write(readme_content)

print("[+] README.md updated successfully.")

import tweepy
import os
import pandas as pd
import glob
from datetime import datetime
import pytz

# Load credentials
API_KEY = 'zxItFW1ex80dMwHgasu0wcmi0'
API_SECRET = 'bX3kLHdh6OmV3dHS6LgfgieOdVlbfTrvTvPDYPp5k6wAUkra3V'
ACCESS_TOKEN = '70089191-mPXkqngcvrh0pkrsxW1rISPXfFe748gyFQi80VS4e'
ACCESS_TOKEN_SECRET = 'sEi0fanDNBNcfrBo0XMQMSsGIIcgRcSciASG4vkkNbljo'

# Authenticate
auth = tweepy.OAuth1UserHandler(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
api = tweepy.API(auth)

# Find latest scan result
latest_scan_file = max(glob.glob('data/bridge_scam_hits_*.csv'), key=os.path.getctime)

# Check scan results
df = pd.read_csv(latest_scan_file)

# Get current time in UTC and EST
utc_now = datetime.now(pytz.utc)
utc_time = utc_now.strftime("%d %b %Y, %H:%M UTC")

est_now = utc_now.astimezone(pytz.timezone('US/Eastern'))
est_time = est_now.strftime("%I:%M %p EST")

# Build Post Text
if len(df) > 1:
    # Threats detected
    POST_TEXT = f"⚠️ ALERT: Potential threat detected during XDC latest scan.\n\n🕒 {utc_time} ({est_time})\n\nInvestigate immediately.\nFull report: https://github.com/MrBlockchain22/xdc-intel-reports 🛡️\n\n#xdc #xdcnetwork #cybersecurity #web3security @xdc_community"
else:
    # No threats
    POST_TEXT = f"✅ Threat scan complete.\n\nNo threats detected.\n🕒 {utc_time} ({est_time})\n\nProtecting @xdc_community from within. 🛡️\n\n#xdc #xdcnetwork #cybersecurity #web3security"

# Post to X
api.update_status(POST_TEXT)

print("[+] Posted successfully!")


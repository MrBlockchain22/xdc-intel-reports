import tweepy
import os
import pandas as pd
import glob

# Load credentials
API_KEY = 'zxItFW1ex80dMwHgasu0wcmi0'
API_SECRET = 'bX3kLHdh6OmV3dHS6LgfgieOdVlbfTrvTvPDYPp5k6wAUkra3V'
ACCESS_TOKEN = '70089191-mPXkqngcvrh0pkrsxW1rISPXfFe748gyFQi80VS4e'
ACCESS_TOKEN_SECRET = 'sEi0fanDNBNcfrBo0XMQMSsGIIcgRcSciASG4vkkNbljo'

# TEST MODE (True = only print, False = actually post)
TEST_MODE = True

# Authenticate
auth = tweepy.OAuth1UserHandler(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
api = tweepy.API(auth)

# Find latest scan result
latest_scan_file = max(glob.glob('data/bridge_scam_hits_*.csv'), key=os.path.getctime)

# Load CSV
df = pd.read_csv(latest_scan_file)

# 🛠 FORCE a fake alert for testing
force_fake_alert = True

if force_fake_alert or len(df) > 1:
    # Threats detected (either real or faked)
    POST_TEXT = "⚠️ ALERT: Potential threat detected during XDC scan. Investigate immediately. Full report: https://github.com/MrBlockchain22/xdc-intel-reports"
else:
    # No threats
    POST_TEXT = "✅ Threat scan complete. No threats found. XDC Network remains secure. #XDC #CyberSecurity #BlockchainSecurity"

# Post or print
if TEST_MODE:
    print("[TEST MODE] Would post:", POST_TEXT)
else:
    api.update_status(POST_TEXT)
    print("[+] Posted successfully!")

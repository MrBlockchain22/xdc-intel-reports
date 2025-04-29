import tweepy
import os
import pandas as pd
import glob

# Load credentials
API_KEY = 'zxItFW1ex80dMwHgasu0wcmi0'
API_SECRET = 'bX3kLHdh6OmV3dHS6LgfgieOdVlbfTrvTvPDYPp5k6wAUkra3V'
ACCESS_TOKEN = '70089191-mPXkqngcvrh0pkrsxW1rISPXfFe748gyFQi80VS4e'
ACCESS_TOKEN_SECRET = 'sEi0fanDNBNcfrBo0XMQMSsGIIcgRcSciASG4vkkNbljo'
BEARER_TOKEN = 'AAAAAAAAAAAAAAAAAAAAAFCZ0wEAAAAAsszFwpGlbw5aqgCjfE4a7bdMXCk%3DcWWjmik4jLUYQ99doSJVXB4vEZNfilcZC3CpbtcmCpfR6TNDO0' 

# Authenticate using Tweepy Client (V2)
client = tweepy.Client(
    bearer_token=BEARER_TOKEN,
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_TOKEN_SECRET
)

# Find latest scan result
latest_scan_file = max(glob.glob('data/bridge_scam_hits_*.csv'), key=os.path.getctime)

# Check scan results
df = pd.read_csv(latest_scan_file)

if len(df) > 1:
    # Threats detected
    POST_TEXT = "⚠️ ALERT: Potential threat detected during XDC latest scan.\n\nInvestigate immediately.\n\nProtecting @xdc_community. 🛡️\n\nFull report: https://github.com/MrBlockchain22/xdc-intel-reports\n\n#xdc #xdcnetwork #cybersecurity #web3security"
else:
    # No threats
    POST_TEXT = "✅ Threat scan complete.\n\nNo threats detected.\n\nProtecting @xdc_community from within. 🛡️\n\n#xdc #xdcnetwork #cybersecurity #web3security"

# Post to X
response = client.create_tweet(text=POST_TEXT)

print(f"[+] Posted successfully! Tweet ID: {response.data['id']}")



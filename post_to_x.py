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
latest_scan_file = max(glob.glob('data/critical_movements_*.csv'), key=os.path.getctime)

# Check scan results
df = pd.read_csv(latest_scan_file)

# Get current time in UTC and EST
utc_now = datetime.now(pytz.utc)
utc_time = utc_now.strftime("%d %b %Y, %H:%M UTC")
est_now = utc_now.astimezone(pytz.timezone('US/Eastern'))
est_time = est_now.strftime("%I:%M %p EST")

if len(df) > 1:
    # 🚨 Large Movements detected, start a thread
    first_post = f"⚠️ ALERT: Large bridge movements (>10K USDC) detected on XDC Network.\n🕒 {utc_time} ({est_time})\n\nFull report: https://github.com/MrBlockchain22/xdc-intel-reports 🛡️\n\n#xdc #xdcnetwork #cybersecurity #web3security @xdc_community"
    tweet = api.update_status(status=first_post)
    print("[+] First alert posted. Posting transaction details...")

    first_tweet_id = tweet.id

    # Post each transaction as a reply
    for index, row in df.iterrows():
        if index == 0:
            continue  # skip header row if necessary

        amount = float(row['amount'])
        tx_hash = row['hash']

        detail_text = f"🔹 Amount: {amount:,.2f} USDC\n🔹 TxHash: {tx_hash[:10]}...\n🔹 See: https://xdcscan.io/tx/{tx_hash}"

        reply = api.update_status(
            status=detail_text,
            in_reply_to_status_id=first_tweet_id,
            auto_populate_reply_metadata=True
        )
        first_tweet_id = reply.id  # Chain replies properly

    print("[+] Thread completed.")

else:
    # ✅ No large movements
    heartbeat_post = f"✅ Bridge scan complete.\n\nNo large movements (>10K USDC) detected.\n🕒 {utc_time} ({est_time})\n\nProtecting @xdc_community from within. 🛡️\n\n#xdc #xdcnetwork #cybersecurity #web3security"
    api.update_status(status=heartbeat_post)
    print("[+] Heartbeat posted successfully!")

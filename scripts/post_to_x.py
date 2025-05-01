import os
import glob
import pandas as pd
import pytz
import argparse
from datetime import datetime
import tweepy
from dotenv import load_dotenv

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Post updates to X for XDC Network scans.")
parser.add_argument("--type", choices=["large_transfers", "contracts_weekly"], required=True,
                    help="Type of data to post: 'large_transfers' or 'contracts_weekly'")
args = parser.parse_args()

# Load environment variables
load_dotenv(dotenv_path=os.path.expanduser("~/xdc-intel/.env"))

# Extract X API credentials
API_KEY = os.getenv("x_api_key")
API_SECRET = os.getenv("x_api_secret")
ACCESS_TOKEN = os.getenv("x_access_token")
ACCESS_TOKEN_SECRET = os.getenv("x_access_token_secret")

if not all([API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET]):
    raise EnvironmentError("❌ Missing X API credentials in .env")

# Authenticate with X using tweepy.Client
client = tweepy.Client(
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_TOKEN_SECRET
)

# Get current UTC and EST times
utc_now = datetime.now(pytz.utc)
utc_time = utc_now.strftime("%d %b %Y, %H:%M UTC")
est_now = utc_now.astimezone(pytz.timezone('US/Eastern'))
est_time = est_now.strftime("%I:%M %p EST")

# Tags for XDC accounts
xdc_tags = "@XDC_Network_ @XDCFoundation @xdc_community"

# Base directory for data files
data_dir = "/root/xdc-intel-reports/data"

if args.type == "large_transfers":
    # Find latest large transfers file
    try:
        latest_file = max(glob.glob(os.path.join(data_dir, "large_transfers_*.csv")), key=os.path.getctime)
    except ValueError:
        print("❌ No large_transfers files found.")
        exit(1)

    # Load scan results
    df = pd.read_csv(latest_file)

    # Check if any transfers are >= $5,000
    large_transfers_df = df[df["value_usd"] >= 5000]

    # Only post if there are large transfers
    if len(large_transfers_df) > 0:
        first_post = (
            f"💥 Big moves on #XDCNetwork! 🚀 {xdc_tags}\n"
            f"🕒 {utc_time} ({est_time})\n"
            f"💰 {len(large_transfers_df)} large transfers (≥ $5,000) detected! Details below 👇\n"
            f"📊 Report: https://github.com/MrBlockchain22/xdc-intel-reports"
        )
        tweet = client.create_tweet(text=first_post)
        print("[+] First large transfers post sent.")

        thread_id = tweet.data["id"]

        for index, row in large_transfers_df.iterrows():
            value_usd = float(row["value_usd"])
            value_xdc = float(row["value_xdc"])
            tx_hash = row["tx_hash"]
            token_symbol = row["token_symbol"]
            timestamp = row["timestamp"]

            detail_text = (
                f"🔥 {value_xdc:,.2f} {token_symbol} (${value_usd:,.2f}) transferred! 📈\n"
                f"⏰ {timestamp}\n"
                f"🔗 Tx: {tx_hash[:10]}... View on XDCScan: https://xdcscan.io/tx/{tx_hash}\n"
                f"🌐 #XDC #Blockchain"
            )

            reply = client.create_tweet(
                text=detail_text,
                in_reply_to_tweet_id=thread_id
            )
            thread_id = reply.data["id"]

        print("[✓] Full large transfers thread posted.")
    else:
        print("[✓] No large transfers (≥ $5,000) found. Skipping post to avoid noise.")

elif args.type == "contracts_weekly":
    # Find latest contracts weekly file
    try:
        latest_file = max(glob.glob(os.path.join(data_dir, "contracts_weekly_*.csv")), key=os.path.getctime)
    except ValueError:
        print("❌ No contracts_weekly files found.")
        exit(1)

    # Load scan results
    df = pd.read_csv(latest_file)

    # Count verified and unverified contracts
    verified_count = len(df[df["isVerified"] == True])
    unverified_count = len(df[df["isVerified"] == False])
    total_count = len(df)

    # Only post if there are smart contracts
    if total_count > 0:
        contract_word = "contract" if total_count == 1 else "contracts"
        summary_post = (
            f"🎉 Exciting week on #XDCNetwork! 🌐 {xdc_tags}\n"
            f"🚀 {total_count} new smart {contract_word} launched in the past 7 days! 📜\n"
            f"✅ Verified: {verified_count} | 🔍 Unverified: {unverified_count}\n"
            f"🕒 {utc_time} ({est_time})\n"
            f"📊 Details: https://github.com/MrBlockchain22/xdc-intel-reports #XDC"
        )
        client.create_tweet(text=summary_post)
        print("[✓] Smart contract summary posted.")
    else:
        print("[✓] No smart contracts found in the past 7 days. Skipping post to avoid noise.")

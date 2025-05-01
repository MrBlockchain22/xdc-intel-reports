import os
from pathlib import Path
import pandas as pd
import pytz
from datetime import datetime
import tweepy
from dotenv import load_dotenv

# Load .env file
load_dotenv("/root/xdc-intel/.env")

# Load X API credentials from .env
API_KEY = os.getenv("X_API_KEY")
API_SECRET = os.getenv("X_API_SECRET")
ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("X_ACCESS_TOKEN_SECRET")

# Validate credentials
if not all([API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET]):
    raise EnvironmentError("❌ Missing X API credentials in .env")

# Authenticate with X API v2
client = tweepy.Client(
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_TOKEN_SECRET
)

# Rest of the script
def get_est_time(utc_time):
    est_tz = pytz.timezone('US/Eastern')
    return utc_time.astimezone(est_tz)

def post_large_transfers(client, csv_dir="/root/xdc-intel-reports/data"):
    csv_files = list(Path(csv_dir).glob("large_transfers_*.csv"))
    if not csv_files:
        print("[!] No large transfer CSV files found.")
        return

    latest_csv = max(csv_files, key=lambda x: x.stat().st_mtime)
    df = pd.read_csv(latest_csv)
    qualifying_transfers = df[df["value_usd"] >= 5000]

    if qualifying_transfers.empty:
        print("[✓] No large transfers (≥ $5,000) found. Skipping post to avoid noise.")
        return

    utc_now = datetime.now(pytz.utc)
    est_now = get_est_time(utc_now)
    utc_time_str = utc_now.strftime("%d %b %Y, %H:%M UTC")
    est_time_str = est_now.strftime("%I:%M %p EST")
    total_transfers = len(qualifying_transfers)

    initial_text = (
        f"💥 Big moves on #XDCNetwork! 🚀 @XDC_Network_ @XDCFoundation @xdc_community\n"
        f"🕒 {utc_time_str} ({est_time_str})\n"
        f"💰 {total_transfers} large transfers (≥ $5,000) detected! Details below 👇\n"
        f"📊 Report: https://github.com/MrBlockchain22/xdc-intel-reports"
    )
    initial_tweet = client.create_tweet(text=initial_text)

    for _, row in qualifying_transfers.iterrows():
        value_xdc = float(row["value_xdc"])
        value_usd = float(row["value_usd"])
        token_symbol = row["token_symbol"]
        timestamp = row["timestamp"]
        tx_hash = row["tx_hash"]

        detail_text = (
            f"🔥 {value_xdc:,.2f} {token_symbol} (${value_usd:,.2f}) transferred! 📈\n"
            f"⏰ {timestamp}\n"
            f"🔗 Tx: {tx_hash[:10]}... View on XDCScan: https://xdcscan.io/tx/{tx_hash}\n"
            f"🌐 #XDC #Blockchain"
        )
        client.create_tweet(text=detail_text, in_reply_to_tweet_id=initial_tweet.data["id"])

def post_contracts_weekly(client, csv_dir="/root/xdc-intel-reports/data"):
    csv_files = list(Path(csv_dir).glob("contracts_weekly_*.csv"))
    if not csv_files:
        print("[!] No contracts weekly CSV files found.")
        return

    latest_csv = max(csv_files, key=lambda x: x.stat().st_mtime)
    df = pd.read_csv(latest_csv)

    if df.empty:
        print("[✓] No smart contracts found in the past 7 days. Skipping post to avoid noise.")
        return

    total_count = len(df)
    verified_count = len(df[df["isVerified"] == True])
    unverified_count = total_count - verified_count

    utc_now = datetime.now(pytz.utc)
    est_now = get_est_time(utc_now)
    utc_time_str = utc_now.strftime("%d %b %Y, %H:%M UTC")
    est_time_str = est_now.strftime("%I:%M %p EST")

    contract_word = "contract" if total_count == 1 else "contracts"
    summary_text = (
        f"🎉 Exciting week on #XDCNetwork! 🌐 @XDC_Network_ @XDCFoundation @xdc_community\n"
        f"🚀 {total_count} new smart {contract_word} launched in the past 7 days! 📜\n"
        f"✅ Verified: {verified_count} | 🔍 Unverified: {unverified_count}\n"
        f"🕒 {utc_time_str} ({est_time_str})\n"
        f"📊 Details: https://github.com/MrBlockchain22/xdc-intel-reports #XDC"
    )
    client.create_tweet(text=summary_text)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Post XDC Network updates to X.")
    parser.add_argument("--type", choices=["large_transfers", "contracts_weekly"], required=True, help="Type of update to post")
    args = parser.parse_args()

    if args.type == "large_transfers":
        post_large_transfers(client)
    elif args.type == "contracts_weekly":
        post_contracts_weekly(client)

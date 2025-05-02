#!/usr/bin/env python3
import os
import pandas as pd
from datetime import datetime
import pytz
from pathlib import Path
import tweepy
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/root/xdc-intel/.env')
API_KEY = os.getenv('TWITTER_API_KEY')
API_SECRET = os.getenv('TWITTER_API_SECRET')
ACCESS_TOKEN = os.getenv('TWITTER_ACCESS_TOKEN')
ACCESS_TOKEN_SECRET = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')

# Paths
DATA_DIR = Path('/root/xdc-intel-reports/data')
LOG_FILE = Path('/root/xdc-intel/scan.log')

# Twitter setup
auth = tweepy.OAuthHandler(API_KEY, API_SECRET)
auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
api = tweepy.API(auth)

# Logging function
def log_message(message):
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{timestamp}] {message}\n")

# Get the latest CSV file
def get_latest_csv(prefix):
    csv_files = list(DATA_DIR.glob(f"{prefix}_*.csv"))
    csv_files = [f for f in csv_files if not f.name.endswith('.tmp')]
    if not csv_files:
        return None
    return max(csv_files, key=lambda x: x.stat().st_mtime)

# Shorten address for display
def shorten_address(address):
    return f"{address[:6]}...{address[-4:]}"

# Shorten transaction hash for display
def shorten_tx_hash(tx_hash):
    return f"{tx_hash[:6]}..."

# Post to Twitter
def post_to_twitter():
    log_message("Starting post_to_x.py...")

    # Handle large XDC transfers (hourly)
    latest_xdc_csv = get_latest_csv("large_transfers")
    xdc_transfers = pd.DataFrame()
    if latest_xdc_csv:
        xdc_transfers = pd.read_csv(latest_xdc_csv)
        log_message(f"Found XDC transfers CSV: {latest_xdc_csv}")

    # Handle USDC.e transfers (daily)
    latest_usdc_csv = get_latest_csv("usdc_bridge_transfers")
    usdc_transfers = pd.DataFrame()
    if latest_usdc_csv:
        usdc_transfers = pd.read_csv(latest_usdc_csv)
        log_message(f"Found USDC.e transfers CSV: {latest_usdc_csv}")

    try:
        # Post XDC transfers (keep existing format for now)
        if not xdc_transfers.empty:
            for _, transfer in xdc_transfers.iterrows():
                tx_hash = transfer['tx_hash']
                value_xdc = transfer['value_xdc']
                value_usd = transfer['value_usd']
                token_symbol = transfer['token_symbol']
                timestamp = transfer['timestamp']
                # Convert timestamp to UTC and EST
                utc_time = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=pytz.UTC)
                est_time = utc_time.astimezone(pytz.timezone('US/Eastern'))
                utc_str = utc_time.strftime("%d %b %Y, %H:%M UTC")
                est_str = est_time.strftime("%I:%M %p EST")
                short_tx = shorten_tx_hash(tx_hash)
                tweet = (
                    f"Big moves on #XDCNetwork! 🚀\n"
                    f"{utc_str} ({est_str})\n"
                    f"1 large transfer (${value_usd:,.2f}) detected! 📈\n"
                    f"{value_xdc:,.2f} {token_symbol} (${value_usd:,.2f}) transferred\n"
                    f"From: {shorten_address(transfer['from'])}\n"
                    f"To: {shorten_address(transfer['to'])}\n"
                    f"{est_time.strftime('%d %b %Y, %I:%M %p EST')}\n"
                    f"Tx: {short_tx} View on XDCScan: xdcscan.io/tx/{tx_hash}\n"
                    f"#XDC #blockchain 🎉"
                )
                api.update_status(tweet)
                log_message(f"Posted XDC transfer: {tx_hash}")

        # Post USDC.e transfers in the same style
        if not usdc_transfers.empty:
            for _, transfer in usdc_transfers.iterrows():
                tx_hash = transfer['tx_hash']
                value_usdc = transfer['value_usdc']
                value_usd = transfer['value_usd']
                token_symbol = transfer['token_symbol']
                timestamp = transfer['timestamp']
                # Convert timestamp to UTC and EST
                utc_time = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=pytz.UTC)
                est_time = utc_time.astimezone(pytz.timezone('US/Eastern'))
                utc_str = utc_time.strftime("%d %b %Y, %H:%M UTC")
                est_str = est_time.strftime("%I:%M %p EST")
                short_tx = shorten_tx_hash(tx_hash)
                tweet = (
                    f"Big moves on #XDCNetwork! 🚀\n"
                    f"{utc_str} ({est_str})\n"
                    f"1 large {token_symbol} transfer (${value_usd:,.2f}) detected! 📈\n"
                    f"{value_usdc:,.2f} {token_symbol} (${value_usd:,.2f}) transferred\n"
                    f"From: {shorten_address(transfer['from'])}\n"
                    f"To: {shorten_address(transfer['to'])}\n"
                    f"{est_time.strftime('%d %b %Y, %I:%M %p EST')}\n"
                    f"Tx: {short_tx} View on XDCScan: xdcscan.io/tx/{tx_hash}\n"
                    f"#XDC #blockchain 🎉"
                )
                api.update_status(tweet)
                log_message(f"Posted USDC.e transfer: {tx_hash}")

        if xdc_transfers.empty and usdc_transfers.empty:
            log_message("No transfers to report. Skipping X post.")

    except Exception as e:
        log_message(f"Error posting to Twitter: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        post_to_twitter()
    except Exception as e:
        log_message(f"Error in post_to_twitter: {str(e)}")
        raise

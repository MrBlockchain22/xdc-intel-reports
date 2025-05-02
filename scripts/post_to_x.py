import os
import pandas as pd
from datetime import datetime
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

    # Get USDC.e bridge balance (placeholder until bridge address is confirmed)
    balance_file = DATA_DIR / "usdc_bridge_balance.txt"
    bridge_balance = "N/A"
    if balance_file.exists():
        with open(balance_file, 'r') as f:
            bridge_balance = float(f.read().strip())
        log_message(f"USDC.e bridge balance: {bridge_balance}")

    # Prepare summary tweet (only if there are transfers to report)
    summary_parts = []
    if not xdc_transfers.empty:
        summary_parts.append(f"- Large XDC Transfers: {len(xdc_transfers)}")
    if not usdc_transfers.empty:
        summary_parts.append(f"- USDC.e Transfers: {len(usdc_transfers)}")
    summary_parts.append(f"- USDC.e Bridge Balance: {bridge_balance} USDC.e (TBD)")
    summary_parts.append("Details: https://github.com/MrBlockchain22/xdc-intel-reports")

    try:
        last_tweet_id = None
        # Post summary tweet only if there are transfers
        if xdc_transfers.empty and usdc_transfers.empty:
            log_message("No transfers to report. Skipping X post.")
            return

        summary = "XDC Network Activity Report\n" + "\n".join(summary_parts)
        summary_tweet = api.update_status(summary)
        log_message("Posted summary tweet.")
        last_tweet_id = summary_tweet.id

        # Post XDC transfer details as replies
        for _, transfer in xdc_transfers.iterrows():
            tx_hash = transfer['tx_hash']
            value_xdc = transfer['value_xdc']
            value_usd = transfer['value_usd']
            token_symbol = transfer['token_symbol']
            tweet = (
                f"Large {token_symbol} Transfer\n"
                f"Amount: {value_xdc:,.2f} {token_symbol} (${value_usd:,.2f})\n"
                f"Tx: https://xdcscan.com/tx/{tx_hash}"
            )
            reply = api.update_status(tweet, in_reply_to_status_id=last_tweet_id)
            last_tweet_id = reply.id
            log_message(f"Posted XDC transfer: {tx_hash}")

        # Post USDC.e transfer details as replies
        for _, transfer in usdc_transfers.iterrows():
            tx_hash = transfer['tx_hash']
            value_usdc = transfer['value_usdc']
            value_usd = transfer['value_usd']
            token_symbol = transfer['token_symbol']
            tweet = (
                f"{token_symbol} Transfer\n"
                f"Amount: {value_usdc:,.2f} {token_symbol} (${value_usd:,.2f})\n"
                f"From: {transfer['from']}\n"
                f"To: {transfer['to']}\n"
                f"Tx: https://xdcscan.com/tx/{tx_hash}"
            )
            reply = api.update_status(tweet, in_reply_to_status_id=last_tweet_id)
            last_tweet_id = reply.id
            log_message(f"Posted USDC.e transfer: {tx_hash}")

    except Exception as e:
        log_message(f"Error posting to Twitter: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        post_to_twitter()
    except Exception as e:
        log_message(f"Error in post_to_twitter: {str(e)}")
        raise

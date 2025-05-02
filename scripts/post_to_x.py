import os
from pathlib import Path
import pandas as pd
import pytz
from datetime import datetime
import tweepy
from dotenv import load_dotenv
import logging
import time

# Set up logging to scan.log
logging.basicConfig(
    filename="/root/xdc-intel/scan.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Load .env file
load_dotenv("/root/xdc-intel/.env")

# Load X API credentials from .env
API_KEY = os.getenv("X_API_KEY")
API_SECRET = os.getenv("X_API_SECRET")
ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("X_ACCESS_TOKEN_SECRET")

# Validate credentials
if not all([API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET]):
    error_msg = "❌ Missing X API credentials in .env"
    logging.error(error_msg)
    raise EnvironmentError(error_msg)

# Authenticate with X API v2
try:
    client = tweepy.Client(
        consumer_key=API_KEY,
        consumer_secret=API_SECRET,
        access_token=ACCESS_TOKEN,
        access_token_secret=ACCESS_TOKEN_SECRET
    )
except Exception as e:
    error_msg = f"❌ Failed to authenticate with X API: {e}"
    logging.error(error_msg)
    raise

# Constants
TWEET_CHAR_LIMIT = 280  # Adjust if you're on X Premium with a higher limit
RATE_LIMIT_PAUSE = 60  # Seconds to pause after every 10 tweets
RATE_LIMIT_BATCH = 10  # Number of tweets before pausing

def get_est_time(utc_time):
    est_tz = pytz.timezone('US/Eastern')
    return utc_time.astimezone(est_tz)

def validate_tweet_length(text, max_length=TWEET_CHAR_LIMIT):
    if len(text) > max_length:
        logging.warning(f"Tweet too long ({len(text)} chars), truncating to {max_length}")
        return text[:max_length-3] + "..."
    return text

def post_large_transfers(client, csv_dir="/root/xdc-intel-reports/data"):
    # Find CSV files
    csv_files = list(Path(csv_dir).glob("large_transfers_*.csv"))
    if not csv_files:
        msg = "[!] No large transfer CSV files found."
        logging.info(msg)
        print(msg)
        return

    # Get the latest CSV
    latest_csv = max(csv_files, key=lambda x: x.stat().st_mtime)
    logging.info(f"Processing CSV: {latest_csv}")

    # Read and validate CSV
    try:
        df = pd.read_csv(latest_csv)
    except Exception as e:
        msg = f"[!] Error reading CSV {latest_csv}: {e}"
        logging.error(msg)
        print(msg)
        return

    # Validate required columns
    required_columns = ["value_usd", "value_xdc", "token_symbol", "timestamp", "tx_hash", "from", "to"]
    if not all(col in df.columns for col in required_columns):
        missing = [col for col in required_columns if col not in df.columns]
        msg = f"[!] Missing columns in CSV: {missing}"
        logging.error(msg)
        print(msg)
        return

    # Convert value columns to numeric, handle non-numeric values
    df["value_usd"] = pd.to_numeric(df["value_usd"], errors="coerce")
    df["value_xdc"] = pd.to_numeric(df["value_xdc"], errors="coerce")
    qualifying_transfers = df[df["value_usd"].notna() & (df["value_usd"] >= 5000)]

    if qualifying_transfers.empty:
        msg = "[✓] No large transfers (≥ $5,000) found. Skipping post to avoid noise."
        logging.info(msg)
        print(msg)
        return

    # Prepare timestamps for the summary
    utc_now = datetime.now(pytz.utc)
    est_now = get_est_time(utc_now)
    utc_time_str = utc_now.strftime("%d %b %Y, %H:%M UTC")
    est_time_str = est_now.strftime("%I:%M %p EST")
    total_transfers = len(qualifying_transfers)

    # Get the first transfer's details
    first_transfer = qualifying_transfers.iloc[0]
    value_xdc = float(first_transfer["value_xdc"])
    value_usd = float(first_transfer["value_usd"])
    token_symbol = first_transfer["token_symbol"]
    timestamp = first_transfer["timestamp"]
    tx_hash = first_transfer["tx_hash"]
    from_address = first_transfer["from"]
    to_address = first_transfer["to"]

    # Parse the timestamp and convert to EST
    try:
        utc_time = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=pytz.utc)
        est_time = get_est_time(utc_time)
        est_time_str_transfer = est_time.strftime("%d %b %Y, %I:%M %p EST")
    except Exception as e:
        msg = f"[!] Error parsing timestamp {timestamp}: {e}"
        logging.error(msg)
        print(msg)
        return

    # Create the initial tweet with the first transfer's details
    initial_text = (
        f"💥 Big moves on #XDCNetwork! 🚀 @XDC_Network_ @XDCFoundation @xdc_community\n"
        f"🕒 {utc_time_str} ({est_time_str})\n"
        f"💰 {total_transfers} large transfers (≥ $5,000) detected! Details below 👇\n"
        f"🔥 {value_xdc:,.2f} {token_symbol} (${value_usd:,.2f}) transferred! 📈\n"
        f"📤 From: {from_address[:6]}...{from_address[-4:]}\n"
        f"📥 To: {to_address[:6]}...{to_address[-4:]}\n"
        f"⏰ {est_time_str_transfer}\n"
        f"🔗 Tx: {tx_hash[:10]}... View on XDCScan: https://xdcscan.io/tx/{tx_hash}\n"
        f"🌐 #XDC #Blockchain"
    )
    initial_text = validate_tweet_length(initial_text)

    # Post initial tweet
    try:
        initial_tweet = client.create_tweet(text=initial_text)
        logging.info(f"Posted initial tweet: {initial_text}")
    except Exception as e:
        msg = f"[!] Failed to post initial tweet: {e}"
        logging.error(msg)
        print(msg)
        return

    # If there are more transfers, post them as threaded replies
    if total_transfers > 1:
        for i, (_, row) in enumerate(qualifying_transfers.iloc[1:].iterrows(), start=1):
            try:
                value_xdc = float(row["value_xdc"])
                value_usd = float(row["value_usd"])
                token_symbol = row["token_symbol"]
                timestamp = row["timestamp"]
                tx_hash = row["tx_hash"]
                from_address = row["from"]
                to_address = row["to"]

                # Parse the timestamp for the reply
                utc_time = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=pytz.utc)
                est_time = get_est_time(utc_time)
                est_time_str_reply = est_time.strftime("%d %b %Y, %I:%M %p EST")

                detail_text = (
                    f"🔥 {value_xdc:,.2f} {token_symbol} (${value_usd:,.2f}) transferred! 📈\n"
                    f"📤 From: {from_address[:6]}...{from_address[-4:]}\n"
                    f"📥 To: {to_address[:6]}...{to_address[-4:]}\n"
                    f"⏰ {est_time_str_reply}\n"
                    f"🔗 Tx: {tx_hash[:10]}... View on XDCScan: https://xdcscan.io/tx/{tx_hash}\n"
                    f"🌐 #XDC #Blockchain"
                )
                detail_text = validate_tweet_length(detail_text)

                client.create_tweet(text=detail_text, in_reply_to_tweet_id=initial_tweet.data["id"])
                logging.info(f"Posted detail tweet for tx {tx_hash[:10]}: {detail_text}")

                # Handle rate limits
                if (i + 1) % RATE_LIMIT_BATCH == 0:
                    logging.info(f"Pausing for {RATE_LIMIT_PAUSE} seconds to avoid rate limits...")
                    time.sleep(RATE_LIMIT_PAUSE)

            except Exception as e:
                msg = f"[!] Failed to post detail tweet for tx {tx_hash[:10]}: {e}"
                logging.error(msg)
                print(msg)
                continue

if __name__ == "__main__":
    logging.info("Starting post_to_x.py script")
    post_large_transfers(client)
    logging.info("Finished post_to_x.py script")

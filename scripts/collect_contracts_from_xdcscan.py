import requests
import pandas as pd
from datetime import datetime, timedelta
import time
from pathlib import Path
import json
import os
from tqdm import tqdm
from dotenv import load_dotenv

# Load .env file
load_dotenv("/root/xdc-intel/.env")

# Constants
XDCSCAN_API_KEY = os.getenv("XDCSCAN_API_KEY")
if not XDCSCAN_API_KEY:
    raise EnvironmentError("❌ Missing XDCSCAN_API_KEY in .env")
BASE_URL = "https://api.xdcscan.io/api"
BLOCKS_PER_BATCH = 1000
SLEEP_BETWEEN_REQUESTS = 1
CHECKPOINT_FILE = "/root/xdc-intel-reports/data/contracts_checkpoint.json"
XDC_BLOCK_TIME = 2  # Average block time in seconds (XDC Network)

# Helper Functions
def get_latest_block():
    url = f"{BASE_URL}?module=proxy&action=eth_blockNumber&apikey={XDCSCAN_API_KEY}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if "result" in data:
            # Convert hex to int (e.g., "0x123abc" to decimal)
            return int(data["result"], 16)
        else:
            print(f"[!] API Error: {data.get('message', 'Unknown error')}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"[!] Network Error: {str(e)}")
        return None

def estimate_block_range(days=7):
    end_block = get_latest_block()
    if not end_block:
        return None, None
    # Estimate blocks for 7 days (7 days * 24 hours * 60 minutes * 60 seconds / 2 seconds per block)
    blocks_in_7_days = int((days * 24 * 60 * 60) / XDC_BLOCK_TIME)
    start_block = end_block - blocks_in_7_days
    return start_block, end_block

def get_block_transactions(start_block, end_block):
    transactions = []
    for block in range(start_block, end_block + 1):
        url = f"{BASE_URL}?module=block&action=getblocktxs&blockno={block}&apikey={XDCSCAN_API_KEY}"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data["status"] == "1":
                transactions.extend(data["result"])
            else:
                print(f"[!] API Error for block {block}: {data.get('message', 'Unknown error')}")
        except requests.exceptions.RequestException as e:
            print(f"[!] Network Error for block {block}: {str(e)}")
        time.sleep(SLEEP_BETWEEN_REQUESTS)
    return transactions

def get_contract_details(address):
    url = f"{BASE_URL}?module=contract&action=getsourcecode&address={address}&apikey={XDCSCAN_API_KEY}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data["status"] == "1" and data["result"]:
            contract = data["result"][0]
            return {
                "address": address,
                "contractName": contract.get("ContractName", "Unknown"),
                "symbol": contract.get("Symbol", "N/A"),
                "compilerVersion": contract.get("CompilerVersion", "Unknown"),
                "license": contract.get("LicenseType", "Unknown"),
                "isVerified": contract.get("SourceCode") != "",
                "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
            }
        return None
    except requests.exceptions.RequestException as e:
        print(f"[!] Network Error for contract {address}: {str(e)}")
        return None

def load_checkpoint():
    if Path(CHECKPOINT_FILE).exists():
        with open(CHECKPOINT_FILE, "r") as f:
            return json.load(f)
    return {"last_processed_block": None, "contracts": []}

def save_checkpoint(last_block, contracts):
    checkpoint = {"last_processed_block": last_block, "contracts": contracts}
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(checkpoint, f)

# Main Script
if __name__ == "__main__":
    # Estimate block range for the last 7 days
    start_block, end_block = estimate_block_range(days=7)

    if not start_block or not end_block:
        print("[!] Failed to fetch block numbers.")
        exit(1)

    print(f"[+] Scanning from block {start_block} to {end_block} (last 7 days)...")

    # Load checkpoint
    checkpoint = load_checkpoint()
    last_processed_block = checkpoint["last_processed_block"] or start_block
    all_contracts = checkpoint["contracts"]

    # Scan in batches
    block_range = list(range(last_processed_block, end_block + 1, BLOCKS_PER_BATCH))
    for i in tqdm(range(len(block_range)), desc="Scanning Batches"):
        batch_start = block_range[i]
        batch_end = min(batch_start + BLOCKS_PER_BATCH - 1, end_block)
        transactions = get_block_transactions(batch_start, batch_end)

        # Process transactions to find contract creations
        for tx in transactions:
            if "contractAddress" in tx and tx["contractAddress"]:
                contract_details = get_contract_details(tx["contractAddress"])
                if contract_details:
                    all_contracts.append(contract_details)

        # Save checkpoint after each batch
        save_checkpoint(batch_end, all_contracts)
        time.sleep(SLEEP_BETWEEN_REQUESTS)

    # Save final results to CSV
    if all_contracts:
        df = pd.DataFrame(all_contracts)
        output_dir = Path("/root/xdc-intel-reports/data")
        output_dir.mkdir(exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"contracts_weekly_{timestamp}.csv"
        df.to_csv(output_file, index=False)
        print(f"[+] Saved {len(df)} contracts to {output_file}")
    else:
        print("[!] No contracts found.")

    # Clean up checkpoint file
    if Path(CHECKPOINT_FILE).exists():
        Path(CHECKPOINT_FILE).unlink()

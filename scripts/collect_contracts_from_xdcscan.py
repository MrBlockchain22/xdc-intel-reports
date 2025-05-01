import requests
import time
import csv
import os
from datetime import datetime, timedelta
from tqdm import tqdm
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv(dotenv_path=os.path.expanduser("~/xdc-intel/.env"))

API_KEY = os.getenv("XDCSCAN_API_KEY")
if not API_KEY:
    raise EnvironmentError("Missing 'XDCSCAN_API_KEY' in .env file.")

BASE_URL = "https://api.xdcscan.com/api"
BLOCK_STEP = 100  # Process 100 blocks per batch
DELAY = 0.3       # 3 calls/sec max (XDCScan rate limit)
DAYS_TO_SCAN = 7  # Scan the last 7 days
BLOCKS_PER_DAY = 1800 * 24  # ~1800 blocks/hour * 24 hours = ~43,200 blocks/day

# File paths
data_dir = "data"
output_file = os.path.join(data_dir, f"contracts_weekly_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv")

# Headers for the output CSV
headers = ["address", "contractName", "symbol", "compilerVersion", "license", "isVerified", "timestamp"]

# Ensure data folder and CSV exist
os.makedirs(data_dir, exist_ok=True)

if not os.path.exists(output_file):
    with open(output_file, "w", newline="") as f:
        csv.writer(f).writerow(headers)

def get_latest_block():
    url = f"{BASE_URL}?module=proxy&action=eth_blockNumber&apikey={API_KEY}"
    try:
        response = requests.get(url)
        data = response.json()
        return int(data["result"], 16) if "result" in data else None
    except Exception as e:
        print(f"[!] Error getting latest block: {e}")
        return None

def get_block_timestamp(block_number):
    url = f"{BASE_URL}?module=proxy&action=eth_getBlockByNumber&tag={hex(block_number)}&boolean=true&apikey={API_KEY}"
    try:
        response = requests.get(url)
        data = response.json()
        if "result" in data and "timestamp" in data["result"]:
            return int(data["result"]["timestamp"], 16)
    except Exception as e:
        print(f"[!] Error getting timestamp for block {block_number}: {e}")
    return None

def get_transactions_in_block(block_number):
    url = f"{BASE_URL}?module=proxy&action=eth_getBlockByNumber&tag={hex(block_number)}&boolean=true&apikey={API_KEY}"
    try:
        response = requests.get(url)
        data = response.json()
        if "result" in data and data["result"] and "transactions" in data["result"]:
            return data["result"]["transactions"], int(data["result"]["timestamp"], 16)
    except Exception as e:
        print(f"[!] Error getting transactions for block {block_number}: {e}")
    return [], None

def get_contract_info(address):
    url = f"{BASE_URL}?module=contract&action=getsourcecode&address={address}&apikey={API_KEY}"
    try:
        response = requests.get(url)
        data = response.json()
        if data["status"] == "1" and data["result"]:
            return data["result"][0]
    except Exception as e:
        print(f"[!] Error getting contract info for {address}: {e}")
    return None

# Get the latest block
latest_block = get_latest_block()
if not latest_block:
    print("[!] Failed to get the latest block.")
    exit(1)

# Estimate the starting block for 7 days ago
estimated_blocks = BLOCKS_PER_DAY * DAYS_TO_SCAN  # ~302,400 blocks for 7 days
start_block = max(0, latest_block - estimated_blocks)

# Adjust start_block to exactly 7 days ago by checking timestamps
seven_days_ago = int((datetime.utcnow() - timedelta(days=DAYS_TO_SCAN)).timestamp())
while True:
    timestamp = get_block_timestamp(start_block)
    time.sleep(DELAY)
    if timestamp is None:
        print("[!] Failed to get block timestamp.")
        exit(1)
    if timestamp < seven_days_ago:
        start_block += 1000  # Move forward in batches of 1000 blocks
    else:
        break

print(f"[+] Scanning from block {start_block} to {latest_block} (last 7 days)...")

# Collect contracts
contract_rows = []
for batch_start in tqdm(range(start_block, latest_block + 1, BLOCK_STEP), desc="Scanning Batches"):
    batch_end = min(batch_start + BLOCK_STEP - 1, latest_block)

    for block_num in range(batch_start, batch_end + 1):
        txs, block_timestamp = get_transactions_in_block(block_num)
        time.sleep(DELAY)

        for tx in txs:
            if tx.get("to") is None and tx.get("contractAddress"):
                address = tx["contractAddress"]
                info = get_contract_info(address)
                time.sleep(DELAY)

                # Convert block timestamp to human-readable format
                timestamp_str = datetime.utcfromtimestamp(block_timestamp).strftime('%Y-%m-%d %H:%M:%S')

                if info:
                    if info["ABI"] == "Contract source code not verified":
                        contract_rows.append([address, "", "", "", "", "False", timestamp_str])
                    else:
                        contract_rows.append([
                            address,
                            info.get("ContractName", ""),
                            info.get("Symbol", ""),
                            info.get("CompilerVersion", ""),
                            info.get("LicenseType", ""),
                            "True",
                            timestamp_str
                        ])

# Write results to CSV
if contract_rows:
    with open(output_file, "a", newline="") as f:
        csv.writer(f).writerows(contract_rows)

# Count verified and unverified contracts
verified_count = sum(1 for row in contract_rows if row[5] == "True")
unverified_count = sum(1 for row in contract_rows if row[5] == "False")
total_count = len(contract_rows)

print(f"[✓] Found {total_count} contracts: {verified_count} verified, {unverified_count} unverified.")
print(f"[✓] Data saved to {output_file}")

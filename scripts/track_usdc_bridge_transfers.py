#!/usr/bin/env python3
import os
import time
import json
from datetime import datetime
from web3 import Web3
from web3.middleware import geth_poa_middleware
import pandas as pd
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv('/root/xdc-intel/.env')
XDCSCAN_API_KEY = os.getenv('XDCSCAN_API_KEY')
COINMARKETCAP_API_KEY = os.getenv('COINMARKETCAP_API_KEY')

# Constants
USDC_E_ADDRESS = "0x2A8E898b6242355c290E1f4Fc966b8788729A4D4"  # USDC.e token contract
BRIDGE_ADDRESS = None  # To be determined; placeholder for now
RPC_URLS = [
    "https://rpc.xinfin.network",
    "https://rpc1.xinfin.network",
    "https://erpc.xinfin.network"
]
BLOCKS_PER_DAY = 43200  # ~1 day of blocks (24 * 60 * 60 / 2)
BATCH_SIZE = 1000  # Reduced to avoid RPC limitations
TRANSFER_THRESHOLD_USD = 5000  # $5,000 threshold
DATA_DIR = Path('/root/xdc-intel-reports/data')
LOG_FILE = Path('/root/xdc-intel/usdc_bridge_transfers.log')
LAST_BLOCK_FILE = Path('/root/xdc-intel/last_block_usdc.txt')
PRICE_CACHE_FILE = Path('/root/xdc-intel/usdc_price_cache.json')
PRICE_CACHE_DURATION = 600  # 10 minutes in seconds

# USDC.e ABI (including Transfer event)
USDC_E_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": False, "name": "value", "type": "uint256"}
        ],
        "name": "Transfer",
        "type": "event"
    }
]

# Initialize Web3 with failover
def get_web3():
    for rpc_url in RPC_URLS:
        try:
            w3 = Web3(Web3.HTTPProvider(rpc_url))
            # Add PoA middleware for XDC Network
            w3.middleware_onion.inject(geth_poa_middleware, layer=0)
            if w3.is_connected():
                log_message(f"Connected to RPC: {rpc_url}")
                return w3
        except Exception as e:
            log_message(f"Failed to connect to RPC {rpc_url}: {str(e)}")
    raise Exception("All RPC endpoints failed")

# Logging function
def log_message(message):
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{timestamp}] {message}\n")

# Get or cache USDC price
def get_usdc_price():
    if PRICE_CACHE_FILE.exists():
        with open(PRICE_CACHE_FILE, 'r') as f:
            cache = json.load(f)
        if time.time() - cache['timestamp'] < PRICE_CACHE_DURATION:
            log_message("Using cached USDC price")
            return cache['price']

    # Fetch from CoinMarketCap Sandbox API
    import requests
    url = "https://sandbox-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
    headers = {"X-CMC_PRO_API_KEY": COINMARKETCAP_API_KEY}
    params = {"symbol": "USDC", "convert": "USD"}
    log_message("Fetching USDC price from CoinMarketCap Sandbox API")
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        log_message(f"CMC API response: {data}")
        price = data['data']['USDC']['quote']['USD']['price']
        with open(PRICE_CACHE_FILE, 'w') as f:
            json.dump({'timestamp': time.time(), 'price': price}, f)
        return price
    except Exception as e:
        log_message(f"Error fetching USDC price: {str(e)}")
        return 1.0  # Assume 1:1 if API fails (since USDC is a stablecoin)

# Get the last processed block
def get_last_block():
    if LAST_BLOCK_FILE.exists():
        with open(LAST_BLOCK_FILE, 'r') as f:
            last_block = int(f.read().strip())
            log_message(f"Last processed block from file: {last_block}")
            return last_block
    w3 = get_web3()
    last_block = w3.eth.block_number - BLOCKS_PER_DAY
    log_message(f"No last block file found. Defaulting to {last_block}")
    return last_block

# Save the last processed block
def save_last_block(block):
    with open(LAST_BLOCK_FILE, 'w') as f:
        f.write(str(block))
    log_message(f"Saved last block: {block}")

# Fetch USDC.e transfers using Web3.py
def fetch_usdc_transfers(start_block, end_block):
    transfers = []
    w3 = get_web3()
    contract = w3.eth.contract(address=USDC_E_ADDRESS, abi=USDC_E_ABI)
    decimals = 6  # USDC.e uses 6 decimals

    log_message(f"Fetching transfers for USDC.e contract {USDC_E_ADDRESS} from block {start_block} to {end_block}")

    try:
        # Fetch Transfer events
        transfer_filter = contract.events.Transfer.create_filter(fromBlock=start_block, toBlock=end_block)
        events = transfer_filter.get_all_entries()
        if not events:
            log_message(f"No Transfer events found between blocks {start_block} and {end_block}")
        for event in events:
            value = event['args']['value'] / (10 ** decimals)
            block = event['blockNumber']
            # Fetch block to get timestamp
            block_data = w3.eth.get_block(block)
            timestamp = datetime.utcfromtimestamp(block_data['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
            transfers.append({
                'tx_hash': event['transactionHash'].hex(),
                'from': event['args']['from'],
                'to': event['args']['to'],
                'value_usdc': value,
                'block_number': block,
                'timestamp': timestamp
            })
            log_message(f"Fetched transfer: {event['transactionHash'].hex()} - {value} USDC.e from {event['args']['from']} to {event['args']['to']}")
    except Exception as e:
        log_message(f"Error fetching transfers via Web3.py: {str(e)}")

    return transfers

# Main function
def main():
    start_time = time.time()
    log_message("Starting USDC transfer scan...")

    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Get block range
    w3 = get_web3()
    end_block = w3.eth.block_number
    log_message(f"Current block number: {end_block}")
    start_block = get_last_block()
    log_message(f"Scanning blocks {start_block} to {end_block}")

    # Fetch USDC price
    usdc_price = get_usdc_price()
    log_message(f"USDC price: ${usdc_price}")

    # Fetch transfers
    transfers = []
    for block in range(start_block, end_block + 1, BATCH_SIZE):
        batch_end = min(block + BATCH_SIZE - 1, end_block)
        batch_transfers = fetch_usdc_transfers(block, batch_end)
        transfers.extend(batch_transfers)
        time.sleep(0.5)  # Increased delay to avoid overwhelming the RPC node

    # Filter transfers ≥ $5,000
    filtered_transfers = []
    for transfer in transfers:
        value_usd = transfer['value_usdc'] * usdc_price
        if value_usd >= TRANSFER_THRESHOLD_USD:
            transfer['value_usd'] = value_usd
            transfer['token_symbol'] = 'USDC.e'
            filtered_transfers.append(transfer)
        else:
            log_message(f"Transfer {transfer['tx_hash']} filtered out: ${value_usd:.2f} < $5,000 threshold")

    # Save to CSV
    if filtered_transfers:
        df = pd.DataFrame(filtered_transfers)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        temp_csv = DATA_DIR / f"usdc_bridge_transfers_{timestamp}.csv.tmp"
        final_csv = DATA_DIR / f"usdc_bridge_transfers_{timestamp}.csv"
        df.to_csv(temp_csv, index=False)
        temp_csv.rename(final_csv)
        log_message(f"Saved {len(filtered_transfers)} transfers to {final_csv}")
    else:
        log_message("No transfers ≥ $5,000 found. No CSV generated.")

    # Update last block
    save_last_block(end_block)

    runtime = time.time() - start_time
    log_message(f"Scan completed in {runtime:.2f} seconds.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log_message(f"Error in main: {str(e)}")
        raise

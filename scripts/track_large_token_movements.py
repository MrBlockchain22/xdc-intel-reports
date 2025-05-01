import os
import time
import logging
from web3 import Web3
from web3.middleware import geth_poa_middleware
import requests
from datetime import datetime, timedelta
import csv
from ratelimit import limits, sleep_and_retry
from dotenv import load_dotenv

# Load environment variables from ~/xdc-intel/.env
load_dotenv(dotenv_path=os.path.join(os.path.expanduser("~"), "xdc-intel", ".env"))

# Configure logging to ~/xdc-intel/scan.log
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(asctime)s %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.expanduser("~"), "xdc-intel", "scan.log")),
        logging.StreamHandler()
    ]
)

# Constants
CMC_API_URL = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
CMC_API_KEY = os.getenv("CMC_API_KEY")
XDC_RPC_URLS = os.getenv("XDC_RPC_URLS", "https://rpc.ankr.com/xdc,https://rpc.xinfin.network,https://rpc.xdcrpc.com").split(",")
MIN_USD_VALUE = 5000
RPC_RATE_LIMIT = 5
CMC_RATE_LIMIT = 30
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

# Validate API keys
if not CMC_API_KEY:
    logging.error("CMC_API_KEY not found in .env")
    exit(1)
if not XDC_RPC_URLS:
    logging.error("XDC_RPC_URLS not found in .env")
    exit(1)

# Initialize Web3 with failover, returning a list of working Web3 instances
def init_web3():
    web3_instances = []
    for rpc_url in XDC_RPC_URLS:
        try:
            w3 = Web3(Web3.HTTPProvider(rpc_url.strip()))
            w3.middleware_onion.inject(geth_poa_middleware, layer=0)
            if w3.is_connected():
                logging.info(f"Connected to RPC: {rpc_url}")
                web3_instances.append(w3)
            else:
                logging.warning(f"Failed to connect to RPC: {rpc_url}")
        except Exception as e:
            logging.warning(f"Error connecting to RPC {rpc_url}: {str(e)}")
    if not web3_instances:
        logging.error("All RPCs failed")
        exit(1)
    return web3_instances

# Execute a function with RPC failover
def with_rpc_failover(web3_instances, func, *args, retries=3, delay=2):
    for attempt in range(retries):
        for w3 in web3_instances:
            try:
                return func(w3, *args)
            except Exception as e:
                logging.warning(f"RPC attempt {attempt+1}/{retries} failed: {str(e)}")
                time.sleep(delay)
        time.sleep(delay)
    logging.error(f"Failed to execute {func.__name__} after {retries} attempts")
    return None

# Rate-limited function for RPC block fetching
@sleep_and_retry
@limits(calls=RPC_RATE_LIMIT, period=1)
def get_block_transactions(w3, block_number):
    return w3.eth.get_block(block_number, full_transactions=True)

# Rate-limited function for RPC log fetching
@sleep_and_retry
@limits(calls=RPC_RATE_LIMIT, period=1)
def get_logs(w3, filter_params):
    return w3.eth.get_logs(filter_params)

# Rate-limited function for CoinMarketCap API
@sleep_and_retry
@limits(calls=CMC_RATE_LIMIT, period=60)
def get_token_price(symbol):
    if symbol == "UNKNOWN":
        return 0
    headers = {"X-CMC_PRO_API_KEY": CMC_API_KEY, "Accept": "application/json"}
    params = {"symbol": symbol, "convert": "USD"}
    try:
        response = requests.get(CMC_API_URL, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        price = data["data"][symbol]["quote"]["USD"]["price"]
        logging.info(f"{symbol} price: ${price}")
        return price
    except Exception as e:
        logging.error(f"Failed to fetch {symbol} price: {str(e)}")
        return 0

def process_transactions():
    web3_instances = init_web3()
    # Use the first Web3 instance for utility functions like from_wei
    w3 = web3_instances[0]

    current_block = with_rpc_failover(web3_instances, lambda w3: w3.eth.block_number)
    if current_block is None:
        logging.error("Cannot proceed without current block number")
        return

    blocks_per_hour = 1800
    start_block = current_block - blocks_per_hour
    logging.info(f"Scanning blocks {start_block} to {current_block}...")

    xdc_price = get_token_price("XDC")
    if not xdc_price:
        logging.error("Cannot proceed without XDC price")
        return

    large_transactions = []
    for block_number in range(start_block, current_block + 1):
        block = with_rpc_failover(web3_instances, get_block_transactions, block_number)
        if not block or "transactions" not in block:
            logging.warning(f"Skipping block {block_number}: no data")
            continue

        logging.info(f"Fetched block {block_number} with {len(block['transactions'])} transactions")

        # Process native XDC transactions
        for tx in block["transactions"]:
            if tx.get("value", 0) > 0:
                value_xdc = w3.from_wei(tx["value"], "ether")
                value_usd = float(value_xdc) * xdc_price
                if value_usd >= MIN_USD_VALUE:
                    tx_data = {
                        "tx_hash": tx["hash"].hex(),
                        "from": tx["from"],
                        "to": tx["to"],
                        "value_xdc": float(value_xdc),
                        "value_usd": value_usd,
                        "token_symbol": "XDC",
                        "block_number": block_number,
                        "timestamp": datetime.utcfromtimestamp(block["timestamp"])
                    }
                    large_transactions.append(tx_data)
                    logging.info(f"Found large XDC tx: {tx['hash'].hex()} - ${value_usd:.2f}")

        # Process ERC-20 token transfers
        filter_params = {
            "fromBlock": block_number,
            "toBlock": block_number,
            "topics": [TRANSFER_TOPIC]
        }
        logs = with_rpc_failover(web3_instances, get_logs, filter_params)
        if logs is None:
            logging.warning(f"Skipping ERC-20 logs for block {block_number}: failed to fetch")
            continue

        for log in logs:
            token_address = log["address"]
            if len(log["topics"]) != 3:
                continue
            try:
                # Convert HexBytes to hex string, removing '0x' prefix
                data_hex = log["data"].hex()[2:] if isinstance(log["data"], bytes) else log["data"][2:]
                # Validate hex string
                if not data_hex or not all(c in '0123456789abcdefABCDEF' for c in data_hex):
                    logging.warning(f"Invalid ERC-20 log data in block {block_number}: {data_hex}")
                    continue
                value = int(data_hex, 16) / 10**18  # Assume 18 decimals
                token_symbol = "UNKNOWN"  # Placeholder
                token_price = get_token_price(token_symbol)
                value_usd = value * token_price
                if value_usd >= MIN_USD_VALUE:
                    from_address = w3.to_checksum_address(f"0x{log['topics'][1][-40:]}")
                    to_address = w3.to_checksum_address(f"0x{log['topics'][2][-40:]}")
                    tx_data = {
                        "tx_hash": log["transactionHash"].hex(),
                        "from": from_address,
                        "to": to_address,
                        "value_xdc": value,
                        "value_usd": value_usd,
                        "token_symbol": token_symbol,
                        "block_number": block_number,
                        "timestamp": datetime.utcfromtimestamp(block["timestamp"])
                    }
                    large_transactions.append(tx_data)
                    logging.info(f"Found large ERC-20 tx: {tx_data['tx_hash']} - ${value_usd:.2f}")
            except Exception as e:
                logging.warning(f"Failed to process ERC-20 log in block {block_number} for token {token_address}: {str(e)}")
                continue

    # Save results to ~/xdc-intel-reports/data/large_transfers_<timestamp>.csv
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(os.path.expanduser("~"), "xdc-intel-reports", "data")
    output_path = os.path.join(output_dir, f"large_transfers_{timestamp}.csv")
    os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "tx_hash", "from", "to", "value_xdc", "value_usd", "token_symbol",
            "block_number", "timestamp"
        ])
        writer.writeheader()
        writer.writerows(large_transactions)
    logging.info(f"Saved {len(large_transactions)} transactions to {output_path}")

if __name__ == "__main__":
    process_transactions()

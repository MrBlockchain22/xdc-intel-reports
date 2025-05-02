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

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.expanduser("~"), "xdc-intel", ".env"))

# Configure logging to ~/xdc-intel/large_transfers.log
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(asctime)s %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.expanduser("~"), "xdc-intel", "large_transfers.log")),
        logging.StreamHandler()
    ]
)

# Constants
CMC_API_URL = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
CMC_API_KEY = os.getenv("CMC_API_KEY")
XDC_RPC_URLS = os.getenv("XDC_RPC_URLS", "https://rpc.ankr.com/xdc,https://rpc.xinfin.network,https://rpc.xdcrpc.com").split(",")
MIN_USD_VALUE = 5000  # Match post_to_x.py threshold
RPC_RATE_LIMIT = 3  # Lowered to be safer
CMC_RATE_LIMIT = 30
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
LAST_BLOCK_FILE = os.path.join(os.path.expanduser("~"), "xdc-intel", "last_block.txt")
BLOCKS_PER_HOUR = 1800  # XDC block time is ~2 seconds, so ~1800 blocks per hour
BATCH_SIZE = 50  # Process 50 blocks at a time to avoid RPC overload

# ERC-20 ABI for symbol and decimals
ERC20_ABI = [
    {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"}
]

# Validate API keys
if not CMC_API_KEY:
    logging.error("CMC_API_KEY not found in .env")
    exit(1)
if not XDC_RPC_URLS:
    logging.error("XDC_RPC_URLS not found in .env")
    exit(1)

# Initialize Web3 with failover
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

# Rate-limited RPC calls
@sleep_and_retry
@limits(calls=RPC_RATE_LIMIT, period=1)
def get_block_transactions(w3, block_number):
    return w3.eth.get_block(block_number, full_transactions=True)

@sleep_and_retry
@limits(calls=RPC_RATE_LIMIT, period=1)
def get_logs(w3, filter_params):
    return w3.eth.get_logs(filter_params)

@sleep_and_retry
@limits(calls=RPC_RATE_LIMIT, period=1)
def call_contract(w3, contract, function_name):
    return getattr(contract.functions, function_name)().call()

# Rate-limited function for CoinMarketCap API
@sleep_and_retry
@limits(calls=CMC_RATE_LIMIT, period=60)
def get_token_price(symbol, cached_prices):
    if symbol in cached_prices:
        return cached_prices[symbol]
    headers = {"X-CMC_PRO_API_KEY": CMC_API_KEY, "Accept": "application/json"}
    params = {"symbol": symbol, "convert": "USD"}
    try:
        response = requests.get(CMC_API_URL, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        price = data["data"][symbol]["quote"]["USD"]["price"]
        cached_prices[symbol] = price
        logging.info(f"{symbol} price: ${price}")
        return price
    except Exception as e:
        logging.error(f"Failed to fetch {symbol} price: {str(e)}")
        return cached_prices.get(symbol, 0)

# Get last processed block from file
def get_last_block():
    try:
        with open(LAST_BLOCK_FILE, "r") as f:
            return int(f.read().strip())
    except FileNotFoundError:
        logging.warning(f"{LAST_BLOCK_FILE} not found, starting from current block minus {BLOCKS_PER_HOUR}")
        return None  # We'll calculate the starting block dynamically
    except Exception as e:
        logging.error(f"Error reading last block: {e}")
        return None

# Save last processed block to file
def save_last_block(block_number):
    try:
        with open(LAST_BLOCK_FILE, "w") as f:
            f.write(str(block_number))
    except Exception as e:
        logging.error(f"Error saving last block: {e}")

def process_transactions():
    web3_instances = init_web3()
    w3 = web3_instances[0]

    # Get current block
    current_block = with_rpc_failover(web3_instances, lambda w3: w3.eth.block_number)
    if current_block is None:
        logging.error("Cannot proceed without current block number")
        return

    # Get last processed block
    last_processed_block = get_last_block()

    # Calculate the block range for the last hour
    if last_processed_block is None:
        # If no last block, start from (current_block - BLOCKS_PER_HOUR)
        start_block = max(current_block - BLOCKS_PER_HOUR, 0)
    else:
        # Start from the last processed block
        start_block = last_processed_block + 1

    # End at the current block
    end_block = current_block

    if start_block >= end_block:
        logging.info("No new blocks to process")
        return

    # Adjust start_block to cover approximately the last hour if needed
    if end_block - start_block > BLOCKS_PER_HOUR:
        start_block = end_block - BLOCKS_PER_HOUR

    logging.info(f"Scanning blocks {start_block} to {end_block}...")

    # Cache for token prices
    cached_prices = {}
    xdc_price = get_token_price("XDC", cached_prices)
    if xdc_price == 0:
        logging.error("Cannot proceed without XDC price")
        return
    cached_prices["XDC"] = xdc_price

    large_transactions = []
    # Process blocks in batches to avoid RPC overload
    current_start = start_block
    while current_start <= end_block:
        batch_end = min(current_start + BATCH_SIZE - 1, end_block)
        logging.info(f"Processing batch: blocks {current_start} to {batch_end}...")
        
        for block_number in range(current_start, batch_end + 1):
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
                        tx_hash = tx["hash"].hex()
                        tx_data = {
                            "tx_hash": tx_hash,
                            "from": tx["from"],
                            "to": tx["to"],
                            "value_xdc": float(value_xdc),
                            "value_usd": value_usd,
                            "token_symbol": "XDC",
                            "block_number": block_number,
                            "timestamp": datetime.utcfromtimestamp(block["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
                        }
                        large_transactions.append(tx_data)
                        logging.info(f"Found large XDC tx: {tx_hash} - ${value_usd:.2f}")

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
                    # Get token details
                    contract = w3.eth.contract(address=token_address, abi=ERC20_ABI)
                    token_symbol = with_rpc_failover(web3_instances, call_contract, contract, "symbol")
                    if not token_symbol:
                        token_symbol = "UNKNOWN"
                    decimals = with_rpc_failover(web3_instances, call_contract, contract, "decimals")
                    if not decimals:
                        decimals = 18  # Fallback to 18 decimals

                    # Process transfer
                    data_hex = log["data"].hex()[2:] if isinstance(log["data"], bytes) else log["data"][2:]
                    if not data_hex or not all(c in '0123456789abcdefABCDEF' for c in data_hex):
                        logging.warning(f"Invalid ERC-20 log data in block {block_number}: {data_hex}")
                        continue
                    value = int(data_hex, 16) / (10 ** decimals)
                    token_price = get_token_price(token_symbol, cached_prices)
                    value_usd = value * token_price
                    if value_usd >= MIN_USD_VALUE:
                        from_address = w3.to_checksum_address(f"0x{log['topics'][1][-40:]}")
                        to_address = w3.to_checksum_address(f"0x{log['topics'][2][-40:]}")
                        tx_hash = log["transactionHash"].hex()
                        tx_data = {
                            "tx_hash": tx_hash,
                            "from": from_address,
                            "to": to_address,
                            "value_xdc": value,
                            "value_usd": value_usd,
                            "token_symbol": token_symbol,
                            "block_number": block_number,
                            "timestamp": datetime.utcfromtimestamp(block["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
                        }
                        large_transactions.append(tx_data)
                        logging.info(f"Found large ERC-20 tx: {tx_data['tx_hash']} - ${value_usd:.2f}")
                except Exception as e:
                    logging.warning(f"Failed to process ERC-20 log in block {block_number} for token {token_address}: {str(e)}")
                    continue

        # Update the current start for the next batch
        current_start = batch_end + 1

    # Save results to CSV
    if large_transactions:
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

    # Update last processed block
    save_last_block(end_block)

if __name__ == "__main__":
    process_transactions()

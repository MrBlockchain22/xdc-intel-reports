from web3 import Web3
from web3.middleware import geth_poa_middleware
import pandas as pd
import json
import os

# Connect to an XDC RPC endpoint
w3 = Web3(Web3.HTTPProvider('https://erpc.xdcrpc.com'))

# Inject PoA Middleware
w3.middleware_onion.inject(geth_poa_middleware, layer=0)

# Load known malicious contracts
with open('malicious_contracts.json', 'r') as f:
    malicious_contracts = {entry['address'].lower(): entry for entry in json.load(f)}

# Load critical infrastructure contracts
with open('critical_infrastructure.json', 'r') as f:
    critical_contracts = {entry['address'].lower(): entry for entry in json.load(f)}

# Configuration
BLOCK_LOOKBACK = 2000  # Scan the last 2000 blocks

def scan_blocks():
    latest_block = w3.eth.block_number
    results = []
    critical_results = []

    for block_num in range(latest_block - BLOCK_LOOKBACK, latest_block):
        block = w3.eth.get_block(block_num, full_transactions=True)
        
        for tx in block.transactions:
            if tx.to:
                to_address = tx.to.lower()

                # Blacklist check
                if to_address in malicious_contracts:
                    results.append({
                        'block': block_num,
                        'hash': tx.hash.hex(),
                        'to': tx.to,
                        'from': tx['from'],
                        'value': w3.from_wei(tx.value, 'ether')
                    })

                # Critical infra monitoring
                if to_address in critical_contracts or tx['from'].lower() in critical_contracts:
                    contract_info = critical_contracts.get(to_address) or critical_contracts.get(tx['from'].lower())
                    if contract_info:
                        threshold = contract_info['threshold_usd']

                        # Convert value to USD assuming 1 XDC ≈ 1 USD (adjust logic later if needed)
                        value_usd = float(w3.from_wei(tx.value, 'ether')) * 1  # 1 XDC ~ $1 (for simplicity)

                        if value_usd >= threshold:
                            critical_results.append({
                                'block': block_num,
                                'hash': tx.hash.hex(),
                                'to': tx.to,
                                'from': tx['from'],
                                'value_usd': value_usd,
                                'critical_target': contract_info['name']
                            })

    return results, critical_results

# Run the scan
txs, criticals = scan_blocks()

# Save malicious interactions
if not os.path.exists('data'):
    os.makedirs('data')
malicious_output = f"data/bridge_scam_hits_{w3.eth.block_number}.csv"
pd.DataFrame(txs).to_csv(malicious_output, index=False)

# Save critical infra movements
critical_output = f"data/critical_movements_{w3.eth.block_number}.csv"
pd.DataFrame(criticals).to_csv(critical_output, index=False)

print(f"Found {len(txs)} suspicious interactions. Report saved to {malicious_output}")
print(f"Found {len(criticals)} critical movements. Report saved to {critical_output}")


import json
import os
import logging
from web3 import AsyncWeb3
from web3.middleware import ExtraDataToPOAMiddleware

logger = logging.getLogger(__name__)

# OKX X Layer Testnet
RPC_URL = "https://testrpc.xlayer.tech"
CONTRACT_ADDRESS = "0xbbAd97DabBa50807F38F9cF3812F2E7B1305b7E6"

# Hardhat Account #0 private key (ONLY FOR LOCAL DEMO)
PRIVATE_KEY = os.getenv("PRIVATE_KEY", "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80")

class RWAWeb3Client:
    def __init__(self):
        self.w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(RPC_URL))
        # Handle POA chains just in case
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        
        self.account = self.w3.eth.account.from_key(PRIVATE_KEY)
        
        # Load ABI
        abi_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "RWAToken.json")
        try:
            with open(abi_path, 'r') as f:
                data = json.load(f)
                self.abi = data.get("abi", [])
        except Exception as e:
            logger.error(f"Failed to load ABI: {e}")
            self.abi = []
            
        self.contract = self.w3.eth.contract(address=CONTRACT_ADDRESS, abi=self.abi)

    async def pause_trading(self, target_address: str = None) -> str:
        """Sends a transaction to pause trading on the RWA contract. Returns the tx_hash."""
        try:
            target = self.contract if not target_address else self.w3.eth.contract(address=target_address, abi=self.abi)
            nonce = await self.w3.eth.get_transaction_count(self.account.address)
            tx = await target.functions.pauseTrading().build_transaction({
                'from': self.account.address,
                'nonce': nonce,
                'gas': 2000000,
                'gasPrice': await self.w3.eth.gas_price
            })
            signed_tx = self.w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
            tx_hash = await self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            return self.w3.to_hex(tx_hash)
        except Exception as e:
            logger.error(f"Failed to pause trading: {e}")
            return f"Error: {e}"

    async def unpause_trading(self) -> str:
        """Sends a transaction to unpause trading on the RWA contract."""
        try:
            nonce = await self.w3.eth.get_transaction_count(self.account.address)
            tx = await self.contract.functions.unpauseTrading().build_transaction({
                'from': self.account.address,
                'nonce': nonce,
                'gas': 2000000,
                'gasPrice': await self.w3.eth.gas_price
            })
            signed_tx = self.w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
            tx_hash = await self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            return self.w3.to_hex(tx_hash)
        except Exception as e:
            logger.error(f"Failed to unpause trading: {e}")
            return f"Error: {e}"

    async def set_yield_rate(self, new_rate: int) -> str:
        """Sends a transaction to set the yield rate on the RWA contract. Returns the tx_hash."""
        try:
            nonce = await self.w3.eth.get_transaction_count(self.account.address)
            tx = await self.contract.functions.setYieldRate(new_rate).build_transaction({
                'from': self.account.address,
                'nonce': nonce,
                'gas': 2000000,
                'gasPrice': await self.w3.eth.gas_price
            })
            signed_tx = self.w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
            tx_hash = await self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            return self.w3.to_hex(tx_hash)
        except Exception as e:
            logger.error(f"Failed to set yield rate: {e}")
            return f"Error: {e}"
            
    async def get_insurance_balance(self) -> float:
        """Returns the insurance pool balance in OKB/ETH."""
        try:
            balance_wei = await self.contract.functions.insurancePool().call()
            return float(self.w3.from_wei(balance_wei, 'ether'))
        except Exception as e:
            logger.error(f"Failed to get insurance pool balance: {e}")
            return 0.0

web3_client = RWAWeb3Client()

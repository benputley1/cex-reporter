"""
Sui Blockchain Token Monitor

Monitors the ALKIMI token contract on Sui for all DEX trades.
Uses the Sui GraphQL API to query coin objects and their transactions
to identify swaps from Cetus, Bluefin, Turbos, Aftermath, and other DEXs.
"""

import os
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass
import httpx

from src.exchanges.base import Trade, TradeSide, ExchangeInterface, ExchangeConnectionError
from src.utils import get_logger

logger = get_logger(__name__)


# Sui GraphQL endpoint
GRAPHQL_URL = "https://sui-mainnet.mystenlabs.com/graphql"

# Known DEX package addresses on Sui mainnet (for exchange identification)
DEX_PACKAGES = {
    "0x1eabed72c53feb73c694be620a9da9dc841af501d0bf5c69e5d9a8c2d2df7c64": "cetus",
    "0xa17fef5d722a9f08a4b15ed4a6a40c8ccc9b21ad5ab44ef2b01ca5c6fa0f2d37": "bluefin",
    "0x91bfbc386a41afcfd9b2533058d7e915a1d3829089cc268ff4333d54d6339ca1": "turbos",
    "0xefe8b36d5b2e43728cc323298626b83177803521d195cfb11e15b910e892fddf": "aftermath",
}

# Token decimals
TOKEN_DECIMALS = {
    "alkimi": 9,
    "sui": 9,
    "usdc": 6,
    "usdt": 6,
}

# GeckoTerminal API for pool data
GECKOTERMINAL_API = "https://api.geckoterminal.com/api/v2"


@dataclass
class PoolInfo:
    """Liquidity pool data"""
    pool_id: str
    dex: str
    name: str
    token_a: str
    token_b: str
    tvl_usd: float
    volume_24h: float
    price: float
    fee_tier: str
    price_change_24h: float


@dataclass
class HolderInfo:
    """Token holder data"""
    address: str
    balance: float
    percentage: float
    rank: int


@dataclass
class WalletBalance:
    """Balance data for a monitored wallet"""
    address: str
    name: str
    alkimi_balance: float
    sui_balance: float
    usdc_balance: float
    timestamp: datetime


@dataclass
class TreasurySnapshot:
    """Snapshot of total treasury value"""
    timestamp: datetime
    total_alkimi: float
    alkimi_price: float
    total_value_usd: float
    wallets: List[WalletBalance]


class SuiTokenMonitor(ExchangeInterface):
    """
    Monitor ALKIMI token contract on Sui for all DEX trades.

    Uses the Sui GraphQL API to:
    1. Query ALKIMI coin objects
    2. Get their previousTransactionBlock (last transaction that modified them)
    3. Analyze balanceChanges to identify swaps (ALKIMI + SUI/USDC paired changes)
    """

    # GraphQL query to get ALKIMI coin objects with their last transaction
    COINS_QUERY = """
    query GetAlkimiCoins($coinType: String!, $cursor: String) {
      coins(type: $coinType, first: 50, after: $cursor) {
        pageInfo {
          hasNextPage
          endCursor
        }
        nodes {
          address
          previousTransactionBlock {
            digest
          }
        }
      }
    }
    """

    # GraphQL query to get transaction details including balance changes
    TRANSACTION_QUERY = """
    query GetTransaction($digest: String!) {
      transactionBlock(digest: $digest) {
        digest
        sender {
          address
        }
        effects {
          timestamp
          balanceChanges {
            nodes {
              coinType {
                repr
              }
              amount
            }
          }
        }
      }
    }
    """

    def __init__(
        self,
        config: Dict[str, Any] = None,
        account_name: str = "DEX",
        mock_mode: bool = False
    ):
        """
        Initialize Sui token monitor.

        Args:
            config: Configuration dict with keys:
                - token_contract: ALKIMI token contract address on Sui
                - rpc_url: Sui RPC endpoint URL (for balance queries)
                - wallets: List of wallet dicts with 'address' and 'name' keys
            account_name: Account identifier
            mock_mode: If True, generate mock data instead of real queries
        """
        super().__init__(
            exchange_name="sui_dex",
            config=config or {},
            mock_mode=mock_mode,
            account_name=account_name
        )

        config = config or {}

        # Load from config or environment
        self.token_contract = config.get('token_contract') or os.getenv('ALKIMI_TOKEN_CONTRACT', '')
        self.rpc_url = config.get('rpc_url') or os.getenv('SUI_RPC_URL', 'https://fullnode.mainnet.sui.io')
        self.graphql_url = GRAPHQL_URL

        # Parse wallet addresses from config or environment
        if config.get('wallets'):
            self.wallet_addresses = config['wallets']
        else:
            self.wallet_addresses = self._parse_wallets_from_env()

        self._client: Optional[httpx.AsyncClient] = None

        token_display = self.token_contract[:20] + "..." if self.token_contract else "not configured"
        logger.info(
            f"SuiTokenMonitor initialized: token={token_display}, "
            f"wallets={len(self.wallet_addresses)}, graphql={self.graphql_url}"
        )

    def _parse_wallets_from_env(self) -> List[Dict[str, str]]:
        """Parse SUI_WALLET_* environment variables"""
        wallets = []
        for key, value in os.environ.items():
            if key.startswith('SUI_WALLET_') and value:
                name = key.replace('SUI_WALLET_', '')
                wallets.append({'address': value, 'name': name})
        return wallets

    async def initialize(self) -> bool:
        """Initialize HTTP client for GraphQL and RPC calls"""
        if self.mock_mode:
            logger.info("SuiTokenMonitor running in mock mode")
            self._initialized = True
            return True

        self._client = httpx.AsyncClient(
            timeout=30.0,
            headers={"Content-Type": "application/json"}
        )

        # Test GraphQL connection
        try:
            result = await self._graphql_query(
                "query { chainIdentifier }",
                {}
            )
            chain_id = result.get('chainIdentifier', 'unknown')
            logger.info(f"Connected to Sui GraphQL API, chain: {chain_id}")
            self._initialized = True
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Sui GraphQL: {e}")
            raise ExchangeConnectionError(f"Sui GraphQL connection failed: {e}")

    async def _graphql_query(self, query: str, variables: Dict[str, Any]) -> Any:
        """Execute a GraphQL query against the Sui API"""
        if not self._client:
            raise ExchangeConnectionError("Client not initialized")

        payload = {
            "query": query,
            "variables": variables
        }

        response = await self._client.post(self.graphql_url, json=payload)
        response.raise_for_status()

        data = response.json()
        if "errors" in data:
            raise ExchangeConnectionError(f"GraphQL error: {data['errors']}")

        return data.get("data", {})

    async def _rpc_call(self, method: str, params: List[Any]) -> Any:
        """Make an RPC call to Sui node (for balance queries)"""
        if not self._client:
            raise ExchangeConnectionError("Client not initialized")

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params
        }

        response = await self._client.post(self.rpc_url, json=payload)
        response.raise_for_status()

        data = response.json()
        if "error" in data:
            raise ExchangeConnectionError(f"RPC error: {data['error']}")

        return data.get("result")

    async def get_balances(self) -> Dict[str, float]:
        """
        Get ALKIMI balances across all monitored wallets.

        Returns:
            Dictionary with total ALKIMI balance and per-wallet breakdown
        """
        if self.mock_mode:
            return self._generate_mock_balances()

        balances = {}
        total_alkimi = 0.0

        for wallet in self.wallet_addresses:
            try:
                wallet_balance = await self._get_wallet_balance(wallet['address'])
                balances[f"ALKIMI_{wallet['name']}"] = wallet_balance
                total_alkimi += wallet_balance
            except Exception as e:
                logger.error(f"Error fetching balance for {wallet['name']}: {e}")
                balances[f"ALKIMI_{wallet['name']}"] = 0.0

        balances['ALKIMI'] = total_alkimi
        return balances

    async def _get_wallet_balance(self, address: str) -> float:
        """Get ALKIMI token balance for a specific wallet"""
        if not self.token_contract:
            logger.warning("No token contract configured")
            return 0.0

        try:
            result = await self._rpc_call(
                "suix_getBalance",
                [address, self.token_contract]
            )

            if result and 'totalBalance' in result:
                return float(result['totalBalance']) / 1e9
            return 0.0
        except Exception as e:
            logger.error(f"Error getting balance for {address}: {e}")
            return 0.0

    async def get_trades(self, since: datetime) -> List[Trade]:
        """
        Fetch all ALKIMI trades from any DEX since the specified timestamp.

        Uses GraphQL to:
        1. Query ALKIMI coin objects
        2. Get unique transaction digests from previousTransactionBlock
        3. Fetch each transaction's balanceChanges
        4. Identify swaps where ALKIMI is paired with SUI/USDC/USDT

        Args:
            since: Fetch trades from this datetime onwards

        Returns:
            List of Trade objects representing DEX swaps
        """
        if self.mock_mode:
            return self._generate_mock_dex_trades(since)

        if not self.token_contract:
            logger.warning("No token contract configured, cannot fetch trades")
            return []

        trades = []
        since_ms = int(since.timestamp() * 1000)

        try:
            # Step 1: Get unique transaction digests from ALKIMI coin objects
            tx_digests = await self._get_alkimi_transaction_digests()
            logger.info(f"Found {len(tx_digests)} unique ALKIMI transactions to analyze")

            # Step 2: Fetch transaction details and parse swaps
            for digest in tx_digests:
                try:
                    trade = await self._get_trade_from_transaction(digest, since_ms)
                    if trade:
                        trades.append(trade)
                except Exception as e:
                    logger.debug(f"Error processing transaction {digest[:16]}...: {e}")

        except Exception as e:
            logger.error(f"Error fetching DEX trades: {e}")

        # Sort by timestamp (newest first)
        trades.sort(key=lambda t: t.timestamp, reverse=True)

        logger.info(f"Found {len(trades)} ALKIMI DEX trades since {since}")
        return trades

    async def _get_alkimi_transaction_digests(self, max_coins: int = 200) -> Set[str]:
        """
        Query ALKIMI coin objects and collect unique transaction digests.

        Each coin object tracks its last modification via previousTransactionBlock.
        """
        tx_digests: Set[str] = set()
        cursor = None
        coins_processed = 0

        while coins_processed < max_coins:
            try:
                result = await self._graphql_query(
                    self.COINS_QUERY,
                    {"coinType": self.token_contract, "cursor": cursor}
                )

                coins_data = result.get('coins', {})
                nodes = coins_data.get('nodes', [])

                if not nodes:
                    break

                for node in nodes:
                    prev_tx = node.get('previousTransactionBlock')
                    if prev_tx and prev_tx.get('digest'):
                        tx_digests.add(prev_tx['digest'])

                coins_processed += len(nodes)

                # Check pagination
                page_info = coins_data.get('pageInfo', {})
                if not page_info.get('hasNextPage'):
                    break
                cursor = page_info.get('endCursor')

            except Exception as e:
                logger.error(f"Error querying coin objects: {e}")
                break

        return tx_digests

    async def _get_trade_from_transaction(
        self,
        digest: str,
        since_ms: int
    ) -> Optional[Trade]:
        """
        Fetch transaction details and parse as a trade if it's a swap.

        A swap is identified by paired balance changes:
        - ALKIMI amount change (positive = buy, negative = sell)
        - SUI/USDC/USDT amount change (opposite sign)
        """
        try:
            result = await self._graphql_query(
                self.TRANSACTION_QUERY,
                {"digest": digest}
            )

            tx_block = result.get('transactionBlock')
            if not tx_block:
                return None

            effects = tx_block.get('effects', {})
            timestamp_str = effects.get('timestamp')

            if not timestamp_str:
                return None

            # Parse timestamp (ISO format from GraphQL)
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            timestamp_ms = int(timestamp.timestamp() * 1000)

            # Skip if before 'since'
            if timestamp_ms < since_ms:
                return None

            # Get balance changes
            balance_changes = effects.get('balanceChanges', {}).get('nodes', [])
            if not balance_changes:
                return None

            # Parse swap from balance changes
            return self._parse_swap_from_balance_changes(
                balance_changes,
                digest,
                timestamp
            )

        except Exception as e:
            logger.debug(f"Error fetching transaction {digest[:16]}...: {e}")
            return None

    def _parse_swap_from_balance_changes(
        self,
        balance_changes: List[Dict],
        tx_digest: str,
        timestamp: datetime
    ) -> Optional[Trade]:
        """
        Parse balance changes to identify an ALKIMI swap.

        A swap is detected when we have:
        - ALKIMI balance change (+ or -)
        - Quote token balance change (SUI/USDC/USDT) with opposite sign

        Returns Trade object if swap detected, None otherwise.
        """
        alkimi_change: Optional[int] = None
        quote_change: Optional[tuple] = None  # (symbol, amount, decimals)

        for bc in balance_changes:
            coin_type = bc.get('coinType', {}).get('repr', '')
            amount = int(bc.get('amount', 0))

            coin_type_lower = coin_type.lower()

            if 'alkimi' in coin_type_lower:
                alkimi_change = amount
            elif '::sui::SUI' in coin_type:
                quote_change = ('SUI', amount, TOKEN_DECIMALS['sui'])
            elif 'usdc' in coin_type_lower:
                quote_change = ('USDC', amount, TOKEN_DECIMALS['usdc'])
            elif 'usdt' in coin_type_lower:
                quote_change = ('USDT', amount, TOKEN_DECIMALS['usdt'])

        # Must have both ALKIMI and a quote token change
        if alkimi_change is None or quote_change is None:
            return None

        # Amounts should have opposite signs for a swap
        if (alkimi_change > 0 and quote_change[1] > 0) or \
           (alkimi_change < 0 and quote_change[1] < 0):
            return None

        # Determine trade side
        side = TradeSide.BUY if alkimi_change > 0 else TradeSide.SELL

        # Calculate amounts with proper decimals
        alkimi_amount = abs(alkimi_change) / (10 ** TOKEN_DECIMALS['alkimi'])
        quote_amount = abs(quote_change[1]) / (10 ** quote_change[2])

        # Calculate price in quote token per ALKIMI
        price = quote_amount / alkimi_amount if alkimi_amount > 0 else 0

        # Identify DEX from transaction (simplified - could analyze transaction inputs)
        exchange = "sui_dex"

        trade = Trade(
            timestamp=timestamp.replace(tzinfo=None),  # Remove timezone for consistency
            symbol='ALKIMI',
            side=side,
            amount=alkimi_amount,
            price=price,
            fee=0.0,  # DEX fees are included in swap amounts
            fee_currency=quote_change[0],
            trade_id=f"sui_{tx_digest[:16]}",
            exchange=exchange
        )

        logger.debug(
            f"Parsed swap: {side.value} {alkimi_amount:.2f} ALKIMI @ "
            f"{price:.8f} {quote_change[0]}"
        )

        return trade

    async def get_deposits(self, since: datetime) -> List:
        """DEX doesn't have deposits in the traditional sense"""
        return []

    async def get_withdrawals(self, since: datetime) -> List:
        """DEX doesn't have withdrawals in the traditional sense"""
        return []

    async def get_prices(self, symbols: List[str]) -> Dict[str, float]:
        """
        Get current prices from DEX pools.

        For now, returns placeholder - real implementation would
        query pool reserves.
        """
        if self.mock_mode:
            return self._generate_mock_prices(symbols)

        # TODO: Query actual DEX pool prices via GraphQL
        return {'ALKIMI': 0.027, 'SUI': 3.50, 'USDC': 1.0}

    async def get_treasury_value(self) -> TreasurySnapshot:
        """
        Calculate total treasury value across all monitored wallets.

        Returns:
            TreasurySnapshot with balances and total value
        """
        if self.mock_mode:
            return TreasurySnapshot(
                timestamp=datetime.now(),
                total_alkimi=1000000.0,
                alkimi_price=0.027,
                total_value_usd=27000.0,
                wallets=[]
            )

        wallet_balances = []
        total_alkimi = 0.0

        for wallet in self.wallet_addresses:
            balance = await self._get_wallet_balance(wallet['address'])
            wallet_balances.append(WalletBalance(
                address=wallet['address'],
                name=wallet['name'],
                alkimi_balance=balance,
                sui_balance=0.0,  # TODO: fetch SUI balance
                usdc_balance=0.0,  # TODO: fetch USDC balance
                timestamp=datetime.now()
            ))
            total_alkimi += balance

        prices = await self.get_prices(['ALKIMI'])
        alkimi_price = prices.get('ALKIMI', 0.027)

        return TreasurySnapshot(
            timestamp=datetime.now(),
            total_alkimi=total_alkimi,
            alkimi_price=alkimi_price,
            total_value_usd=total_alkimi * alkimi_price,
            wallets=wallet_balances
        )

    # =========================================================================
    # ON-CHAIN ANALYTICS: Pools, Holders, Wallet Tracking
    # =========================================================================

    async def get_alkimi_pools(self) -> List[PoolInfo]:
        """
        Get all ALKIMI liquidity pools across DEXs via GeckoTerminal API.

        Returns pool data including TVL, 24h volume, price, and DEX.
        """
        if self.mock_mode:
            return self._generate_mock_pools()

        if not self._client or not self.token_contract:
            logger.warning("Client/token not configured, cannot fetch pools")
            return []

        pools = []
        try:
            # Use token-based endpoint instead of search (search doesn't find ALKIMI)
            response = await self._client.get(
                f"{GECKOTERMINAL_API}/networks/sui-network/tokens/{self.token_contract}/pools"
            )

            if response.status_code != 200:
                logger.error(f"GeckoTerminal API error: {response.status_code}")
                return []

            data = response.json()

            for pool_data in data.get("data", []):
                attrs = pool_data.get("attributes", {})
                rel = pool_data.get("relationships", {})

                # Get DEX name
                dex_data = rel.get("dex", {}).get("data", {})
                dex_id = dex_data.get("id", "unknown")

                # Parse pool info
                pool = PoolInfo(
                    pool_id=attrs.get("address", ""),
                    dex=dex_id,
                    name=attrs.get("name", ""),
                    token_a="ALKIMI",
                    token_b="SUI",
                    tvl_usd=float(attrs.get("reserve_in_usd", 0) or 0),
                    volume_24h=float(attrs.get("volume_usd", {}).get("h24", 0) or 0),
                    price=float(attrs.get("base_token_price_usd", 0) or 0),
                    fee_tier=self._extract_fee_tier(attrs.get("name", "")),
                    price_change_24h=float(attrs.get("price_change_percentage", {}).get("h24", 0) or 0)
                )
                pools.append(pool)

            logger.info(f"Found {len(pools)} ALKIMI liquidity pools")

        except Exception as e:
            logger.error(f"Error fetching ALKIMI pools: {e}")

        return pools

    def _extract_fee_tier(self, pool_name: str) -> str:
        """Extract fee tier from pool name (e.g., 'ALKIMI / SUI 0.3%' -> '0.3%')"""
        import re
        match = re.search(r'(\d+\.?\d*%)', pool_name)
        return match.group(1) if match else "N/A"

    async def get_top_holders(self, limit: int = 10, max_pages: int = 20) -> List[HolderInfo]:
        """
        Get top ALKIMI token holders by balance.

        Aggregates coin objects by owner address via GraphQL.

        Args:
            limit: Number of top holders to return
            max_pages: Maximum pages to query (50 coins per page)

        Returns:
            List of HolderInfo sorted by balance descending
        """
        if self.mock_mode:
            return self._generate_mock_holders(limit)

        if not self._client or not self.token_contract:
            logger.warning("Client/token not configured, cannot fetch holders")
            return []

        # GraphQL query to get coin objects with owner
        holders_query = """
        query GetAlkimiCoins($coinType: String!, $cursor: String) {
          coins(type: $coinType, first: 50, after: $cursor) {
            pageInfo {
              hasNextPage
              endCursor
            }
            nodes {
              coinBalance
              owner {
                ... on AddressOwner {
                  owner {
                    address
                  }
                }
              }
            }
          }
        }
        """

        holders: Dict[str, float] = {}
        cursor = None
        pages_queried = 0

        try:
            while pages_queried < max_pages:
                result = await self._graphql_query(
                    holders_query,
                    {"coinType": self.token_contract, "cursor": cursor}
                )

                coins_data = result.get("coins", {})
                nodes = coins_data.get("nodes", [])

                if not nodes:
                    break

                for node in nodes:
                    balance = int(node.get("coinBalance", 0)) / 1e9
                    owner_data = node.get("owner", {})

                    if isinstance(owner_data, dict):
                        owner_addr = owner_data.get("owner", {}).get("address", "")
                    else:
                        owner_addr = ""

                    if owner_addr:
                        holders[owner_addr] = holders.get(owner_addr, 0) + balance

                pages_queried += 1

                page_info = coins_data.get("pageInfo", {})
                if not page_info.get("hasNextPage"):
                    break
                cursor = page_info.get("endCursor")

            # Calculate total and sort
            total_supply = sum(holders.values())
            sorted_holders = sorted(holders.items(), key=lambda x: x[1], reverse=True)

            result = []
            for rank, (addr, balance) in enumerate(sorted_holders[:limit], 1):
                pct = (balance / total_supply * 100) if total_supply > 0 else 0
                result.append(HolderInfo(
                    address=addr,
                    balance=balance,
                    percentage=pct,
                    rank=rank
                ))

            logger.info(f"Found {len(holders)} unique ALKIMI holders, returning top {limit}")
            return result

        except Exception as e:
            logger.error(f"Error fetching top holders: {e}")
            return []

    async def get_wallet_activity(
        self,
        address: str,
        since: datetime
    ) -> Dict[str, Any]:
        """
        Get ALKIMI trading activity for a specific wallet address.

        Args:
            address: Sui wallet address to track
            since: Only include activity after this timestamp

        Returns:
            Dict with trades_count, volume, net_change, last_trade
        """
        if self.mock_mode:
            return self._generate_mock_wallet_activity(address)

        if not self._client:
            return {"error": "Client not initialized"}

        wallet_tx_query = """
        query GetWalletTransactions($address: SuiAddress!) {
          address(address: $address) {
            transactionBlocks(first: 50) {
              nodes {
                digest
                effects {
                  timestamp
                  balanceChanges {
                    nodes {
                      coinType {
                        repr
                      }
                      amount
                    }
                  }
                }
              }
            }
          }
        }
        """

        try:
            result = await self._graphql_query(
                wallet_tx_query,
                {"address": address}
            )

            tx_nodes = result.get("address", {}).get("transactionBlocks", {}).get("nodes", [])

            trades_count = 0
            total_volume = 0.0
            net_change = 0.0
            last_trade_time = None
            since_ms = int(since.timestamp() * 1000)

            for tx in tx_nodes:
                effects = tx.get("effects", {})
                timestamp_str = effects.get("timestamp")

                if not timestamp_str:
                    continue

                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                timestamp_ms = int(timestamp.timestamp() * 1000)

                if timestamp_ms < since_ms:
                    continue

                balance_changes = effects.get("balanceChanges", {}).get("nodes", [])

                for bc in balance_changes:
                    coin_type = bc.get("coinType", {}).get("repr", "")
                    if "alkimi" in coin_type.lower():
                        amount = int(bc.get("amount", 0)) / 1e9
                        net_change += amount
                        total_volume += abs(amount)
                        trades_count += 1

                        if last_trade_time is None or timestamp > last_trade_time:
                            last_trade_time = timestamp

            return {
                "address": address,
                "trades_count": trades_count,
                "volume": total_volume,
                "net_change": net_change,
                "last_trade": last_trade_time.isoformat() if last_trade_time else None
            }

        except Exception as e:
            logger.error(f"Error fetching wallet activity for {address[:16]}...: {e}")
            return {"error": str(e)}

    async def get_onchain_analytics(self) -> Dict[str, Any]:
        """
        Get comprehensive on-chain analytics for ALKIMI.

        Returns combined data for pools, holders, and watched wallets.
        """
        pools = await self.get_alkimi_pools()
        holders = await self.get_top_holders(limit=10)

        # Track watched wallets if configured
        watched_wallets = []
        since_24h = datetime.now() - timedelta(hours=24)

        for wallet in self.wallet_addresses:
            activity = await self.get_wallet_activity(wallet['address'], since_24h)
            activity['name'] = wallet['name']
            watched_wallets.append(activity)

        # Calculate totals
        total_tvl = sum(p.tvl_usd for p in pools)
        total_volume_24h = sum(p.volume_24h for p in pools)
        top_10_concentration = sum(h.percentage for h in holders[:10])

        return {
            "pools": pools,
            "total_tvl": total_tvl,
            "total_volume_24h": total_volume_24h,
            "holders": holders,
            "top_10_concentration": top_10_concentration,
            "watched_wallets": watched_wallets,
            "timestamp": datetime.now().isoformat()
        }

    def _generate_mock_pools(self) -> List[PoolInfo]:
        """Generate mock pool data for testing"""
        return [
            PoolInfo(
                pool_id="0x5cf7...", dex="cetus", name="ALKIMI/SUI 0.3%",
                token_a="ALKIMI", token_b="SUI", tvl_usd=37100.0,
                volume_24h=670.0, price=0.0187, fee_tier="0.3%", price_change_24h=-1.2
            ),
            PoolInfo(
                pool_id="0x7a1f...", dex="bluefin", name="ALKIMI/SUI 0.3%",
                token_a="ALKIMI", token_b="SUI", tvl_usd=28166.0,
                volume_24h=362.0, price=0.0187, fee_tier="0.3%", price_change_24h=-1.1
            ),
        ]

    def _generate_mock_holders(self, limit: int) -> List[HolderInfo]:
        """Generate mock holder data for testing"""
        return [
            HolderInfo(address="0xa515...ea26", balance=12500000.0, percentage=74.77, rank=1),
            HolderInfo(address="0xf8b7...d43f", balance=3112584.0, percentage=18.62, rank=2),
            HolderInfo(address="0xfd97...b099", balance=257016.0, percentage=1.54, rank=3),
        ][:limit]

    def _generate_mock_wallet_activity(self, address: str) -> Dict[str, Any]:
        """Generate mock wallet activity for testing"""
        return {
            "address": address,
            "trades_count": 5,
            "volume": 50000.0,
            "net_change": -12000.0,
            "last_trade": datetime.now().isoformat()
        }

    async def close(self) -> None:
        """Close HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info("SuiTokenMonitor closed")

    def _generate_mock_dex_trades(self, since: datetime) -> List[Trade]:
        """Generate mock DEX trade data for testing"""
        import random

        trades = []
        current_time = since
        dex_names = list(DEX_PACKAGES.values())

        for i in range(random.randint(5, 15)):
            current_time += timedelta(hours=random.uniform(1, 12))

            dex = random.choice(dex_names)
            side = random.choice([TradeSide.BUY, TradeSide.SELL])
            amount = round(random.uniform(1000, 50000), 2)
            price = round(random.uniform(0.025, 0.035), 4)

            trades.append(Trade(
                timestamp=current_time,
                symbol='ALKIMI',
                side=side,
                amount=amount,
                price=price,
                fee=round(amount * price * 0.003, 4),  # 0.3% DEX fee
                fee_currency='SUI',
                trade_id=f"{dex}_mock_{i}",
                exchange=dex
            ))

        return trades

    def _generate_mock_balances(self) -> Dict[str, float]:
        """Generate mock balance data for testing"""
        import random

        balances = {}
        total = 0.0

        for wallet in self.wallet_addresses or [{'name': 'TREASURY'}, {'name': 'MM1'}]:
            balance = round(random.uniform(100000, 500000), 2)
            balances[f"ALKIMI_{wallet['name']}"] = balance
            total += balance

        balances['ALKIMI'] = total
        return balances

    def _generate_mock_prices(self, symbols: List[str]) -> Dict[str, float]:
        """Generate mock price data for testing"""
        prices = {'ALKIMI': 0.027, 'SUI': 3.50, 'USDC': 1.0}
        return {s: prices.get(s, 0.0) for s in symbols}

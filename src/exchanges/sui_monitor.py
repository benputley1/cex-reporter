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
from src.utils.retry import retry_with_backoff

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

# Note: DEX swap event types are no longer used - we fetch trades from GeckoTerminal API
# which is more reliable than querying Sui events (DEX package addresses change frequently)

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

    async def _ensure_client(self) -> bool:
        """
        Ensure HTTP client is initialized (lazy initialization).

        This allows methods to work without requiring explicit initialize() call.

        Returns:
            True if client is ready
        """
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={"Content-Type": "application/json"}
            )
            logger.debug("HTTP client lazily initialized")
        return True

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
        await self._ensure_client()

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
        await self._ensure_client()

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

    @retry_with_backoff(max_retries=3, initial_delay=1.0)
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

    @retry_with_backoff(max_retries=3, initial_delay=2.0)
    async def get_trades(self, since: datetime) -> List[Trade]:
        """
        Fetch all ALKIMI trades from DEX pools via GeckoTerminal API.

        Uses GeckoTerminal's trades endpoint which is more reliable than
        querying Sui swap events directly (DEX package addresses change).

        Args:
            since: Fetch trades from this datetime onwards

        Returns:
            List of Trade objects representing DEX swaps
        """
        if self.mock_mode:
            return self._generate_mock_dex_trades(since)

        # Step 1: Get ALKIMI pools from GeckoTerminal
        pools = await self.get_alkimi_pools()
        if not pools:
            logger.warning("No ALKIMI pools found, cannot fetch trades")
            return []

        logger.info(f"Fetching trades from {len(pools)} ALKIMI pools")

        trades = []

        # Step 2: Fetch trades from each pool via GeckoTerminal
        for pool in pools:
            try:
                pool_trades = await self._fetch_pool_trades(pool.pool_id, pool.dex, since)
                trades.extend(pool_trades)
            except Exception as e:
                logger.debug(f"Error fetching trades for pool {pool.pool_id[:16]}...: {e}")

        # Sort by timestamp (newest first)
        trades.sort(key=lambda t: t.timestamp, reverse=True)

        logger.info(f"Found {len(trades)} ALKIMI DEX trades since {since}")
        return trades

    async def _fetch_pool_trades(
        self,
        pool_id: str,
        dex_name: str,
        since: datetime
    ) -> List[Trade]:
        """
        Fetch trades for a specific pool from GeckoTerminal API.

        Args:
            pool_id: Pool address on Sui
            dex_name: Name of the DEX (for trade metadata)
            since: Only return trades after this timestamp

        Returns:
            List of Trade objects
        """
        await self._ensure_client()

        trades = []
        try:
            response = await self._client.get(
                f"{GECKOTERMINAL_API}/networks/sui-network/pools/{pool_id}/trades"
            )

            if response.status_code != 200:
                return []

            data = response.json()

            for trade_data in data.get("data", []):
                attrs = trade_data.get("attributes", {})

                # Parse timestamp
                timestamp_str = attrs.get("block_timestamp", "")
                if not timestamp_str:
                    continue

                try:
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    # Convert to naive datetime for comparison
                    timestamp = timestamp.replace(tzinfo=None)
                except ValueError:
                    continue

                # Skip trades before 'since'
                if timestamp < since:
                    continue

                # Determine trade side and amount
                kind = attrs.get("kind", "").lower()
                if kind == "buy":
                    side = TradeSide.BUY
                    amount = float(attrs.get("to_token_amount", 0))
                elif kind == "sell":
                    side = TradeSide.SELL
                    amount = float(attrs.get("from_token_amount", 0))
                else:
                    continue

                # Get price (ALKIMI price in USD)
                if kind == "buy":
                    price = float(attrs.get("price_to_in_usd", 0))
                else:
                    price = float(attrs.get("price_from_in_usd", 0))

                # Create trade object
                trade = Trade(
                    timestamp=timestamp,
                    symbol='ALKIMI',
                    side=side,
                    amount=amount,
                    price=price,
                    fee=0.0,  # GeckoTerminal doesn't provide fee info
                    fee_currency='USD',
                    trade_id=f"sui_{attrs.get('tx_hash', '')[:16]}",
                    exchange=dex_name
                )
                trades.append(trade)

        except Exception as e:
            logger.debug(f"Error parsing trades for pool {pool_id[:16]}...: {e}")

        return trades

    async def get_deposits(self, since: datetime) -> List:
        """DEX doesn't have deposits in the traditional sense"""
        return []

    async def get_withdrawals(self, since: datetime) -> List:
        """DEX doesn't have withdrawals in the traditional sense"""
        return []

    @retry_with_backoff(max_retries=3, initial_delay=1.0)
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

    @retry_with_backoff(max_retries=3, initial_delay=1.0)
    async def get_alkimi_pools(self) -> List[PoolInfo]:
        """
        Get all ALKIMI liquidity pools across DEXs via GeckoTerminal API.

        Returns pool data including TVL, 24h volume, price, and DEX.
        """
        if self.mock_mode:
            return self._generate_mock_pools()

        if not self.token_contract:
            logger.warning("Token contract not configured, cannot fetch pools")
            return []

        await self._ensure_client()

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

    async def get_total_tvl(self) -> Dict[str, Any]:
        """
        Get total TVL across all ALKIMI pools with breakdown by DEX.

        Returns:
            Dict with total_tvl_usd, total_volume_24h, pool_count, and by_dex breakdown
        """
        pools = await self.get_alkimi_pools()

        if not pools:
            return {
                'total_tvl_usd': 0.0,
                'total_volume_24h': 0.0,
                'pool_count': 0,
                'by_dex': {}
            }

        # Calculate totals
        total_tvl = sum(p.tvl_usd for p in pools)
        total_volume = sum(p.volume_24h for p in pools)

        # Group by DEX
        dex_tvl: Dict[str, float] = {}
        for pool in pools:
            dex_name = pool.dex
            dex_tvl[dex_name] = dex_tvl.get(dex_name, 0) + pool.tvl_usd

        return {
            'total_tvl_usd': total_tvl,
            'total_volume_24h': total_volume,
            'pool_count': len(pools),
            'by_dex': dex_tvl
        }

    @retry_with_backoff(max_retries=3, initial_delay=1.0)
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

        if not self.token_contract:
            logger.warning("Token contract not configured, cannot fetch holders")
            return []

        await self._ensure_client()

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

        await self._ensure_client()

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

"""
Claude AI Analyst Module

AI-powered trading analysis using Claude API.
Provides pattern detection, arbitrage opportunities, whale alerts,
and natural language query capabilities for HFT traders.
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from src.utils import get_logger

logger = get_logger(__name__)


@dataclass
class ArbitrageOpportunity:
    """Represents a detected arbitrage opportunity"""
    venue_low: str
    venue_high: str
    price_low: float
    price_high: float
    spread_percent: float
    potential_profit_usd: float
    timestamp: datetime


@dataclass
class TradingInsight:
    """AI-generated trading insight"""
    insight_type: str  # 'pattern', 'arbitrage', 'whale', 'risk', 'recommendation'
    content: str
    confidence: float
    timestamp: datetime
    data_context: Optional[Dict] = None


class ClaudeAnalyst:
    """
    AI-powered trading analysis using Claude API.

    Queries trade data and provides actionable insights for HFT traders.
    Supports natural language queries via Slack bot integration.
    """

    def __init__(
        self,
        api_key: str = None,
        model: str = None,
        db_connection: Any = None
    ):
        """
        Initialize Claude Analyst.

        Args:
            api_key: Anthropic API key (defaults to env var)
            model: Claude model to use (defaults to env var)
            db_connection: Optional database connection for trade data
        """
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY', '')
        self.model = model or os.getenv('CLAUDE_MODEL', 'claude-sonnet-4-20250514')
        self.db = db_connection
        self._client = None
        self._initialized = False

        if not self.api_key:
            logger.warning("No Anthropic API key configured - AI analysis disabled")

        logger.info(f"ClaudeAnalyst initialized with model: {self.model}")

    async def initialize(self) -> bool:
        """Initialize the Anthropic client"""
        if not self.api_key:
            logger.warning("Cannot initialize ClaudeAnalyst - no API key")
            return False

        try:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self.api_key)
            self._initialized = True
            logger.info("ClaudeAnalyst initialized successfully")
            return True
        except ImportError:
            logger.error("anthropic package not installed")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize ClaudeAnalyst: {e}")
            return False

    async def analyze_trading_patterns(
        self,
        trades: List[Dict],
        timeframe: str = "24h"
    ) -> TradingInsight:
        """
        Analyze recent trading patterns across CEX + DEX venues.

        Args:
            trades: List of trade dictionaries
            timeframe: Time window for analysis

        Returns:
            TradingInsight with pattern analysis
        """
        if not self._initialized:
            return TradingInsight(
                insight_type='error',
                content='AI analysis not available - not initialized',
                confidence=0.0,
                timestamp=datetime.now()
            )

        # Build context from trade data
        context = self._build_trade_context(trades, timeframe)

        prompt = f"""Analyze this ALKIMI trading data and provide actionable insights:

{context}

Focus on:
1. Volume patterns across venues (CEX vs DEX)
2. Price discrepancies / arbitrage opportunities
3. Unusual activity or whale movements
4. Recommended actions for market making
5. Risk alerts

Be concise and actionable. Format your response as bullet points."""

        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )

            analysis = response.content[0].text

            return TradingInsight(
                insight_type='pattern',
                content=analysis,
                confidence=0.85,
                timestamp=datetime.now(),
                data_context={'timeframe': timeframe, 'trade_count': len(trades)}
            )

        except Exception as e:
            logger.error(f"Error in pattern analysis: {e}")
            return TradingInsight(
                insight_type='error',
                content=f'Analysis failed: {str(e)}',
                confidence=0.0,
                timestamp=datetime.now()
            )

    async def detect_arbitrage_opportunities(
        self,
        prices: Dict[str, float],
        min_spread_percent: float = 1.0
    ) -> List[ArbitrageOpportunity]:
        """
        Detect arbitrage opportunities between venues.

        Args:
            prices: Dictionary of venue -> price
            min_spread_percent: Minimum spread to flag as opportunity

        Returns:
            List of ArbitrageOpportunity objects
        """
        opportunities = []

        venues = list(prices.keys())
        for i, venue_low in enumerate(venues):
            for venue_high in venues[i+1:]:
                price_low = prices[venue_low]
                price_high = prices[venue_high]

                # Ensure we have the lower price first
                if price_low > price_high:
                    venue_low, venue_high = venue_high, venue_low
                    price_low, price_high = price_high, price_low

                spread = ((price_high - price_low) / price_low) * 100

                if spread >= min_spread_percent:
                    opportunities.append(ArbitrageOpportunity(
                        venue_low=venue_low,
                        venue_high=venue_high,
                        price_low=price_low,
                        price_high=price_high,
                        spread_percent=spread,
                        potential_profit_usd=0.0,  # Would need position size
                        timestamp=datetime.now()
                    ))

        return opportunities

    async def generate_daily_briefing(
        self,
        trades: List[Dict],
        balances: Dict[str, float],
        prices: Dict[str, float]
    ) -> str:
        """
        Generate morning briefing for HFT trader.

        Args:
            trades: Recent trades (last 24h)
            balances: Current balances by venue
            prices: Current prices by venue

        Returns:
            Formatted briefing string
        """
        if not self._initialized:
            return "Daily briefing unavailable - AI not initialized"

        # Calculate key metrics
        total_volume = sum(t.get('amount', 0) * t.get('price', 0) for t in trades)
        buy_volume = sum(
            t.get('amount', 0) * t.get('price', 0)
            for t in trades if t.get('side') == 'buy'
        )
        sell_volume = total_volume - buy_volume

        # Group by exchange
        by_exchange = {}
        for t in trades:
            ex = t.get('exchange', 'unknown')
            if ex not in by_exchange:
                by_exchange[ex] = {'count': 0, 'volume': 0}
            by_exchange[ex]['count'] += 1
            by_exchange[ex]['volume'] += t.get('amount', 0) * t.get('price', 0)

        context = f"""
Overnight Activity Summary (Last 24h):

Total Volume: ${total_volume:,.2f}
- Buy Volume: ${buy_volume:,.2f}
- Sell Volume: ${sell_volume:,.2f}

Activity by Exchange:
{chr(10).join(f"- {ex}: {data['count']} trades, ${data['volume']:,.2f}" for ex, data in by_exchange.items())}

Current Balances:
{chr(10).join(f"- {asset}: {amount:,.2f}" for asset, amount in balances.items())}

Current Prices:
{chr(10).join(f"- {venue}: ${price:.4f}" for venue, price in prices.items())}
"""

        prompt = f"""Based on this overnight trading data, generate a concise morning briefing for an HFT trader:

{context}

Include:
1. Key overnight activity summary (2-3 bullet points)
2. Notable price movements
3. Recommended focus areas for today
4. Any risk alerts

Keep it brief and actionable."""

        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Error generating briefing: {e}")
            return f"Briefing generation failed: {str(e)}"

    async def analyze_whale_activity(
        self,
        trades: List[Dict],
        threshold_usd: float = 10000
    ) -> List[TradingInsight]:
        """
        Detect and analyze large trades (whale activity).

        Args:
            trades: List of trade dictionaries
            threshold_usd: USD value threshold for whale trades

        Returns:
            List of insights about whale activity
        """
        whale_trades = []
        for t in trades:
            value = t.get('amount', 0) * t.get('price', 0)
            if value >= threshold_usd:
                whale_trades.append({
                    **t,
                    'value_usd': value
                })

        if not whale_trades:
            return []

        insights = []
        for wt in whale_trades:
            insights.append(TradingInsight(
                insight_type='whale',
                content=f"Large {wt.get('side', 'trade')}: {wt.get('amount'):,.0f} ALKIMI "
                       f"@ ${wt.get('price'):.4f} = ${wt['value_usd']:,.2f} on {wt.get('exchange', 'unknown')}",
                confidence=0.95,
                timestamp=datetime.fromisoformat(wt.get('timestamp', datetime.now().isoformat())),
                data_context=wt
            ))

        return insights

    async def answer_query(
        self,
        query: str,
        data_context: Dict
    ) -> str:
        """
        Answer a natural language query from the trader.

        Args:
            query: User's question in natural language
            data_context: Relevant data to inform the answer

        Returns:
            Natural language response
        """
        if not self._initialized:
            return "Sorry, AI analysis is not available. Please check the API configuration."

        # Format the data context
        context_str = self._format_data_context(data_context)

        prompt = f"""You are a trading analytics assistant for ALKIMI token trading operations.
Answer the following question based on the provided data context.
Be concise and specific. If the data doesn't contain information to answer the question, say so.

Data Context:
{context_str}

Question: {query}

Answer:"""

        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Error answering query: {e}")
            return f"Sorry, I couldn't process that query: {str(e)}"

    def _build_trade_context(self, trades: List[Dict], timeframe: str) -> str:
        """Build a text context from trade data for Claude"""
        if not trades:
            return "No trades in the specified timeframe."

        # Group by exchange
        by_exchange = {}
        for t in trades:
            ex = t.get('exchange', 'unknown')
            if ex not in by_exchange:
                by_exchange[ex] = {'trades': [], 'buy_vol': 0, 'sell_vol': 0}

            value = t.get('amount', 0) * t.get('price', 0)
            if t.get('side') == 'buy':
                by_exchange[ex]['buy_vol'] += value
            else:
                by_exchange[ex]['sell_vol'] += value
            by_exchange[ex]['trades'].append(t)

        context = f"Trading Activity ({timeframe}):\n\n"

        for exchange, data in by_exchange.items():
            context += f"{exchange.upper()}:\n"
            context += f"  - Trades: {len(data['trades'])}\n"
            context += f"  - Buy Volume: ${data['buy_vol']:,.2f}\n"
            context += f"  - Sell Volume: ${data['sell_vol']:,.2f}\n"
            context += f"  - Net Flow: ${data['buy_vol'] - data['sell_vol']:,.2f}\n\n"

        # Add price summary if available
        prices = {}
        for t in trades:
            ex = t.get('exchange', 'unknown')
            if ex not in prices:
                prices[ex] = []
            prices[ex].append(t.get('price', 0))

        if prices:
            context += "Average Prices by Exchange:\n"
            for ex, price_list in prices.items():
                avg = sum(price_list) / len(price_list) if price_list else 0
                context += f"  - {ex}: ${avg:.4f}\n"

        return context

    def _format_data_context(self, data: Dict) -> str:
        """Format data dictionary as readable context"""
        lines = []
        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"{key}:")
                for k, v in value.items():
                    if isinstance(v, float):
                        lines.append(f"  {k}: {v:,.4f}")
                    else:
                        lines.append(f"  {k}: {v}")
            elif isinstance(value, list):
                lines.append(f"{key}: {len(value)} items")
            elif isinstance(value, float):
                lines.append(f"{key}: {value:,.4f}")
            else:
                lines.append(f"{key}: {value}")
        return "\n".join(lines)

    async def close(self):
        """Cleanup resources"""
        self._client = None
        self._initialized = False
        logger.info("ClaudeAnalyst closed")

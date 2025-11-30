#!/usr/bin/env python3
"""
ALKIMI Slack Bot Entry Point

Launches the ALKIMI trading bot with LLM-powered natural language interface.

Features:
- Natural language queries ("What's our P&L this month?")
- SQL query execution
- Python code generation and execution
- Saved functions
- P&L calculations with OTC support
- Query history tracking
- Rich Slack formatting

Usage:
    python bot_main.py

Required environment variables:
    SLACK_BOT_TOKEN      - Bot User OAuth Token (xoxb-...)
    SLACK_APP_TOKEN      - App-Level Token for Socket Mode (xapp-...)
    SLACK_SIGNING_SECRET - Signing Secret from Slack App config
    ANTHROPIC_API_KEY    - Claude API Key for LLM features

Optional environment variables:
    DB_PATH             - Path to SQLite database (default: data/trade_cache.db)
    SNAPSHOTS_DIR       - Path to snapshots directory (default: data/snapshots)

Setup:
    1. Create a Slack app at https://api.slack.com/apps
    2. Enable Socket Mode and create an App-Level Token
    3. Add Bot Token Scopes: app_mentions:read, chat:write, commands, im:history, im:read
    4. Install app to workspace
    5. Set environment variables in .env file
    6. Run: python bot_main.py

Example .env file:
    SLACK_BOT_TOKEN=xoxb-your-bot-token
    SLACK_APP_TOKEN=xapp-your-app-token
    SLACK_SIGNING_SECRET=your-signing-secret
    ANTHROPIC_API_KEY=your-anthropic-key
"""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.bot.slack_bot import create_bot
from src.utils import get_logger

logger = get_logger(__name__)


def check_env_vars():
    """
    Check required environment variables are set.

    Raises:
        SystemExit: If required variables are missing
    """
    required = [
        "SLACK_BOT_TOKEN",
        "SLACK_APP_TOKEN",
        "SLACK_SIGNING_SECRET",
        "ANTHROPIC_API_KEY"
    ]

    missing = [var for var in required if not os.environ.get(var)]

    if missing:
        logger.error("=" * 60)
        logger.error("MISSING REQUIRED ENVIRONMENT VARIABLES")
        logger.error("=" * 60)
        for var in missing:
            logger.error(f"  - {var}")
        logger.error("")
        logger.error("Please set these variables in your .env file or environment.")
        logger.error("See bot_main.py docstring for setup instructions.")
        logger.error("=" * 60)
        sys.exit(1)


def check_data_directories():
    """
    Check that required data directories exist.

    Creates directories if they don't exist.
    """
    required_dirs = [
        "data",
        "data/snapshots",
        "data/functions"
    ]

    for dir_path in required_dirs:
        path = Path(dir_path)
        if not path.exists():
            logger.warning(f"Creating directory: {dir_path}")
            path.mkdir(parents=True, exist_ok=True)


def display_startup_banner():
    """Display startup banner with configuration info."""
    logger.info("=" * 60)
    logger.info("ALKIMI SLACK BOT")
    logger.info("=" * 60)
    logger.info("Configuration:")
    logger.info(f"  Database: {os.getenv('DB_PATH', 'data/trade_cache.db')}")
    logger.info(f"  Snapshots: {os.getenv('SNAPSHOTS_DIR', 'data/snapshots')}")
    logger.info(f"  Bot Token: {os.getenv('SLACK_BOT_TOKEN', '')[:20]}...")
    logger.info(f"  Anthropic API: {'Configured' if os.getenv('ANTHROPIC_API_KEY') else 'Missing'}")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Features enabled:")
    logger.info("  ✓ Natural language queries")
    logger.info("  ✓ SQL query execution")
    logger.info("  ✓ Python code generation")
    logger.info("  ✓ Saved functions")
    logger.info("  ✓ P&L calculations")
    logger.info("  ✓ Query history")
    logger.info("  ✓ OTC transaction management")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Starting bot with Socket Mode...")
    logger.info("Bot will be available in Slack once connected.")
    logger.info("Press Ctrl+C to stop.")
    logger.info("")


async def main():
    """Main entry point."""
    # Load environment variables from .env file
    load_dotenv()

    # Check configuration
    check_env_vars()
    check_data_directories()

    # Display startup info
    display_startup_banner()

    try:
        # Create and start bot
        bot = create_bot()
        await bot.start()

    except KeyboardInterrupt:
        logger.info("")
        logger.info("=" * 60)
        logger.info("Bot stopped by user (Ctrl+C)")
        logger.info("=" * 60)

    except Exception as e:
        logger.error("")
        logger.error("=" * 60)
        logger.error("FATAL ERROR")
        logger.error("=" * 60)
        logger.error(f"Error: {e}")
        logger.error("")
        logger.error("Stack trace:", exc_info=True)
        logger.error("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    # Run async main
    asyncio.run(main())

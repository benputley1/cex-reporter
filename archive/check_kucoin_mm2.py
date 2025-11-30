"""
Pull all activity for KuCoin MM2 account
"""
import asyncio
from datetime import datetime, timedelta
from src.exchanges.kucoin import KuCoinClient
from config.settings import settings

async def check_kucoin_mm2():
    """Check all activity on KuCoin MM2"""
    print("=" * 80)
    print("KuCoin MM2 Account Activity Report")
    print("=" * 80)

    # Get KuCoin MM2 config
    kucoin_accounts = settings.kucoin_accounts
    mm2_config = None

    for account in kucoin_accounts:
        if account['account_name'] == 'MM2':
            mm2_config = account
            break

    if not mm2_config:
        print("ERROR: KuCoin MM2 account not found in configuration")
        return

    # Initialize client
    client = KuCoinClient(config=mm2_config, mock_mode=False, account_name='MM2')

    try:
        await client.initialize()
        print("\n✓ Connected to KuCoin MM2\n")

        # 1. Current Balances
        print("=" * 80)
        print("CURRENT BALANCES")
        print("=" * 80)
        balances = await client.get_balances()

        for asset, balance in balances.items():
            if balance['total'] > 0:
                print(f"\n{asset}:")
                print(f"  Free:      {balance['free']:,.2f}")
                print(f"  Locked:    {balance['locked']:,.2f}")
                print(f"  Total:     {balance['total']:,.2f}")

        # 2. Trade History (last 90 days)
        print("\n" + "=" * 80)
        print("TRADE HISTORY (Last 90 Days)")
        print("=" * 80)

        since = datetime.now() - timedelta(days=90)
        trades = await client.get_trades(since=since)

        print(f"\nTotal trades: {len(trades)}")

        if trades:
            # Group by date
            trades_by_date = {}
            for trade in trades:
                date = trade.timestamp.date()
                if date not in trades_by_date:
                    trades_by_date[date] = []
                trades_by_date[date].append(trade)

            # Show summary by date (most recent first)
            for date in sorted(trades_by_date.keys(), reverse=True):
                day_trades = trades_by_date[date]
                buys = sum(1 for t in day_trades if t.side.value == 'buy')
                sells = sum(1 for t in day_trades if t.side.value == 'sell')
                total_volume = sum(t.amount * t.price for t in day_trades)
                total_fees = sum(t.fee for t in day_trades)

                print(f"\n{date}:")
                print(f"  Trades: {len(day_trades)} ({buys} buys, {sells} sells)")
                print(f"  Volume: ${total_volume:,.2f}")
                print(f"  Fees: ${total_fees:,.2f}")

            # Show last 10 trades
            print("\n" + "-" * 80)
            print("Last 10 Trades:")
            print("-" * 80)
            for trade in sorted(trades, key=lambda t: t.timestamp, reverse=True)[:10]:
                print(f"\n{trade.timestamp.strftime('%Y-%m-%d %H:%M:%S')} - {trade.side.value.upper()} {trade.symbol}")
                print(f"  Amount: {trade.amount:,.2f} @ ${trade.price:.6f}")
                print(f"  Value: ${trade.amount * trade.price:,.2f}")
                print(f"  Fee: ${trade.fee:.4f} {trade.fee_currency}")

        # 3. Deposits (last 90 days)
        print("\n" + "=" * 80)
        print("DEPOSITS (Last 90 Days)")
        print("=" * 80)

        deposits = await client.get_deposits(since=since)
        print(f"\nTotal deposits: {len(deposits)}")

        if deposits:
            for deposit in sorted(deposits, key=lambda d: d.timestamp, reverse=True):
                print(f"\n{deposit.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"  Asset: {deposit.symbol}")
                print(f"  Amount: {deposit.amount:,.2f}")
                print(f"  Status: {deposit.status}")
                if deposit.tx_id:
                    print(f"  TX ID: {deposit.tx_id}")
                if deposit.network:
                    print(f"  Network: {deposit.network}")

        # 4. Withdrawals (last 90 days)
        print("\n" + "=" * 80)
        print("WITHDRAWALS (Last 90 Days)")
        print("=" * 80)

        withdrawals = await client.get_withdrawals(since=since)
        print(f"\nTotal withdrawals: {len(withdrawals)}")

        if withdrawals:
            for withdrawal in sorted(withdrawals, key=lambda w: w.timestamp, reverse=True):
                print(f"\n{withdrawal.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"  Asset: {withdrawal.symbol}")
                print(f"  Amount: {withdrawal.amount:,.2f}")
                print(f"  Fee: {withdrawal.fee:,.4f}")
                print(f"  Status: {withdrawal.status}")
                if withdrawal.tx_id:
                    print(f"  TX ID: {withdrawal.tx_id}")
                if withdrawal.address:
                    print(f"  Address: {withdrawal.address}")
                if withdrawal.network:
                    print(f"  Network: {withdrawal.network}")

        print("\n" + "=" * 80)
        print("Report Complete")
        print("=" * 80)

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(check_kucoin_mm2())

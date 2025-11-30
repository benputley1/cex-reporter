"""
Test MEXC MM1 API credentials
"""
import asyncio
from src.exchanges.mexc import MEXCClient
from config.settings import settings

async def test_mexc_mm1():
    """Test MEXC MM1 connection and fetch balances"""

    print("=" * 80)
    print("TESTING MEXC MM1 API CREDENTIALS")
    print("=" * 80)

    # Get MM1 config
    mm1_config = None
    for account in settings.mexc_accounts:
        if account['account_name'] == 'MM1':
            mm1_config = account
            break

    if not mm1_config:
        print("ERROR: MM1 config not found")
        return False

    print(f"\nAPI Key: {mm1_config['apiKey'][:10]}...")
    print(f"Secret: {mm1_config['secret'][:10]}...")

    client = MEXCClient(
        config=mm1_config,
        mock_mode=False,
        account_name='MM1'
    )

    try:
        print("\nInitializing connection...")
        await client.initialize()
        print("✓ Connection successful!")

        print("\nFetching balances...")
        balances = await client.get_balances()

        print("\nBalances:")
        for asset, balance in balances.items():
            if balance['total'] > 0:
                print(f"  {asset}:")
                print(f"    Free:   {balance['free']:,.2f}")
                print(f"    Locked: {balance['locked']:,.2f}")
                print(f"    Total:  {balance['total']:,.2f}")

        await client.close()

        print("\n" + "=" * 80)
        print("✓ TEST PASSED - MEXC MM1 API credentials are working!")
        print("=" * 80)
        return True

    except Exception as e:
        print(f"\n✗ TEST FAILED: {str(e)}")
        print("=" * 80)
        try:
            await client.close()
        except:
            pass
        return False

if __name__ == "__main__":
    result = asyncio.run(test_mexc_mm1())
    exit(0 if result else 1)

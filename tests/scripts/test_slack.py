"""Quick test to verify Slack webhook is working"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

webhook_url = os.getenv('SLACK_WEBHOOK_URL')

if not webhook_url or webhook_url == 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL':
    print("❌ SLACK_WEBHOOK_URL not configured in .env file")
    print("Please update the SLACK_WEBHOOK_URL in your .env file")
    exit(1)

# Send a simple test message
payload = {
    "text": "✅ CEX Reporter Slack webhook test successful! Your reports will be posted here."
}

try:
    response = requests.post(webhook_url, json=payload)

    if response.status_code == 200:
        print("✅ Success! Check your Slack channel for the test message.")
    else:
        print(f"❌ Error: {response.status_code}")
        print(f"Response: {response.text}")
except Exception as e:
    print(f"❌ Failed to send message: {e}")

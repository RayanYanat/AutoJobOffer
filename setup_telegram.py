#!/usr/bin/env python3
"""
Helper to set up Telegram bot and get your chat_id.

Usage:
    1. Create a bot via @BotFather on Telegram
    2. Copy the token
    3. Run: python setup_telegram.py <YOUR_BOT_TOKEN>
    4. Send any message to your bot on Telegram
    5. Press Enter here to retrieve your chat_id
"""

import sys
import requests


def main():
    if len(sys.argv) < 2:
        print("Usage: python setup_telegram.py <BOT_TOKEN>")
        print()
        print("Steps:")
        print("  1. Open Telegram, search @BotFather")
        print("  2. Send /newbot")
        print("  3. Choose a name (ex: 'Job Alert Bot')")
        print("  4. Choose a username (ex: 'my_job_alert_bot')")
        print("  5. Copy the token and run this script with it")
        sys.exit(1)

    token = sys.argv[1]
    base_url = f"https://api.telegram.org/bot{token}"

    # Verify token
    print("Verifying bot token...")
    resp = requests.get(f"{base_url}/getMe", timeout=10)
    if resp.status_code != 200:
        print(f"❌ Invalid token. Error: {resp.text}")
        sys.exit(1)

    bot_info = resp.json()["result"]
    print(f"✅ Bot found: @{bot_info['username']} ({bot_info['first_name']})")
    print()
    print(f"Now open Telegram and send any message to @{bot_info['username']}")
    input("Press Enter after sending a message...")

    # Get chat_id
    resp = requests.get(f"{base_url}/getUpdates", timeout=10)
    data = resp.json()

    if not data.get("result"):
        print("❌ No messages found. Make sure you sent a message to the bot.")
        sys.exit(1)

    chat_id = data["result"][-1]["message"]["chat"]["id"]
    print()
    print(f"✅ Your chat_id: {chat_id}")
    print()
    print("Add these to your .env file:")
    print(f"  TELEGRAM_BOT_TOKEN={token}")
    print(f"  TELEGRAM_CHAT_ID={chat_id}")
    print()

    # Test message
    send = input("Send a test message? (y/n): ").strip().lower()
    if send == "y":
        resp = requests.post(
            f"{base_url}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": "✅ Bot configuré ! Les alertes emploi sont prêtes.",
                "parse_mode": "HTML",
            },
            timeout=10,
        )
        if resp.status_code == 200:
            print("✅ Test message sent! Check Telegram.")
        else:
            print(f"❌ Failed: {resp.text}")


if __name__ == "__main__":
    main()

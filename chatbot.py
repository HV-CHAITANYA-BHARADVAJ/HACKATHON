import time
import requests
from telegram import Bot

# --- USER CONFIGURATION ---

TELEGRAM_TOKEN = "7644983400:AAFgDmVICv6u2DQXxIA2pbQ58FhjC75Kx1s"
TELEGRAM_CHAT_ID = 2070881390  # Use your user ID, group/channel numeric ID, or username as a string

COINS = {
    'bitcoin': {'threshold_up': 45000, 'threshold_down': 40000},
    'ethereum': {'threshold_up': 3500, 'threshold_down': 3000},
    # add more coins as needed
}
CURRENCY = 'usd' \
''
CHECK_INTERVAL = 60  # seconds

# --- END USER CONFIGURATION ---

def get_prices(coin_ids, currency):
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        'ids': ','.join(coin_ids),
        'vs_currencies': currency
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

def send_telegram_message(bot, chat_id, message):
    bot.send_message(chat_id=2070881390, text="NEW ALERT!\n")

def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    last_above = {coin: False for coin in COINS}
    last_below = {coin: False for coin in COINS}

    while True:
        try:
            prices = get_prices(list(COINS.keys()), CURRENCY)
            for coin, thresholds in COINS.items():
                price = prices[coin][CURRENCY]
                # Check upward threshold
                if price >= thresholds['threshold_up'] and not last_above[coin]:
                    msg = f"🚀 {coin.title()} is above {thresholds['threshold_up']} {CURRENCY.upper()}! (Current: {price})"
                    send_telegram_message(bot, TELEGRAM_CHAT_ID, msg)
                    last_above[coin] = True
                    last_below[coin] = False
                # Check downward threshold
                elif price <= thresholds['threshold_down'] and not last_below[coin]:
                    msg = f"🔻 {coin.title()} is below {thresholds['threshold_down']} {CURRENCY.upper()}! (Current: {price})"
                    send_telegram_message(bot, TELEGRAM_CHAT_ID, msg)
                    last_below[coin] = True
                    last_above[coin] = False
                # Reset flags if price is between thresholds
                elif thresholds['threshold_down'] < price < thresholds['threshold_up']:
                    last_above[coin] = False
                    last_below[coin] = False
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
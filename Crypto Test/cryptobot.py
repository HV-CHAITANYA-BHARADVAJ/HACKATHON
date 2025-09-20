import os
import requests
from firebase_admin import firestore, initialize_app
from firebase_functions import https_fn, config

# --- Firebase Initialization ---
try:
    initialize_app()
except ValueError:
    pass
db = firestore.client()

# --- Telegram Bot Configuration ---
_telegram_config = config.get("telegram")
if _telegram_config and _telegram_config.get("bot_token"):
    TELEGRAM_BOT_TOKEN = _telegram_config["bot_token"]
else:
    print("Warning: 'telegram.bot_token' not found in Firebase Functions config. Bot will not function.")
    TELEGRAM_BOT_TOKEN = None

if not TELEGRAM_BOT_TOKEN:
    TELEGRAM_API_URL = "https://api.telegram.org/bot_TOKEN_NOT_SET"
else:
    TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# --- Helper Function to Send Telegram Messages ---
def send_telegram_message(chat_id: int, text: str):
    method = 'sendMessage'
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'}
    try:
        response = requests.post(f"{TELEGRAM_API_URL}/{method}", json=payload)
        response.raise_for_status()
        print(f"Message sent to chat_id {chat_id}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error sending message to {chat_id}: {e}")
        return False

# --- Firestore Transaction Helpers (for robust updates) ---
def _upsert_alert_to_firestore(transaction, user_doc_ref, chat_id, symbol, high, low):
    snapshot = user_doc_ref.get(transaction=transaction)
    current_alerts = snapshot.to_dict().get('alerts', []) if snapshot.exists else []

    new_alert_data = {
        'symbol': symbol,
        'high': high,
        'low': low,
        'last_notified_high': None,
        'last_notified_low': None
    }
    
    updated = False
    for i, alert in enumerate(current_alerts):
        if alert['symbol'] == symbol:
            # Update existing alert, preserving existing thresholds if not provided
            current_alerts[i]['high'] = high if high is not None else current_alerts[i].get('high')
            current_alerts[i]['low'] = low if low is not None else current_alerts[i].get('low')
            updated = True
            break
    
    if not updated:
        current_alerts.append(new_alert_data)

    transaction.set(user_doc_ref, {'chat_id': chat_id, 'alerts': current_alerts}, merge=True)

def _remove_alert_from_firestore(transaction, user_doc_ref, symbol_to_remove):
    snapshot = user_doc_ref.get(transaction=transaction)
    if snapshot.exists:
        current_alerts = snapshot.to_dict().get('alerts', [])
        updated_alerts = [alert for alert in current_alerts if alert['symbol'] != symbol_to_remove]
        transaction.update(user_doc_ref, {'alerts': updated_alerts})
    else:
        print(f"No document found for {user_doc_ref.id} to remove alert.")

# --- Main Cloud Function Entry Point ---
@https_fn.on_request()
def cryptoBotWebhook(request: https_fn.Request) -> https_fn.Response:
    if request.method != 'POST':
        return https_fn.Response('Method Not Allowed', status=405)

    try:
        update = request.get_json()
        print(f"Received Telegram update: {update}")

        message = update.get('message', {})
        chat_id = message.get('chat', {}).get('id')
        user_text = message.get('text', '').strip().lower()

        if not chat_id or not user_text:
            return https_fn.Response('No valid message or chat ID found', status=200)

        response_text = "I didn't quite catch that. Try /help for commands."

        if user_text == '/start':
            response_text = "Welcome to your personal Crypto Monitor Bot! I can help you track cryptocurrency prices and send alerts. Type /help to see what I can do."
        elif user_text == '/help':
            # Updated /help to include /upperlimit
            response_text = """
Available Commands:
/start - Get started with the bot.
/help - Show this help message.
/addalert <SYMBOL> <HIGH_PRICE> high <LOW_PRICE> low - Add a new price alert.
  Example: `/addalert BTC 70000 high 60000 low`
  You can omit high/low if you only want one threshold.
/upperlimit <SYMBOL> <PRICE> - Set only an upper price limit for a cryptocurrency.
  Example: `/upperlimit ETH 4500`
/lowerlimit <SYMBOL> <PRICE> - Set only a lower price limit for a cryptocurrency.
  Example: `/lowerlimit ETH 3000`
/listalerts - See all your active alerts.
/removealert <SYMBOL> - Remove an alert for a specific symbol.
"""
        elif user_text.startswith('/addalert'):
            parts = user_text.split()
            if len(parts) >= 3:
                try:
                    coin_symbol = parts[1].upper()
                    high_price = None
                    low_price = None

                    i = 2
                    while i < len(parts):
                        if parts[i] == 'high' and i + 1 < len(parts):
                            high_price = float(parts[i+1])
                            i += 2
                        elif parts[i] == 'low' and i + 1 < len(parts):
                            low_price = float(parts[i+1])
                            i += 2
                        else:
                            raise ValueError("Malformed alert command.")
                    
                    if high_price is None and low_price is None:
                        response_text = "Please specify at least one threshold (high or low)."
                    else:
                        user_doc_ref = db.collection('user_alerts').document(str(chat_id))
                        db.run_transaction(lambda transaction: _upsert_alert_to_firestore(transaction, user_doc_ref, chat_id, coin_symbol, high_price, low_price))
                        
                        response_text = f"Alert added for {coin_symbol}: High: {high_price if high_price else 'N/A'}, Low: {low_price if low_price else 'N/A'}."
                except (ValueError, IndexError):
                    response_text = "Invalid /addalert format. Use: /addalert BTC 70000 high 60000 low."
            else:
                response_text = "Invalid /addalert command. Missing symbol or price."
        
        # --- NEW COMMAND: /upperlimit ---
        elif user_text.startswith('/upperlimit'):
            parts = user_text.split()
            if len(parts) == 3: # e.g., /upperlimit BTC 75000
                try:
                    coin_symbol = parts[1].upper()
                    price = float(parts[2])
                    
                    user_doc_ref = db.collection('user_alerts').document(str(chat_id))
                    # Use the upsert helper to update or add the high threshold
                    db.run_transaction(lambda transaction: _upsert_alert_to_firestore(transaction, user_doc_ref, chat_id, coin_symbol, high=price, low=None))
                    
                    response_text = f"Upper limit for {coin_symbol} set to {price}. Use /listalerts to see all your alerts."
                except (ValueError, IndexError):
                    response_text = "Invalid /upperlimit format. Use: /upperlimit <SYMBOL> <PRICE> (e.g., /upperlimit ETH 4500)."
            else:
                response_text = "Invalid /upperlimit command. Please specify a symbol and a price (e.g., /upperlimit ETH 4500)."

        # --- NEW COMMAND: /lowerlimit (following the same pattern) ---
        elif user_text.startswith('/lowerlimit'):
            parts = user_text.split()
            if len(parts) == 3: # e.g., /lowerlimit BTC 60000
                try:
                    coin_symbol = parts[1].upper()
                    price = float(parts[2])
                    
                    user_doc_ref = db.collection('user_alerts').document(str(chat_id))
                    # Use the upsert helper to update or add the low threshold
                    db.run_transaction(lambda transaction: _upsert_alert_to_firestore(transaction, user_doc_ref, chat_id, coin_symbol, high=None, low=price))
                    
                    response_text = f"Lower limit for {coin_symbol} set to {price}. Use /listalerts to see all your alerts."
                except (ValueError, IndexError):
                    response_text = "Invalid /lowerlimit format. Use: /lowerlimit <SYMBOL> <PRICE> (e.g., /lowerlimit ETH 3000)."
            else:
                response_text = "Invalid /lowerlimit command. Please specify a symbol and a price (e.g., /lowerlimit ETH 3000)."


        elif user_text == '/listalerts':
            user_doc_ref = db.collection('user_alerts').document(str(chat_id))
            user_doc = user_doc_ref.get()

            if user_doc.exists and 'alerts' in user_doc.to_dict():
                alerts = user_doc.to_dict()['alerts']
                if alerts:
                    alert_list_str = "\n".join([
                        f"- {alert['symbol']}: High: {alert['high'] if alert['high'] else 'N/A'}, Low: {alert['low'] if alert['low'] else 'N/A'}"
                        for alert in alerts
                    ])
                    response_text = f"Your current alerts:\n{alert_list_str}"
                else:
                    response_text = "You have no active alerts. Use /addalert to add one!"
            else:
                response_text = "You have no active alerts. Use /addalert to add one!"

        elif user_text.startswith('/removealert'):
            parts = user_text.split()
            if len(parts) == 2:
                coin_symbol_to_remove = parts[1].upper()
                user_doc_ref = db.collection('user_alerts').document(str(chat_id))
                db.run_transaction(lambda transaction: _remove_alert_from_firestore(transaction, user_doc_ref, coin_symbol_to_remove))
                response_text = f"Alert for {coin_symbol_to_remove} removed."
            else:
                response_text = "Invalid /removealert format. Use: /removealert BTC"
            
        send_telegram_message(chat_id, response_text)
        return https_fn.Response('OK', status=200)

    except Exception as e:
        print(f"Error processing Telegram update: {e}")
        return https_fn.Response('Error processing request', status=500)
    
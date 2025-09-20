import tkinter as tk
from tkinter import ttk, messagebox
import threading
import requests
import time
import asyncio
from telegram import Bot

COINGECKO_API_URL = "https://api.coingecko.com/api/v3/simple/price"

# --- Your Telegram details ---
TELEGRAM_TOKEN = "7644983400:AAFgDmVICv6u2DQXxIA2pbQ58FhjC75Kx1s"
TELEGRAM_CHAT_ID = "2070881390"

class CryptoMonitor(threading.Thread):
    def __init__(self, coins, thresholds, currency, interval, on_alert):
        super().__init__()
        self.coins = coins
        self.thresholds = thresholds
        self.currency = currency
        self.interval = interval
        self.on_alert = on_alert
        self._stop_event = threading.Event()
        self.bot = Bot(token=TELEGRAM_TOKEN)
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, daemon=True).start()

    def get_prices(self, coin_ids, currency):
        params = {
            'ids': ','.join(coin_ids),
            'vs_currencies': currency
        }
        resp = requests.get(COINGECKO_API_URL, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()

    async def send_telegram_message_async(self, message):
        await self.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)

    def send_telegram_message(self, message):
        asyncio.run_coroutine_threadsafe(
            self.send_telegram_message_async(message),
            self.loop
        )

    def run(self):
        last_status = {coin: None for coin in self.coins}
        while not self._stop_event.is_set():
            try:
                prices = self.get_prices(self.coins, self.currency)
                for coin in self.coins:
                    price = prices.get(coin, {}).get(self.currency)
                    if price is None:
                        continue
                    up = float(self.thresholds[coin]['up'])
                    down = float(self.thresholds[coin]['down'])
                    if price >= up and last_status[coin] != 'up':
                        msg = f"🚀 {coin.title()} is above {up} {self.currency.upper()}! (Current: {price})"
                        self.send_telegram_message(msg)
                        self.on_alert(msg)
                        last_status[coin] = 'up'
                    elif price <= down and last_status[coin] != 'down':
                        msg = f"🔻 {coin.title()} is below {down} {self.currency.upper()}! (Current: {price})"
                        self.send_telegram_message(msg)
                        self.on_alert(msg)
                        last_status[coin] = 'down'
                    elif down < price < up:
                        last_status[coin] = None
                time.sleep(self.interval)
            except Exception as e:
                self.on_alert(f"Error: {e}")
                time.sleep(self.interval)

    def stop(self):
        self._stop_event.set()
        try:
            self.loop.call_soon_threadsafe(self.loop.stop)
        except Exception:
            pass

class CryptoAlertApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Crypto Price Alert")
        self.geometry("500x500") # Adjusted the window height
        self.resizable(False, False)

        # Coin selection and thresholds
        self.coin_vars = {}
        self.threshold_vars = {}
        self.available_coins = ["bitcoin", "ethereum", "dogecoin", "solana", "cardano", "ripple", "litecoin"]
        self.currency_var = tk.StringVar(value="usd")

        ttk.Label(self, text="Select Cryptos & Set Thresholds:", font=("Arial", 12, "bold")).pack(pady=10)
        self.coins_frame = ttk.Frame(self)
        self.coins_frame.pack(pady=5)

        for i, coin in enumerate(self.available_coins):
            coin_var = tk.IntVar()
            self.coin_vars[coin] = coin_var
            frame = ttk.Frame(self.coins_frame)
            frame.grid(row=i, column=0, sticky="w", pady=2)
            cb = ttk.Checkbutton(frame, text=coin.title(), variable=coin_var)
            cb.grid(row=0, column=0)
            up_var = tk.StringVar()
            down_var = tk.StringVar()
            self.threshold_vars[coin] = {'up': up_var, 'down': down_var}
            ttk.Label(frame, text="Up:").grid(row=0, column=1)
            ttk.Entry(frame, textvariable=up_var, width=8).grid(row=0, column=2)
            ttk.Label(frame, text="Down:").grid(row=0, column=3)
            ttk.Entry(frame, textvariable=down_var, width=8).grid(row=0, column=4)

        # Currency & interval
        options_frame = ttk.Frame(self)
        options_frame.pack(pady=10)
        ttk.Label(options_frame, text="Currency:").grid(row=0, column=0)
        ttk.Entry(options_frame, textvariable=self.currency_var, width=8).grid(row=0, column=1)
        ttk.Label(options_frame, text="Check every (sec):").grid(row=0, column=2)
        self.interval_var = tk.IntVar(value=60)
        ttk.Entry(options_frame, textvariable=self.interval_var, width=8).grid(row=0, column=3)

        # Start/stop and log output
        self.status_var = tk.StringVar(value="Status: Idle")
        ttk.Label(self, textvariable=self.status_var, foreground="blue").pack(pady=6)
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=5)
        self.start_btn = ttk.Button(btn_frame, text="Start Monitoring", command=self.start_monitoring)
        self.start_btn.grid(row=0, column=0, padx=5)
        self.stop_btn = ttk.Button(btn_frame, text="Stop", command=self.stop_monitoring, state="disabled")
        self.stop_btn.grid(row=0, column=1, padx=5)

        # Log
        ttk.Label(self, text="Alerts Log:").pack()
        self.log_text = tk.Text(self, height=10, width=60, state="disabled", bg="#f3f3f3")
        self.log_text.pack()

        self.monitor_thread = None

    def start_monitoring(self):
        coins = [coin for coin, var in self.coin_vars.items() if var.get()]
        if not coins:
            messagebox.showwarning("No Coins", "Please select at least one cryptocurrency.")
            return
        thresholds = {}
        for coin in coins:
            up = self.threshold_vars[coin]['up'].get()
            down = self.threshold_vars[coin]['down'].get()
            if not up or not down:
                messagebox.showwarning("Missing Threshold", f"Enter up/down thresholds for {coin.title()}.")
                return
            try:
                float(up)
                float(down)
            except ValueError:
                messagebox.showwarning("Invalid Threshold", f"Thresholds for {coin.title()} must be numbers.")
                return
            thresholds[coin] = {'up': up, 'down': down}
        interval = self.interval_var.get()
        if interval < 10:
            messagebox.showwarning("Interval", "Interval should be at least 10 seconds.")
            return
        self.monitor_thread = CryptoMonitor(
            coins, thresholds, self.currency_var.get().strip().lower(), interval,
            self.log_alert
        )
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        self.status_var.set("Status: Monitoring...")
        self.start_btn['state'] = "disabled"
        self.stop_btn['state'] = "normal"
        self.log_alert("Monitoring started.")

    def stop_monitoring(self):
        if self.monitor_thread:
            self.monitor_thread.stop()
            self.monitor_thread = None
        self.status_var.set("Status: Idle")
        self.start_btn['state'] = "normal"
        self.stop_btn['state'] = "disabled"
        self.log_alert("Monitoring stopped.")

    def log_alert(self, msg):
        self.log_text['state'] = "normal"
        self.log_text.insert("end", f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {msg}\n")
        self.log_text.see("end")
        self.log_text['state'] = "disabled"

    def on_closing(self):
        self.stop_monitoring()
        self.destroy()

if __name__ == "__main__":
    app = CryptoAlertApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
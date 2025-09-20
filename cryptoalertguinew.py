import tkinter as tk
from tkinter import ttk, messagebox
import threading
import requests
import time

COINGECKO_API_URL = "https://api.coingecko.com/api/v3/simple/price"

# -------------------- Hardcoded Telegram Bot --------------------
TELEGRAM_TOKEN = "7644983400:AAFgDmVICv6u2DQXxIA2pbQ58FhjC75Kx1s"
TELEGRAM_CHAT_ID = "2070881390"  # Note: Chat ID is now a string for the API URL

# -------------------- Monitoring Thread --------------------
class CryptoMonitor(threading.Thread):
    def __init__(self, coins, thresholds, currency, interval, on_alert, on_price_update=None):
        super().__init__()
        self.coins = coins
        self.thresholds = thresholds
        self.currency = currency
        self.interval = interval
        self.on_alert = on_alert
        self.on_price_update = on_price_update
        self._stop_event = threading.Event()

    def run(self):
        last_status = {coin: None for coin in self.coins}
        while not self._stop_event.is_set():
            try:
                prices = self.get_prices(self.coins, self.currency)
                if self.on_price_update:
                    self.on_price_update(prices)
                for coin in self.coins:
                    price = prices.get(coin, {}).get(self.currency)
                    if price is None:
                        continue
                    up = float(self.thresholds[coin]['up'])
                    down = float(self.thresholds[coin]['down'])
                    if price >= up and last_status[coin] != 'up':
                        msg = f"🚀 {coin.title()} is above {up} {self.currency.upper()}! (Current: {price})"
                        self._send_telegram_message(msg)
                        self.on_alert(msg, "up")
                        last_status[coin] = 'up'
                    elif price <= down and last_status[coin] != 'down':
                        msg = f"🔻 {coin.title()} is below {down} {self.currency.upper()}! (Current: {price})"
                        self._send_telegram_message(msg)
                        self.on_alert(msg, "down")
                        last_status[coin] = 'down'
                    elif down < price < up:
                        last_status[coin] = None
                time.sleep(self.interval)
            except Exception as e:
                self.on_alert(f"Error: {e}", "error")
                time.sleep(self.interval)

    def get_prices(self, coin_ids, currency):
        params = {'ids': ','.join(coin_ids), 'vs_currencies': currency}
        resp = requests.get(COINGECKO_API_URL, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def _send_telegram_message(self, message):
        """Sends a message directly to Telegram via a requests post."""
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message
        }
        try:
            requests.post(url, json=payload, timeout=5)
        except requests.exceptions.RequestException as e:
            self.on_alert(f"Failed to send Telegram message: {e}", "error")

    def stop(self):
        self._stop_event.set()


# -------------------- UI Application --------------------
class CryptoAlertApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("💰 CryptoVault Alert")
        self.geometry("650x650")
        self.resizable(False, False)
        self.monitor_thread = None

        self.coin_vars = {}
        self.threshold_vars = {}
        self.price_vars = {}
        self.available_coins = ["bitcoin", "ethereum", "dogecoin", "solana", "cardano", "ripple", "litecoin"]
        self.currency_var = tk.StringVar(value="usd")
        self.interval_var = tk.IntVar(value=60)

        self.create_tabs()

    def create_tabs(self):
        notebook = ttk.Notebook(self)
        notebook.pack(expand=True, fill="both", pady=10)

        # ---- Coins Tab ----
        tab_coins = ttk.Frame(notebook)
        notebook.add(tab_coins, text="Coins & Thresholds")
        ttk.Label(tab_coins, text="Select Coins & Set Thresholds", font=("Arial", 12, "bold")).pack(pady=10)
        coins_frame = ttk.Frame(tab_coins)
        coins_frame.pack(pady=5)

        for i, coin in enumerate(self.available_coins):
            coin_var = tk.IntVar()
            self.coin_vars[coin] = coin_var
            frame = ttk.Frame(coins_frame)
            frame.grid(row=i, column=0, sticky="w", pady=2, padx=5)
            ttk.Checkbutton(frame, text=coin.title(), variable=coin_var).grid(row=0, column=0)

            up_var = tk.StringVar()
            down_var = tk.StringVar()
            price_var = tk.StringVar(value="-")
            self.threshold_vars[coin] = {'up': up_var, 'down': down_var}
            self.price_vars[coin] = price_var

            ttk.Label(frame, text="Up:").grid(row=0, column=1, padx=(10,2))
            ttk.Spinbox(frame, from_=0, to=1000000, textvariable=up_var, width=10).grid(row=0, column=2)
            ttk.Label(frame, text="Down:").grid(row=0, column=3, padx=(10,2))
            ttk.Spinbox(frame, from_=0, to=1000000, textvariable=down_var, width=10).grid(row=0, column=4)
            ttk.Label(frame, textvariable=price_var, width=12, foreground="blue").grid(row=0, column=5, padx=(10,2))

        # Currency & Interval
        options_frame = ttk.Frame(tab_coins)
        options_frame.pack(pady=15)
        ttk.Label(options_frame, text="Currency:").grid(row=0, column=0, padx=5)
        ttk.Combobox(options_frame, textvariable=self.currency_var, values=["usd", "inr", "eur"], width=8, state="readonly").grid(row=0, column=1, padx=5)
        ttk.Label(options_frame, text="Check every (sec):").grid(row=0, column=2, padx=5)
        ttk.Spinbox(options_frame, from_=10, to=3600, textvariable=self.interval_var, width=8).grid(row=0, column=3, padx=5)

        # ---- Monitoring Tab ----
        tab_monitor = ttk.Frame(notebook)
        notebook.add(tab_monitor, text="Monitoring & Logs")
        self.status_var = tk.StringVar(value="Status: Idle")
        self.status_label = ttk.Label(tab_monitor, textvariable=self.status_var, foreground="blue", font=("Arial", 11, "bold"))
        self.status_label.pack(pady=8)

        btn_frame = ttk.Frame(tab_monitor)
        btn_frame.pack(pady=5)
        self.start_btn = ttk.Button(btn_frame, text="Start Monitoring", command=self.start_monitoring, width=20)
        self.start_btn.grid(row=0, column=0, padx=10)
        self.stop_btn = ttk.Button(btn_frame, text="Stop Monitoring", command=self.stop_monitoring, state="disabled", width=20)
        self.stop_btn.grid(row=0, column=1, padx=10)

        ttk.Label(tab_monitor, text=f"Telegram Bot is hardcoded ✅").pack(pady=5)
        ttk.Label(tab_monitor, text="Alerts Log:").pack(pady=(10,2))
        self.log_text = tk.Text(tab_monitor, height=20, width=80, state="disabled", bg="#f0f0f0")
        self.log_text.pack(pady=(0,10))
        self.log_text.tag_config("up", foreground="green")
        self.log_text.tag_config("down", foreground="red")
        self.log_text.tag_config("error", foreground="orange")

    # ---------------- Monitoring Control ----------------
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
            try: float(up); float(down)
            except ValueError:
                messagebox.showwarning("Invalid Threshold", f"Thresholds for {coin.title()} must be numbers.")
                return
            thresholds[coin] = {'up': up, 'down': down}

        interval = self.interval_var.get()
        self.monitor_thread = CryptoMonitor(
            coins, thresholds, self.currency_var.get().strip().lower(), interval,
            self.log_alert, self.update_prices
        )
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        self.status_var.set("Status: Monitoring...")
        self.status_label['foreground'] = "green"
        self.start_btn['state'] = "disabled"
        self.stop_btn['state'] = "normal"
        self.log_alert("Monitoring started.", "up")

    def stop_monitoring(self):
        if self.monitor_thread:
            self.monitor_thread.stop()
            self.monitor_thread = None
        self.status_var.set("Status: Idle")
        self.status_label['foreground'] = "blue"
        self.start_btn['state'] = "normal"
        self.stop_btn['state'] = "disabled"
        self.log_alert("Monitoring stopped.", "error")

    # ---------------- Logging ----------------
    def log_alert(self, msg, tag=""):
        self.log_text['state'] = "normal"
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        self.log_text.insert("end", f"{timestamp} - {msg}\n", tag)
        self.log_text.see("end")
        self.log_text['state'] = "disabled"

    # ---------------- Price Updates ----------------
    def update_prices(self, prices):
        for coin, price_var in self.price_vars.items():
            price = prices.get(coin, {}).get(self.currency_var.get(), "-")
            price_var.set(price)

    def on_closing(self):
        self.stop_monitoring()
        self.destroy()

if __name__ == "__main__":
    app = CryptoAlertApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
    
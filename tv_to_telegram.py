from flask import Flask, request
import requests
import os
import threading
import time

app = Flask(__name__)

# --- CONFIGURACIÓN (desde variables de entorno de Render) ---
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
RENDER_URL       = os.environ.get("RENDER_URL")  # ej: https://tvtotelegram-7plj.onrender.com

# --- WEBHOOK ---
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_data(as_text=True)
    send_telegram(data)
    return "ok", 200
    
# --- HEALTH CHECK ---
@app.route("/", methods=["GET", "HEAD"])
def root():
    return "ok", 200

# --- KEEP ALIVE ---
@app.route("/ping", methods=["GET"])
def ping():
    return "pong", 200


# --- SEND TELEGRAM ---
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    requests.post(url, json=payload)


# --- KEEP ALIVE HILO ---
def keepalive():
    while True:
        time.sleep(600)
        try:
            requests.get(f"{RENDER_URL}/ping", timeout=10)
        except Exception:
            pass


if __name__ == "__main__":
    t = threading.Thread(target=keepalive, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=5000)

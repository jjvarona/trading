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

# --- KEEP ALIVE ---
@app.route("/ping", methods=["GET"])
def ping():
    return "pong", 200

def keep_alive():
    while True:
        time.sleep(600)  # cada 10 minutos
        try:
            requests.get(f"{RENDER_URL}/ping", timeout=10)
        except Exception:
            pass

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    requests.post(url, json=payload)

if __name__ == "__main__":
    # Arrancar keep-alive en hilo separado
    t = threading.Thread(target=keep_alive, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=5000)
